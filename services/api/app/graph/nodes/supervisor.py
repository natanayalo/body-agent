from __future__ import annotations
import json
import os
from typing import Dict, List, Literal
import numpy as np
import logging
from app.graph.state import BodyState
from app.tools.embeddings import embed

# ---- Config ----
_EX_PATH = os.getenv("INTENT_EXEMPLARS_PATH")
_THRESHOLD = float(os.getenv("INTENT_THRESHOLD", "0.30"))
_MARGIN = float(os.getenv("INTENT_MARGIN", "0.05"))

_DEFAULT_EXAMPLES: Dict[str, List[str]] = {
    "symptom": [
        "I have a fever",
        "my head hurts",
        "I feel dizzy",
        "יש לי חום",
        "כואב לי הראש",
        "אני מרגיש חלש",
    ],
    "meds": [
        "refill my prescription",
        "took ibuprofen",
        "morning pill schedule",
        "אני צריך תרופה",
        "נטלתי תרופה",
        "תזכיר לי לקחת תרופה",
    ],
    "appointment": [
        "book a lab appointment",
        "schedule a doctor visit",
        "reschedule my appointment",
        "קבע תור לרופא",
        "קבע בדיקות דם",
        "שנה תור",
    ],
    "routine": [
        "set a reminder",
        "weekly check-in",
        "add a to-do",
        "הוסף תזכורת",
        "בדיקה שבועית",
    ],
}


def _load_exemplars() -> Dict[str, List[str]]:
    # Load exemplars from file if provided; otherwise defaults
    path = _EX_PATH
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Ensure only known intents & non-empty strings
            out = {}
            for k, vals in data.items():
                if k in {"symptom", "meds", "appointment", "routine"}:
                    out[k] = [v for v in vals if isinstance(v, str) and v.strip()]
            if out:
                logging.info(f"Loaded intent exemplars from {path}")
                return out
            else:
                logging.warning(
                    f"Exemplars file {path} is empty or malformed, using default exemplars."
                )
                return _DEFAULT_EXAMPLES
        except Exception as e:
            logging.error(
                f"Failed to load intent exemplars from {path}: {e}", exc_info=True
            )
            logging.info("Using default intent exemplars.")
            return _DEFAULT_EXAMPLES
    logging.info(
        "INTENT_EXEMPLARS_PATH not set or file not found, using default intent exemplars."
    )
    return _DEFAULT_EXAMPLES


_EXEMPLARS = _load_exemplars()
_EX_VECS = {
    k: np.array(embed(v)) if v else np.zeros((0, 384)) for k, v in _EXEMPLARS.items()
}


def detect_intent(
    text: str,
) -> Literal["meds", "appointment", "symptom", "routine", "other"]:
    # Embedding exemplar classifier with abstain (threshold + margin)
    q = np.array(embed([text])[0])
    # cosine since embeddings are normalized
    scores = {
        k: (vecs @ q).max() if len(vecs) else -1.0 for k, vecs in _EX_VECS.items()
    }
    logging.debug(f"Intent scores for '{text}': {scores}")  # Added print statement
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    if not ordered:
        return "other"
    top, s_top = ordered[0]
    s_second = ordered[1][1] if len(ordered) > 1 else -1.0
    if s_top >= _THRESHOLD and (s_top - s_second) >= _MARGIN:
        if top in {"symptom", "meds", "appointment", "routine"}:
            return top  # type: ignore
        else:
            return "other"
    return "other"


def run(state: BodyState) -> BodyState:
    state["intent"] = detect_intent(state["user_query"])
    return state
