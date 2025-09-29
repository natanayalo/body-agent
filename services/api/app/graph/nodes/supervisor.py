from __future__ import annotations
import json
import os
import re
from typing import Dict, List, Literal, Optional
import numpy as np
import logging
from app.graph.state import BodyState, SubIntent
from app.tools.embeddings import embed
from app.tools.med_normalize import find_medications_in_text

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


_SUB_INTENT_KEYWORDS: Dict[SubIntent, List[str]] = {
    "onset": [
        "when will it start",
        "when does it start",
        "how long until it",
        "how long until it works",
        "how long before it works",
        "how long before it starts",
        "start working",
        "kick in",
        "מתי זה מתחיל להשפיע",
        "מתי זה אמור להשפיע",
        "מתי התרופה אמורה להשפיע",
        "מתי זה משפיע",
        "מתי יתחיל להשפיע",
        "תוך כמה זמן",
        "תוך כמה זמן זה",
        "תוך כמה זמן זה משפיע",
        "תוך כמה זמן מתחיל להשפיע",
        "תוך כמה",
    ],
    "interaction": [
        "can i take with",
        "interaction with",
        "interaction",
        "interact with",
        "mix with",
        "take together",
        "take together with",
        "combine with",
        "אפשר לקחת עם",
        "מותר לקחת עם",
        "מותר עם",
        "בניגוד",
        "יחד עם",
        "אפשר לשלב",
        "מותר לשלב",
        "אפשר לקחת ביחד",
        "מותר לקחת ביחד",
        "לשלב עם",
    ],
    "schedule": [
        "remind me to take",
        "reminder to take",
        "schedule my meds",
        "schedule my medication",
        "schedule my medicine",
        "medication schedule",
        "meds schedule",
        "pill schedule",
        "dose schedule",
        "when should i take",
        "what time should i take",
        "how often should i take",
        "מתי לקחת",
        "איך לקחת",
        "תזכיר לי לקחת",
        "תזכורת לקחת",
        "להזכיר לי לקחת",
        "לוח זמנים לתרופות",
        "שעות לקיחה",
        "כמה פעמים ביום",
    ],
    "side_effects": [
        "side effect",
        "side effects",
        "adverse effect",
        "adverse effects",
        "reaction",
        "תופעת לוואי",
        "תופעות לוואי",
        "השפעות לוואי",
    ],
    "refill": [
        "refill",
        "refill my",
        "prescription renewal",
        "renew my prescription",
        "renew the prescription",
        "get a new prescription",
        "חדש מרשם",
        "רענן מרשם",
        "מרשם חוזר",
        "חידוש מרשם",
    ],
}

_MED_CONTEXT_TOKENS = {
    "meds",
    "medication",
    "medications",
    "medicine",
    "medicines",
    "pill",
    "pills",
    "tablet",
    "tablets",
    "dose",
    "doses",
    "dosing",
    "capsule",
    "capsules",
    "prescription",
    "prescriptions",
    "rx",
    "תרופה",
    "תרופות",
    "כדור",
    "כדורים",
}


def _has_med_context(text: str) -> bool:
    tokens = set(re.findall(r"\w+", text.lower()))
    return any(token in _MED_CONTEXT_TOKENS for token in tokens)


def detect_med_sub_intent(text: str) -> Optional[SubIntent]:
    lowered = text.lower()
    for sub_intent, keywords in _SUB_INTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in lowered:
                return sub_intent
    if " עם" in lowered and (
        "אפשר לקחת" in lowered or "מותר לקחת" in lowered or "לשלב" in lowered
    ):
        return "interaction"
    return None


def run(state: BodyState) -> BodyState:
    query_text = state.get("user_query_redacted", state.get("user_query", ""))
    detected_intent = detect_intent(query_text)
    state["intent"] = detected_intent
    logging.debug(f"Detected intent: {detected_intent}")

    normalized_meds = find_medications_in_text(query_text, state.get("language"))
    if normalized_meds:
        debug = state.setdefault("debug", {})
        debug["normalized_query_meds"] = normalized_meds

    sub_intent = detect_med_sub_intent(query_text)
    if sub_intent:
        has_context = bool(normalized_meds) or _has_med_context(query_text)

        if detected_intent == "meds":
            state["sub_intent"] = sub_intent
        elif has_context:
            state["intent"] = "meds"
            state["sub_intent"] = sub_intent
    return state
