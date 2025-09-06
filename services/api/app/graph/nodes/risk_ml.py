from __future__ import annotations
import os
from typing import Dict
from app.graph.state import BodyState

_PIPE = None


def _get_pipe():
    """Lazy-load a zero-shot classifier pipeline.

    Uses a multilingual NLI model by default so Hebrew/English both work.
    Falls back to no-op if model can't be loaded (offline build, etc.).
    """
    global _PIPE
    print("risk_ml.py: _get_pipe() called")
    if _PIPE is not None:
        print("risk_ml.py: returning cached pipe")
        return _PIPE
    try:
        print("risk_ml.py: importing pipeline from transformers")
        from transformers import pipeline

        print("risk_ml.py: pipeline imported successfully")
        model_id = os.getenv("RISK_MODEL_ID", "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli")
        print(f"risk_ml.py: loading model {model_id}")
        _PIPE = pipeline("zero-shot-classification", model=model_id, device=-1)
        print("risk_ml.py: pipeline created successfully")
    except Exception as e:
        print(f"risk_ml.py: exception in _get_pipe: {e}")
        _PIPE = None
    return _PIPE


def _parse_thresholds(spec: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    if not spec:
        return out
    for part in spec.split(","):
        if ":" in part:
            k, v = part.split(":", 1)
            try:
                out[k.strip()] = float(v)
            except ValueError:
                pass
    return out


def run(state: BodyState) -> BodyState:
    """Classify risk level using open-source NLI (no hardcoded red flags).

    Inputs: state.user_query (+ meds context if available)
    Outputs: appends alerts/messages with an ML-backed label and confidence.
    """
    print("risk_ml.py: run() called")
    pipe = _get_pipe()
    labels = [
        s.strip()
        for s in os.getenv(
            "RISK_LABELS", "urgent_care,see_doctor,self_care,info_only"
        ).split(",")
        if s.strip()
    ]
    thresholds = _parse_thresholds(
        os.getenv("RISK_THRESHOLDS", "urgent_care:0.55,see_doctor:0.50")
    )
    hyp = os.getenv("RISK_HYPOTHESIS", "This situation requires {}.")

    # Build text with lightweight context (med names only)
    text = state.get("user_query", "")
    print(f"risk_ml.py: initial text: {text}")
    meds = []
    for m in state.get("memory_facts") or []:
        if m.get("entity") == "medication":
            meds.append(
                m.get("name") or m.get("normalized", {}).get("ingredient") or ""
            )
    if meds:
        text = (
            text + "\nContext meds: " + ", ".join(sorted(set([m for m in meds if m])))
        )

    print(f"risk_ml.py: text with context: {text}")

    if pipe is None or not labels:
        print("risk_ml.py: pipe is None or no labels, returning")
        # Model couldn't load (offline) — degrade gracefully
        return state

    try:
        print("risk_ml.py: calling pipeline")
        res = pipe(
            text, candidate_labels=labels, hypothesis_template=hyp, multi_label=False
        )
        print(f"risk_ml.py: pipeline result: {res}")
        top_label = res.get("labels", [None])[0]
        top_score = float(res.get("scores", [0.0])[0])
        print(f"risk_ml.py: top_label: {top_label}, top_score: {top_score}")
    except Exception as e:
        print(f"risk_ml.py: exception in run: {e}")
        return state

    # Map to UX
    msg_map = {
        "urgent_care": "Potential urgent issue — consider urgent evaluation.",
        "see_doctor": "Consider contacting your clinician soon.",
        "self_care": "Likely self-care with monitoring.",
        "info_only": "General information only.",
    }

    if top_label in ("urgent_care", "see_doctor"):
        thr = thresholds.get(top_label, 0.5)
        if top_score >= thr:
            print(f"risk_ml.py: adding alert for {top_label}")
            state.setdefault("alerts", []).append(
                f"ML risk: {top_label} (p={top_score:.2f})"
            )
            state.setdefault("messages", []).append(
                {"role": "assistant", "content": msg_map.get(top_label, "")}
            )
    elif top_label in ("self_care", "info_only"):
        # add a gentle message if no other guidance present
        if not state.get("messages"):
            print(f"risk_ml.py: adding gentle message for {top_label}")
            state.setdefault("messages", []).append(
                {"role": "assistant", "content": msg_map.get(top_label, "")}
            )

    # Always stash the raw result for debugging (non-PII)
    print("risk_ml.py: setting debug.risk")
    state.setdefault("debug", {})["risk"] = {"label": top_label, "score": top_score}
    return state
