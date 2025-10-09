import pytest

from app.graph.nodes import places
from app.graph.nodes.places import _should_replace_candidate
from app.graph.nodes.rationale_codes import (
    HOURS_MATCH,
    TRAVEL_WITHIN_LIMIT,
    PREFERRED_KIND,
    INSURANCE_MATCH,
)
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
    codes = set(candidates[0].get("reason_codes", []))
    assert PREFERRED_KIND in codes
    assert HOURS_MATCH in codes

    # Change preference to clinic and ensure ordering flips deterministically
    state["preferences"] = {"preferred_kinds": ["clinic"]}
    ranked_state = places.run(state, es_client=dummy_es)
    candidates = ranked_state["candidates"]
    assert candidates[0]["name"] == "Clinic A"
    assert PREFERRED_KIND in set(candidates[0].get("reason_codes", []))


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
    assert TRAVEL_WITHIN_LIMIT in set(candidates[0].get("reason_codes", []))


def test_places_dedupe_prefers_in_range(monkeypatch):
    far = {
        "name": "Unified Clinic",
        "phone": "+972-3-555-0505",
        "kind": "clinic",
        "_score": 1.0,
        "geo": {"lat": 32.2, "lon": 34.9},
        "hours": "Sun-Thu 09:00-17:00",
    }
    near = {
        "name": "Unified Clinic",
        "phone": "+972-3-555-0505",
        "kind": "clinic",
        "_score": 0.8,
        "geo": {"lat": 32.089, "lon": 34.781},
        "hours": "Sun-Thu 09:00-17:00",
    }

    monkeypatch.setattr(
        places,
        "search_providers",
        lambda *args, **kwargs: [far.copy(), near.copy()],
    )

    state = BodyState(
        user_query="clinic",
        user_query_redacted="clinic",
        preferences={"max_travel_km": 5},
    )

    ranked_state = places.run(state, es_client=object())
    candidates = ranked_state["candidates"]
    assert len(candidates) == 1
    assert candidates[0]["phone"] == far["phone"]
    assert candidates[0]["_score"] == 0.8
    assert candidates[0]["distance_km"] < 5
    assert TRAVEL_WITHIN_LIMIT in set(candidates[0].get("reason_codes", []))


def test_places_dedupe_prefers_closer_on_tie(monkeypatch):
    farther = {
        "name": "Tie Clinic",
        "phone": "+972-3-555-0606",
        "kind": "clinic",
        "_score": 1.0,
        "geo": {"lat": 32.12, "lon": 34.83},
        "hours": "Sun-Thu 09:00-17:00",
    }
    closer = {
        "name": "Tie Clinic",
        "phone": "+972-3-555-0606",
        "kind": "clinic",
        "_score": 1.0,
        "geo": {"lat": 32.09, "lon": 34.79},
        "hours": "Sun-Thu 09:00-17:00",
    }

    monkeypatch.setattr(
        places,
        "search_providers",
        lambda *args, **kwargs: [farther.copy(), closer.copy()],
    )

    state = BodyState(
        user_query="clinic",
        user_query_redacted="clinic",
        preferences={"max_travel_km": 10},
    )

    ranked_state = places.run(state, es_client=object())
    candidates = ranked_state["candidates"]
    assert len(candidates) == 1
    assert candidates[0]["geo"] == closer["geo"]


def test_places_dedupe_prefers_higher_score_when_no_limit(monkeypatch):
    lower_score = {
        "name": "Score Clinic",
        "phone": "+972-3-555-0707",
        "kind": "clinic",
        "_score": 0.7,
        "geo": {"lat": 32.18, "lon": 34.9},
        "hours": "Sun-Thu 09:00-17:00",
    }
    higher_score = {
        "name": "Score Clinic",
        "phone": "+972-3-555-0707",
        "kind": "clinic",
        "_score": 1.2,
        "geo": {"lat": 32.25, "lon": 35.1},
        "hours": "Sun-Thu 09:00-17:00",
    }

    monkeypatch.setattr(
        places,
        "search_providers",
        lambda *args, **kwargs: [lower_score.copy(), higher_score.copy()],
    )

    state = BodyState(
        user_query="clinic",
        user_query_redacted="clinic",
        preferences={},
    )

    ranked_state = places.run(state, es_client=object())
    candidates = ranked_state["candidates"]
    assert len(candidates) == 1
    assert candidates[0]["_score"] == 1.2


