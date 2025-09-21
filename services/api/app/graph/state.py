from typing import Literal, TypedDict, Required


class BodyState(TypedDict, total=False):
    user_id: str
    user_query: Required[str]
    user_query_redacted: str
    language: Literal["en", "he"]
    intent: Literal["meds", "appointment", "symptom", "routine", "other"]
    memory_facts: list[dict]
    public_snippets: list[dict]
    candidates: list[dict]
    plan: dict
    preferences: dict
    messages: list[dict]
    alerts: list[str]
    citations: list[str]
    debug: dict
