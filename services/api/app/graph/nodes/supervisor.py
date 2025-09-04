from app.graph.state import BodyState


MED_TRIGGERS = ("med", "pill", "dose", "refill")
APPT_TRIGGERS = ("appointment", "book", "clinic", "lab")
SYMPTOM_TRIGGERS = ("symptom", "fever", "pain", "sore", "headache")


# Lightweight intent classifier (rule-based to avoid LLM dependency for MVP)
def detect_intent(text: str) -> str:
    lower = text.lower()
    if any(t in lower for t in MED_TRIGGERS):
        return "meds"
    if any(t in lower for t in APPT_TRIGGERS):
        return "appointment"
    if any(t in lower for t in SYMPTOM_TRIGGERS):
        return "symptom"
    return "other"


def run(state: BodyState) -> BodyState:
    state["intent"] = detect_intent(state["user_query"])
    return state