def test_should_replace_candidate_prefers_in_range():
    existing = ({"_score": 1.2}, 8.0)
    candidate = ({"_score": 0.9}, 4.0)
    assert _should_replace_candidate(existing, candidate, travel_limit_km=5)


def test_should_replace_candidate_rejects_out_of_range():
    existing = ({"_score": 0.9}, 4.0)
    candidate = ({"_score": 1.5}, 8.0)
    assert not _should_replace_candidate(existing, candidate, travel_limit_km=5)


def test_places_insurance_preference_ranking(monkeypatch):
    unmatched = {
        "name": "Clinic Out",
        "phone": "+972-3-999-8888",
        "kind": "clinic",
        "_score": 1.1,
        "geo": {"lat": 32.18, "lon": 34.9},
        "insurance_plans": ["clalit"],
    }
    matched = {
        "name": "Insurance Center",
        "phone": "+972-3-777-6666",
        "kind": "clinic",
        "_score": 0.9,
        "geo": {"lat": 32.09, "lon": 34.78},
        "insurance_plans": ["maccabi", "clalit"],
    }

    monkeypatch.setenv(
        "PREFERENCE_SCORING_WEIGHTS",
        "semantic:0.2,distance:0.2,hours:0.0,insurance:0.6",
    )
    monkeypatch.setattr(
        places,
        "search_providers",
        lambda *args, **kwargs: [unmatched, matched],
    )

    state = BodyState(
        user_query="insurance match",
        user_query_redacted="insurance match",
        preferences={"insurance_plan": "Maccabi", "max_travel_km": 20},
    )

    ranked_state = places.run(state, es_client=object())
    top = ranked_state["candidates"][0]
    assert top["name"] == "Insurance Center"
    assert "Accepts your Maccabi insurance" in top.get("reasons", [])
    codes = set(top.get("reason_codes", []))
    assert INSURANCE_MATCH in codes
    assert top.get("matched_insurance_label") == "Maccabi"


@pytest.mark.parametrize(
    "weights_str, expected",
    [
        ("semantic:0.7,distance:0.2,hours:0.0,insurance:0.1", "Semantic Specialist"),
        ("semantic:0.1,distance:0.8,hours:0.0,insurance:0.1", "Nearby Clinic"),
        ("semantic:0.1,distance:0.1,hours:0.0,insurance:0.8", "Insurance Match Center"),
    ],
)
def test_places_scoring_weights_permutations(monkeypatch, weights_str, expected):
    semantic = {
        "name": "Semantic Specialist",
        "phone": "+972-3-555-1112",
        "kind": "clinic",
        "_score": 1.0,
        "geo": {"lat": 32.3, "lon": 34.9},
        "insurance_plans": ["private"],
    }
    nearby = {
        "name": "Nearby Clinic",
        "phone": "+972-3-555-1113",
        "kind": "clinic",
        "_score": 0.6,
        "geo": {"lat": 32.09, "lon": 34.78},
        "insurance_plans": ["clalit"],
    }
    insurance = {
        "name": "Insurance Match Center",
        "phone": "+972-3-555-1114",
        "kind": "clinic",
        "_score": 0.6,
        "geo": {"lat": 32.3, "lon": 35.1},
        "insurance_plans": ["maccabi"],
    }

    monkeypatch.setenv("PREFERENCE_SCORING_WEIGHTS", weights_str)
    monkeypatch.setattr(
        places,
        "search_providers",
        lambda *args, **kwargs: [semantic, nearby, insurance],
    )

    state = BodyState(
        user_query="find clinic",
        user_query_redacted="find clinic",
        preferences={"insurance_plan": "Maccabi", "max_travel_km": 50},
    )

    ranked_state = places.run(state, es_client=object())
    assert ranked_state["candidates"][0]["name"] == expected


def test_places_scoring_weights_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("PREFERENCE_SCORING_WEIGHTS", raising=False)
    weights = places._get_scoring_weights()
    assert weights == places.DEFAULT_WEIGHTS


def test_places_scoring_weights_parses_and_normalizes(monkeypatch):
    monkeypatch.setenv(
        "PREFERENCE_SCORING_WEIGHTS",
        "semantic:2.0, distance:1.0, hours:0.0, insurance:1.0,ignored,-foo:-1",
    )
    weights = places._get_scoring_weights()
    total = sum(weights.values())
    assert pytest.approx(total, rel=1e-6) == 1.0
    assert pytest.approx(weights["semantic"], rel=1e-6) == 0.5
    assert pytest.approx(weights["distance"], rel=1e-6) == 0.25
    assert pytest.approx(weights["insurance"], rel=1e-6) == 0.25
    assert pytest.approx(weights["hours"], rel=1e-6) == 0.0


