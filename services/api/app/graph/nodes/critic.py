from app.graph.state import BodyState


def run(state: BodyState) -> BodyState:
    # Require citations when health snippets are present
    if state.get("public_snippets") and not state.get("citations"):
        state.setdefault("alerts", []).append("No citations found; verify guidance.")
    # Minimal red-flag banner
    for snip in state.get("public_snippets", []):
        if str(snip.get("section", "")).lower() in {"warnings", "emergency"}:
            state.setdefault("alerts", []).append(
                "Potential red-flag detected. Consider urgent care if symptoms worsen."
            )
    return state
