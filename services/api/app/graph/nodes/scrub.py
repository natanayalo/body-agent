import re
from typing import cast
from app.graph.state import BodyState
from app.tools.language import (
    resolve_language,
    normalize_language_code,
    pivot_to_english,
)


_CREDIT_CARD_RE = re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b")
_SSN_RE = re.compile(r"\b\d{3}[\s\-]?\d{2}[\s\-]?\d{4}\b")
_GOV_ID_RE = re.compile(
    r"\b(?:social security number|passport(?: number)?|national id|gov(?:ernment)? id|id(?: number)?|license(?: number)?|תעודת זהות|ת\.ז\.?)\s*[:#]?\s*(?:[A-Za-z0-9\-]{3,}|\[ssn\])",
    flags=re.IGNORECASE,
)
_PHONE_RE = re.compile(r"\s*\b[+]?\d[\d\s\-]{7,}\b\s*")
_STREET_SUFFIXES = (
    "street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|court|ct|"
    "way|place|pl|terrace|ter|circle|cir"
)
_ADDR_EN_RE = re.compile(
    rf"\b\d{{1,5}}\s+(?:[A-Za-z\u0590-\u05FF]+\s+){{0,5}}(?:{_STREET_SUFFIXES})\b\.?",
    flags=re.IGNORECASE,
)
_ADDR_HE_RE = re.compile(
    r"\b(?:[בל]?רחוב)\s+(?:[^\s\d]+\s*)+\d{1,4}\b",
    flags=re.UNICODE,
)
_EMAIL_RE = re.compile(r"\s*[\w\.-]+@[\w\.-]+\s*")
_WHITESPACE_RE = re.compile(r"\s+")


def run(state: BodyState) -> BodyState:
    txt = state.get("user_query", "")
    red = _CREDIT_CARD_RE.sub("[credit-card]", txt)
    red = _SSN_RE.sub("[ssn]", red)
    red = _GOV_ID_RE.sub(" [gov_id] ", red)
    red = _PHONE_RE.sub(" [phone] ", red)
    red = _ADDR_EN_RE.sub(" [address] ", red)
    red = _ADDR_HE_RE.sub(" [address] ", red)
    red = _EMAIL_RE.sub(" [email] ", red)
    red = _WHITESPACE_RE.sub(" ", red).strip()

    # Create a new state dict with the base required fields
    new_state = dict(state)  # Make a copy
    new_state["user_query"] = red
    new_state["user_query_redacted"] = red
    existing = new_state.get("language")
    normalized = normalize_language_code(
        existing if isinstance(existing, str) else None
    )
    language = normalized or resolve_language(None, txt)
    new_state["language"] = language

    pivot = pivot_to_english(red, language)
    if pivot:
        new_state["user_query_pivot"] = pivot
    else:
        new_state.pop("user_query_pivot", None)

    return cast(BodyState, new_state)