def test_places_extract_plan_map_handles_iterables():
    plans, display = places._extract_plan_map([" Maccabi ", "clalit", "maccabi"])
    assert plans == {"maccabi": "Maccabi", "clalit": "clalit"}
    assert display == "Maccabi"


def test_places_extract_plan_map_from_string():
    plans, display = places._extract_plan_map(" Meuhedet ")
    assert plans == {"meuhedet": "Meuhedet"}
    assert display == "Meuhedet"


def test_places_extract_plan_map_from_set():
    plans, display = places._extract_plan_map({" Clalit ", "Meuhedet"})
    assert plans[display.lower()] == display
    assert set(plans.keys()) == {"clalit", "meuhedet"}


def test_places_insurance_reason_not_added_without_candidate_data(monkeypatch):
    # Candidate lacks insurance info, so reason code should not be set
    monkeypatch.setenv(
        "PREFERENCE_SCORING_WEIGHTS",
        "semantic:0.6,distance:0.3,hours:0.1,insurance:0.0",
    )

    candidate = {
        "name": "No Insurance Clinic",
        "phone": "+972-3-111-2222",
        "kind": "clinic",
        "_score": 0.9,
        "geo": {"lat": 32.1, "lon": 34.8},
    }

    monkeypatch.setattr(
        places,
        "search_providers",
        lambda *args, **kwargs: [candidate],
    )

    state = BodyState(
        user_query="clinic",
        user_query_redacted="clinic",
        preferences={"insurance_plan": "Maccabi", "max_travel_km": 10},
    )

    ranked_state = places.run(state, es_client=object())
    top = ranked_state["candidates"][0]
    assert "reason_codes" not in top or INSURANCE_MATCH not in set(
        top.get("reason_codes", [])
    )
    assert "matched_insurance_label" not in top


def test_places_hours_mismatch_zeroes_hours_fit():
    # Directly exercise meta computation to check hours mismatch path
    candidate = {
        "name": "Clinic",
        "phone": "+972-3-222-3333",
        "kind": "clinic",
        "_score": 1.0,
        "hours": "Sun-Thu 08:00-12:00",
    }
    semantic_norm = 1.0
    prefs = {"hours_window": "evening", "preferred_kinds": []}
    travel_limit = None
    distance = 2.0
    weights = places._get_scoring_weights()

    score, reasons, _distance, reason_codes = places._compute_candidate_meta(
        candidate, semantic_norm, prefs, travel_limit, distance, weights
    )

    assert not any("Open during" in r for r in reasons)
    assert HOURS_MATCH not in reason_codes
    assert score < semantic_norm  # hours penalty applied


def test_places_scoring_weights_negative_values_removed(monkeypatch):
    monkeypatch.setenv(
        "PREFERENCE_SCORING_WEIGHTS",
        "semantic:1.0,insurance:-1.0,distance:1.0,hours:0.0",
    )
    weights = places._get_scoring_weights()
    assert weights["insurance"] == pytest.approx(0.0)
    assert sum(weights.values()) == pytest.approx(1.0)


def test_places_travel_limit_only_reason():
    weights = places._get_scoring_weights()
    candidate = {"name": "Clinic", "phone": "+972", "kind": "clinic"}
    prefs = {"preferred_kinds": []}
    score, reasons, distance, reason_codes = places._compute_candidate_meta(
        candidate,
        semantic_norm=0.5,
        prefs=prefs,
        travel_limit_km=5,
        distance_km=None,
        weights=weights,
    )
    assert TRAVEL_WITHIN_LIMIT in reason_codes
    assert all("travel limit" not in r for r in reasons)
    assert "matched_insurance_label" not in candidate
    assert distance is None


def test_places_scoring_weights_invalid_falls_back(monkeypatch):
    monkeypatch.setenv(
        "PREFERENCE_SCORING_WEIGHTS",
        "semantic:0,distance:0,hours:0,insurance:0",
    )
    called = {}

    def _warn(message, *_args, **_kwargs):
        called["warned"] = message

    monkeypatch.setattr(places.logger, "warning", _warn)
    weights = places._get_scoring_weights()
    assert weights == places.DEFAULT_WEIGHTS
    assert "Invalid PREFERENCE_SCORING_WEIGHTS" in called["warned"]


