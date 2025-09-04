from typing import Literal, TypedDict, Any


class BodyState(TypedDict, total=False):
    user_id: str
    user_query: str
    intent: Literal["meds","appointment","symptom","routine","other"]
    memory_facts: list[dict]
    public_snippets: list[dict]
    candidates: list[dict]
    plan: dict
    messages: list[dict]
    alerts: list[str]
    citations: list[str]
