import re
from typing import cast
from app.graph.state import BodyState


def run(state: BodyState) -> BodyState:
    txt = state.get("user_query", "")
    # Credit card numbers (most specific first)
    red = re.sub(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b", "[credit-card]", txt)

    # Social security numbers (US format)
    red = re.sub(r"\b\d{3}[\s\-]?\d{2}[\s\-]?\d{4}\b", "[ssn]", red)

    # Phone numbers (including international)
    red = re.sub(r"\s*\b[+]?\d[\d\s\-]{7,}\b\s*", " [phone] ", red)

    # Email addresses
    red = re.sub(r"\s*[\w\.-]+@[\w\.-]+\s*", " [email] ", red)

    # Clean up extra spaces
    red = re.sub(r"\s+", " ", red).strip()

    # Create a new state dict with the base required fields
    new_state = dict(state)  # Make a copy
    new_state["user_query"] = red
    new_state["user_query_redacted"] = red

    return cast(BodyState, new_state)
    txt = state.get("user_query", "")
    # Credit card numbers (most specific first)
    red = re.sub(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b", "[credit-card]", txt)

    # Social security numbers (US format)
    red = re.sub(r"\b\d{3}[\s\-]?\d{2}[\s\-]?\d{4}\b", "[ssn]", red)

    # Phone numbers (including international)
    red = re.sub(r"\s*\b[+]?\d[\d\s\-]{7,}\b\s*", " [phone] ", red)

    # Email addresses
    red = re.sub(r"\s*[\w\.-]+@[\w\.-]+\s*", " [email] ", red)

    # Clean up extra spaces
    red = re.sub(r"\s+", " ", red).strip()

    # Create a new state dict with the base required fields
    new_state = dict(state)  # Make a copy
    new_state["user_query"] = red
    new_state["user_query_redacted"] = red

    return cast(BodyState, new_state)
