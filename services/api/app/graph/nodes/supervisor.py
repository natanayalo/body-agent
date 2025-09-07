import numpy as np
from app.tools.embeddings import embed

INTENT_EXAMPLES = {
    "symptom": ["I have a fever", "my head hurts", "יש לי חום", "כואב לי"],
    "meds": ["refill my prescription", "took ibuprofen", "נטלתי תרופה"],
    "appointment": ["book a lab", "schedule a doctor visit", "קבע תור"],
}


def detect_intent(text: str) -> str:
    q = np.array(embed([text])[0])
    best, best_score = "other", -1
    for label, examples in INTENT_EXAMPLES.items():
        ex = np.array(embed(examples))
        score = (ex @ q).max()
        if score > best_score:
            best, best_score = label, score
    return best if best_score > 0.30 else "other"
