from __future__ import annotations
import os
import logging
from typing import List, Dict, Tuple, cast
from app.graph.state import BodyState

logger = logging.getLogger(__name__)

_PIPE = None


def _get_pipe():
    """Lazy-load a zero-shot classifier pipeline.
    Uses a multilingual NLI model by default so Hebrew/English both work.
    Falls back to no-op if model can't be loaded (offline build, etc.).
    """
    global _PIPE
    if _PIPE is not None:
        logger.debug("Using existing ML pipeline")
        return _PIPE

    model_id = os.getenv("RISK_MODEL_ID", "MoritzLaurer/mDeBERta-v3-base-mnli-xnli")

    if model_id == "__stub__":
        logger.info("Using stub ML pipeline")

        def stub_pipeline(text, candidate_labels, **kwargs):
            # deterministic scores for testing gating behavior
            scores = []
            for label in candidate_labels:
                if label == "urgent_care":
                    scores.append(0.9)  # High score to trigger urgent_care
                elif label == "see_doctor":
                    scores.append(0.6)  # High score to trigger see_doctor
                else:
                    scores.append(0.1)  # Low score for other labels
            return {"labels": candidate_labels, "scores": scores}

        _PIPE = stub_pipeline
        return _PIPE

    try:
        from transformers import pipeline

        logger.info(f"Loading ML model: {model_id}")
        _PIPE = pipeline("zero-shot-classification", model=model_id, device=-1)
        logger.info("ML pipeline initialized successfully")
    except Exception as e:
        logger.error(f"Failed to load ML pipeline: {str(e)}", exc_info=True)
        _PIPE = None
    return _PIPE


def _parse_thresholds(spec: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    if not spec:
        logger.debug("No risk thresholds specified")
        return out
    logger.debug(f"Parsing risk thresholds from spec: {spec}")
    for part in spec.split(","):
        if ":" in part:
            k, v = part.split(":", 1)
            try:
                out[k.strip()] = float(v)
                logger.debug(f"Added threshold {k.strip()}={float(v)}")
            except ValueError:
                logger.warning(f"Invalid threshold value in RISK_THRESHOLDS: {part}")
    logger.info(f"Parsed thresholds: {out}")
    return out


def run(state: BodyState) -> BodyState:
    """Classify risk level using open-source NLI (no hardcoded red flags).

    Inputs: state.user_query (+ meds context if available)
    Outputs: appends alerts/messages with an ML-backed label and confidence.
    """
    logger.info("Starting risk classification")

    pipe = _get_pipe()
    if pipe is None:
        logger.warning("ML pipeline unavailable - skipping risk classification")
        return state

    labels = [
        s.strip()
        for s in os.getenv(
            "RISK_LABELS", "urgent_care,see_doctor,self_care,info_only"
        ).split(",")
        if s.strip()
    ]
    logger.debug(f"Using risk labels: {labels}")

    thresholds = _parse_thresholds(
        os.getenv("RISK_THRESHOLDS", "urgent_care:0.55,see_doctor:0.50")
    )
    hyp = os.getenv("RISK_HYPOTHESIS", "This situation requires {}.")
    logger.debug(f"Using hypothesis template: {hyp}")

    # Build text with lightweight context (med names only)
    text = state.get("user_query_redacted", state["user_query"])
    logger.debug(f"Base query text: {state.get('user_query_redacted', text)}")

    meds = []
    for m in state.get("memory_facts") or []:
        if m.get("entity") == "medication":
            med_name = m.get("normalized", {}).get("ingredient") or m.get("name") or ""
            if med_name:
                meds.append(med_name)
                logger.debug(f"Added medication context: {med_name}")

    if meds:
        text += "\nContext meds: " + ", ".join(sorted(set(meds)))
        logger.debug(f"Final text with med context: {text}")

    if not labels:
        logger.warning("No risk labels configured - skipping classification")
        return state

    try:
        logger.info("Running risk classification")
        # Use multi_label=True so each label is independently scored
        res = cast(
            dict,
            pipe(
                text, candidate_labels=labels, hypothesis_template=hyp, multi_label=True
            ),
        )
        pairs: List[Tuple[str, float]] = list(
            zip(res.get("labels", []), [float(s) for s in res.get("scores", [])])
        )
        logger.debug(f"Classification results: {pairs}")
    except Exception as e:
        logger.error(f"Risk classification failed: {str(e)}", exc_info=True)
        return state

    # Map to UX
    msg_map = {
        "urgent_care": "Potential urgent issue — consider urgent evaluation.",
        "see_doctor": "Consider contacting your clinician soon.",
        "self_care": "Likely self-care with monitoring.",
        "info_only": "General information only.",
    }
    logger.debug(f"Using message map: {msg_map}")

    triggered = []
    for label, score in pairs:
        thr = thresholds.get(
            label, 1.1
        )  # default high so only listed thresholds can trigger
        logger.debug(f"Checking {label} (score={score:.3f}) against threshold {thr}")

        if score >= thr:
            triggered.append((label, score))
            logger.info(f"Triggered risk label: {label} with score {score:.3f}")

            if label in ("urgent_care", "see_doctor"):
                alert = f"ML risk: {label} (p={score:.2f})"
                state.setdefault("alerts", []).append(alert)
                message = {"role": "assistant", "content": msg_map.get(label, "")}
                state.setdefault("messages", []).append(message)
                logger.info(f"Added alert: {alert}")
                logger.info(f"Added message: {message}")

    # If nothing triggered and we have no messages yet, provide the top-scoring label as gentle guidance
    if not triggered and not state.get("messages") and pairs:
        logger.info("No triggers - using top score for gentle guidance")
        pairs_sorted = sorted(pairs, key=lambda x: x[1], reverse=True)
        label, score = pairs_sorted[0]
        message = {"role": "assistant", "content": msg_map.get(label, "")}
        state.setdefault("messages", []).append(message)
        logger.info(f"Added gentle guidance message for {label} (score={score:.3f})")

    # Stash raw results for debugging
    state.setdefault("debug", {})["risk"] = {
        "scores": {label: s for label, s in pairs},
        "triggered": [{"label": label, "score": s} for label, s in triggered],
    }
    return state
