import re


def run(state):
    txt = state["user_query"]
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

    state["user_query_redacted"] = red
    state["user_query"] = red  # Also update the original query
    return state