def test_should_replace_candidate_prefers_closer_same_score():
    existing = ({"_score": 1.0}, 4.5)
    candidate = ({"_score": 1.0}, 3.0)
    assert _should_replace_candidate(existing, candidate, travel_limit_km=10)


def test_should_replace_candidate_keeps_closer_when_new_farther():
    existing = ({"_score": 1.0}, 3.0)
    candidate = ({"_score": 1.0}, 4.5)
    assert not _should_replace_candidate(existing, candidate, travel_limit_km=10)


def test_should_replace_candidate_prefers_higher_score_no_limit():
    existing = ({"_score": 0.8}, 6.0)
    candidate = ({"_score": 1.1}, 7.0)
    assert _should_replace_candidate(existing, candidate, travel_limit_km=None)


def test_should_replace_candidate_defaults_to_existing():
    existing = ({"_score": 0.9}, None)
    candidate = ({"_score": 0.9}, None)
    assert not _should_replace_candidate(existing, candidate, travel_limit_km=None)


def test_should_replace_candidate_handles_missing_candidate_distance():
    existing = ({"_score": 1.0}, 3.0)
    candidate = ({"_score": 1.5}, None)
    assert not _should_replace_candidate(existing, candidate, travel_limit_km=5)


def test_should_replace_candidate_handles_missing_existing_distance():
    existing = ({"_score": 1.0}, None)
    candidate = ({"_score": 0.8}, 3.0)
    assert _should_replace_candidate(existing, candidate, travel_limit_km=5)


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


def test_places_handles_missing_geo(monkeypatch):
    no_geo = {
        "name": "No Geo Clinic",
        "phone": "+972-3-555-0808",
        "kind": "clinic",
        "_score": 0.6,
        "hours": "Sun-Thu 09:00-17:00",
    }

    monkeypatch.setattr(
        places,
        "search_providers",
        lambda *args, **kwargs: [no_geo.copy()],
    )

    state = BodyState(
        user_query="clinic",
        user_query_redacted="clinic",
        preferences={"max_travel_km": 5},
    )

    ranked_state = places.run(state, es_client=object())
    candidates = ranked_state["candidates"]
    assert len(candidates) == 1
    assert "distance_km" not in candidates[0]
    assert TRAVEL_WITHIN_LIMIT in set(candidates[0].get("reason_codes", []))


def test_places_handles_invalid_geo(monkeypatch):
    invalid_geo = {
        "name": "Invalid Geo Clinic",
        "phone": "+972-3-555-0909",
        "kind": "clinic",
        "_score": 0.7,
        "geo": {"lat": "not-a-number", "lon": 34.8},
    }

    monkeypatch.setattr(
        places,
        "search_providers",
        lambda *args, **kwargs: [invalid_geo.copy()],
    )

    state = BodyState(
        user_query="clinic",
        user_query_redacted="clinic",
        preferences={},
    )

    ranked_state = places.run(state, es_client=object())

    candidates = ranked_state["candidates"]
    assert len(candidates) == 1
    assert "distance_km" not in candidates[0]
    assert "reason_codes" not in candidates[0]


def test_places_skips_candidates_without_name_or_phone(monkeypatch):
    entries = [
        {"name": None, "phone": "+972-3-000", "_score": 0.5},
        {"name": "Valid", "phone": "", "_score": 0.6},
        {"name": "Kept", "phone": "+972-3-999", "_score": 0.7},
    ]

    monkeypatch.setattr(
        places,
        "search_providers",
        lambda *args, **kwargs: [entry.copy() for entry in entries],
    )

    state = BodyState(user_query="clinic", user_query_redacted="clinic")
    ranked_state = places.run(state, es_client=object())
    candidates = ranked_state["candidates"]
    assert len(candidates) == 1
    assert candidates[0]["name"] == "Kept"


def test_places_filters_all_candidates(monkeypatch):
    far = {
        "name": "FarOnly",
        "phone": "+972-3-444",
        "kind": "clinic",
        "_score": 1.0,
        "geo": {"lat": 33.0, "lon": 35.5},
    }

    monkeypatch.setattr(
        places,
        "search_providers",
        lambda *args, **kwargs: [far.copy()],
    )

    state = BodyState(
        user_query="clinic",
        user_query_redacted="clinic",
        preferences={"max_travel_km": 1},
    )

    ranked_state = places.run(state, es_client=object())
    assert ranked_state["candidates"] == []
