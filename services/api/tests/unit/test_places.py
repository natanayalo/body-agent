from app.graph.nodes import places
from app.graph.state import BodyState


def test_places_ranking_respects_preferred_kind(monkeypatch):
    results = [
        {
            "name": "Clinic A",
            "phone": "+972-3-000-1111",
            "kind": "clinic",
            "_score": 0.8,
            "geo": {"lat": 32.081, "lon": 34.78},
            "hours": "Sun-Thu 12:00-20:00",
        },
        {
            "name": "Dizengoff Lab Center",
            "phone": "+972-3-555-0202",
            "kind": "lab",
            "_score": 0.7,
            "geo": {"lat": 32.0871, "lon": 34.7754},
            "hours": "Sun-Fri 07:00-14:00",
        },
    ]

    monkeypatch.setattr(
        places,
        "search_providers",
        lambda *args, **kwargs: results,
    )

    dummy_es = object()
    state = BodyState(
        user_query="book appointment",
        user_query_redacted="book appointment",
        preferences={"preferred_kinds": ["lab"], "hours_window": "morning"},
    )

    ranked_state = places.run(state, es_client=dummy_es)
    candidates = ranked_state["candidates"]
    assert candidates[0]["name"] == "Dizengoff Lab Center"
    assert any("preferred" in r for r in candidates[0].get("reasons", []))

    # Change preference to clinic and ensure ordering flips deterministically
    state["preferences"] = {"preferred_kinds": ["clinic"]}
    ranked_state = places.run(state, es_client=dummy_es)
    candidates = ranked_state["candidates"]
    assert candidates[0]["name"] == "Clinic A"


def test_places_filters_by_travel_limit(monkeypatch):
    near = {
        "name": "Nearby Clinic",
        "phone": "+972-3-555-0303",
        "kind": "clinic",
        "_score": 0.9,
        "geo": {"lat": 32.09, "lon": 34.78},
        "hours": "Sun-Thu 09:00-18:00",
    }
    far = {
        "name": "Far Specialist Center",
        "phone": "+972-4-555-0404",
        "kind": "clinic",
        "_score": 1.1,
        "geo": {"lat": 32.5, "lon": 35.3},
        "hours": "Sun-Thu 08:00-14:00",
    }

    monkeypatch.setattr(
        places,
        "search_providers",
        lambda *args, **kwargs: [near, far],
    )

    state = BodyState(
        user_query="nearby clinic",
        user_query_redacted="nearby clinic",
        preferences={"max_travel_km": 5},
    )

    ranked_state = places.run(state, es_client=object())
    candidates = ranked_state["candidates"]
    assert len(candidates) == 1
    assert candidates[0]["name"] == "Nearby Clinic"
    reasons = candidates[0].get("reasons", [])
    assert any("travel limit" in reason for reason in reasons)


def test_hours_windows_variants():
    assert places._hours_windows("") == set()
    assert places._hours_windows("Open all morning and evening") == {
        "morning",
        "evening",
    }
    assert places._hours_windows("Fri 21:00-23:00") == {"evening"}
    assert places._hours_windows("Sat 22:00-02:00") == {"evening"}


def test_normalize_handles_zero_vector():
    assert places._normalize([]) == []
    assert places._normalize([0.0, 0.0]) == [0.0, 0.0]
    assert places._normalize([0.2, 0.4]) == [0.5, 1.0]
