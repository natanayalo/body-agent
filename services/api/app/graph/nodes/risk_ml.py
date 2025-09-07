from __future__ import annotations
import os
from typing import List, Dict, Tuple
from app.graph.state import BodyState

_PIPE = None


def _get_pipe():
    """Lazy-load a zero-shot classifier pipeline.

    Uses a multilingual NLI model by default so Hebrew/English both work.
    Falls back to no-op if model can't be loaded (offline build, etc.).
    """
    global _PIPE
    if _PIPE is not None:
        return _PIPE
    try:
        from transformers import pipeline

        model_id = os.getenv("RISK_MODEL_ID", "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli")
        _PIPE = pipeline("zero-shot-classification", model=model_id, device=-1)
    except Exception:
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

    if pipe is None or not labels:
        # Model couldn't load (offline) — degrade gracefully
        return state

    try:
        # Use multi_label=True so each label is independently scored
        res = pipe(
            text, candidate_labels=labels, hypothesis_template=hyp, multi_label=True
        )
        pairs: List[Tuple[str, float]] = list(
            zip(res.get("labels", []), [float(s) for s in res.get("scores", [])])
        )
    except Exception:
        return state

    # Map to UX
    msg_map = {
        "urgent_care": "Potential urgent issue — consider urgent evaluation.",
        "see_doctor": "Consider contacting your clinician soon.",
        "self_care": "Likely self-care with monitoring.",
        "info_only": "General information only.",
    }
    triggered = []
    for label, score in pairs:
        thr = thresholds.get(
            label, 1.1
        )  # default high so only listed thresholds can trigger
        if score >= thr:
            triggered.append((label, score))
            if label in ("urgent_care", "see_doctor"):
                state.setdefault("alerts", []).append(
                    f"ML risk: {label} (p={score:.2f})"
                )
                state.setdefault("messages", []).append(
                    {"role": "assistant", "content": msg_map.get(label, "")}
                )
    # If nothing triggered and we have no messages yet, provide the top-scoring label as gentle guidance
    if not triggered and not state.get("messages") and pairs:
        pairs_sorted = sorted(pairs, key=lambda x: x[1], reverse=True)
        label, score = pairs_sorted[0]
        state.setdefault("messages", []).append(
            {"role": "assistant", "content": msg_map.get(label, "")}
        )

    # Stash raw results for debugging
    state.setdefault("debug", {})["risk"] = {
        "scores": {label: s for label, s in pairs},
        "triggered": [{"label": label, "score": s} for label, s in triggered],
    }
    return state
