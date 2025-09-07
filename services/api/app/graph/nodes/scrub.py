import re


def run(state):
    txt = state["user_query"]
    red = re.sub(r"\b[+]?\\d[\\d\\s\\-]{7,}\\b", "[phone]", txt)
    red = re.sub(r"[\\w\\.-]+@[\\w\\.-]+", "[email]", red)
    state["user_query_redacted"] = red
    return state
