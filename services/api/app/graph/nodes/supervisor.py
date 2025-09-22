from __future__ import annotations
import json
import os
from typing import Dict, List, Literal, Optional
import numpy as np
import logging
from app.graph.state import BodyState
from app.tools.embeddings import embed

# ---- Config ----
_EX_PATH = os.getenv("INTENT_EXEMPLARS_PATH")
_THRESHOLD = float(os.getenv("INTENT_THRESHOLD", "0.30"))
_MARGIN = float(os.getenv("INTENT_MARGIN", "0.05"))
_WATCH = os.getenv("INTENT_EXEMPLARS_WATCH", "false").strip().lower() == "true"
_EX_MTIME: Optional[float] = None

_DEFAULT_EXAMPLES: Dict[str, List[str]] = {
    "symptom": [
        "I have a fever",
        "my head hurts",
        "I feel dizzy",
        "יש לי חום",
        "כואב לי הראש",
        "אני מרגיש חלש",
        "כואבת לי הבטן",
        "כאבי בטן",
        "מה אפשר לקחת לכאבי בטן",
    ],
    "meds": [
        "refill my prescription",
        "took ibuprofen",
        "morning pill schedule",
        "אני צריך תרופה",
        "נטלתי תרופה",
        "תזכיר לי לקחת תרופה",
        "drug interaction",
        "can I combine these pills",
        "is it safe to take with",
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
    "other": [
        "where can I eat near me",
        "find a restaurant nearby",
        "what's a good place to eat",
        "recommend activities",
        "איפה אפשר לאכול",
        "מסעדה ליד הבית",
        "מה לעשות הערב",
    ],
}


def _parse_json_exemplars(obj: dict) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for k, vals in obj.items():
        if k in {"symptom", "meds", "appointment", "routine", "other"}:
            out[k] = [v for v in vals if isinstance(v, str) and v.strip()]
    return out


def _parse_jsonl_exemplars(lines: List[str]) -> Dict[str, List[str]]:
    buckets: Dict[str, List[str]] = {
        k: [] for k in ["symptom", "meds", "appointment", "routine", "other"]
    }
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        intent = rec.get("intent") or rec.get("label")
        text = rec.get("text") or rec.get("example")
        if isinstance(intent, str) and isinstance(text, str):
            if intent in buckets and text.strip():
                buckets[intent].append(text.strip())
    # remove empty buckets
    return {k: v for k, v in buckets.items() if v}


def _load_exemplars() -> Dict[str, List[str]]:
    # Load exemplars from file if provided; otherwise defaults
    global _EX_MTIME
    path = _EX_PATH
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                if path.endswith(".jsonl"):
                    data = _parse_jsonl_exemplars(f.readlines())
                else:
                    data = _parse_json_exemplars(json.load(f))
            if data:
                try:
                    _EX_MTIME = os.path.getmtime(path)
                except OSError:
                    _EX_MTIME = None
                logging.info(f"Loaded intent exemplars from {path}")
                return data
            logging.warning(
                f"Exemplars file {path} is empty or malformed, using default exemplars."
            )
            return _DEFAULT_EXAMPLES
        except (OSError, json.JSONDecodeError) as e:
            logging.error(
                f"Failed to load intent exemplars from {path}: {e}", exc_info=True
            )
            logging.info("Using default intent exemplars.")
            return _DEFAULT_EXAMPLES
    logging.info(
        "INTENT_EXEMPLARS_PATH not set or file not found, using default exemplars."
    )
    return _DEFAULT_EXAMPLES


_EXEMPLARS = _load_exemplars()
_EX_VECS: Dict[str, np.ndarray] = {}


def _rebuild_vectors() -> None:
    global _EX_VECS
    _EX_VECS = {
        k: np.array(embed(v)) if v else np.zeros((0, 384))
        for k, v in _EXEMPLARS.items()
    }


_rebuild_vectors()


def _maybe_reload() -> None:
    if not _WATCH:
        return
    path = _EX_PATH
    if not path or not os.path.exists(path):
        return
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return
    global _EX_MTIME, _EXEMPLARS
    if _EX_MTIME is None or mtime > _EX_MTIME:
        new_map = _load_exemplars()
        if new_map:
            _EXEMPLARS = new_map
            _rebuild_vectors()
            logging.info("Reloaded intent exemplars after file change")


def detect_intent(
    text: str,
) -> Literal["meds", "appointment", "symptom", "routine", "other"]:
    # Embedding exemplar classifier with abstain (threshold + margin)
    _maybe_reload()
    q = np.array(embed([text])[0])
    # cosine since embeddings are normalized
    scores = {
        k: (vecs @ q).max() if len(vecs) else -1.0 for k, vecs in _EX_VECS.items()
    }

    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    if not ordered:
        return "other"
    top, s_top = ordered[0]
    s_second = ordered[1][1] if len(ordered) > 1 else -1.0
    if s_top >= _THRESHOLD and (s_top - s_second) >= _MARGIN:
        if top in {"symptom", "meds", "appointment", "routine", "other"}:
            return top  # type: ignore
        else:
            return "other"
    return "other"


def run(state: BodyState) -> BodyState:
    detected_intent = detect_intent(
        state.get("user_query_redacted", state.get("user_query", ""))
    )
    state["intent"] = detected_intent
    logging.debug(f"Detected intent: {detected_intent}")
    return state
