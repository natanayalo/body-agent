from app.graph.state import BodyState


def run(state: BodyState) -> BodyState:
    # Require citations when health snippets are present
    if state.get("public_snippets") and not state.get("citations"):
        state.setdefault("alerts", []).append("No citations found; verify guidance.")
    # Gate the red-flag banner by ML risk (if available)
    risk = (state.get("debug") or {}).get("risk") or {}
    tri = {t.get("label"): t.get("score") for t in risk.get("triggered", [])}
    if any(lbl in tri for lbl in ("urgent_care", "see_doctor")):
        state.setdefault("alerts", []).append(
            "Potential red-flag detected. Consider urgent care if symptoms worsen."
        )
    return state
