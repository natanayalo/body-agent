from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from app.graph.state import BodyState

HERE = Path(__file__).parent
INPUTS = HERE / "inputs.jsonl"

with INPUTS.open("r", encoding="utf-8") as fh:
    _CASES: List[Dict[str, Any]] = [json.loads(line) for line in fh if line.strip()]


def _provider_hits(providers: List[Dict[str, Any]]) -> Dict[str, Any]:
    hits = []
    for provider in providers:
        doc = provider.copy()
        score = doc.pop("_score", 1.0)
        hits.append({"_source": doc, "_score": score})
    return {"hits": {"hits": hits}}


def _preferences_hits(user_id: str, prefs: List[Dict[str, Any]]) -> Dict[str, Any]:
    docs = []
    for pref in prefs:
        docs.append(
            {
                "_source": {
                    "user_id": user_id,
                    "entity": "preference",
                    "name": pref["name"],
                    "value": pref.get("value", ""),
                }
            }
        )
    return {"hits": {"hits": docs}}


@pytest.mark.parametrize("case", _CASES, ids=lambda c: c["id"])
def test_golden_cases(
    case: Dict[str, Any],
    client: TestClient,
    fake_es,
    fake_pipe,
    sample_docs,
):
    # Reset handlers for isolated expectations
    fake_es.handlers = []
    hits_fn, fever_doc, ibu_warn, warf_inter, abdomen_doc = sample_docs
    doc_lookup = {
        "fever_doc": fever_doc,
        "ibu_warn": ibu_warn,
        "warf_inter": warf_inter,
    }

    public_docs = [
        doc_lookup[name] for name in case.get("public_docs", []) if name in doc_lookup
    ]

    if public_docs:

        def _public_pred(index: str, body: Dict[str, Any]) -> bool:
            return index.endswith("public_medical_kb")

        fake_es.add_handler(_public_pred, hits_fn(public_docs))

    providers = case.get("providers")
    if providers:

        def _providers_pred(index: str, body: Dict[str, Any]) -> bool:
            return index.endswith("providers_places")

        fake_es.add_handler(_providers_pred, _provider_hits(providers))

    preferences = case.get("preferences", [])
    user_id = case.get("user_id", "golden-user")
    if preferences:

        def _prefs_pred(index: str, body: Dict[str, Any]) -> bool:
            if not index.endswith("private_user_memory"):
                return False
            term = body.get("query", {}).get("term")
            if term and term.get("user_id") == user_id:
                return True
            knn = body.get("knn", {})
            filt_term = knn.get("filter", {}).get("term", {})
            return filt_term.get("user_id") == user_id

        fake_es.add_handler(_prefs_pred, _preferences_hits(user_id, preferences))

    risk_scores = case.get("risk_scores")
    if risk_scores:
        fake_pipe.run(**risk_scores)
    else:
        fake_pipe.run()

    payload = {"user_id": user_id, "query": case["query"]}
    response = client.post("/api/graph/run", json=payload)
    assert response.status_code == 200
    state: BodyState = response.json()["state"]

    assert state.get("intent") == case["expected_intent"]

    citations = state.get("citations", [])
    assert len(citations) >= case.get("min_citations", 0)
    assert len(citations) == len(set(citations))

    if case.get("expect_alert"):
        alerts = state.get("alerts", [])
        assert any(case["alert_contains"] in alert for alert in alerts)
    else:
        assert not state.get("alerts")

    plan_expect = case.get("expected_plan")
    if plan_expect:
        plan = state.get("plan", {})
        assert plan.get("type") == plan_expect.get("type")
        if "provider_kind" in plan_expect:
            provider = plan.get("provider", {})
            assert provider.get("kind") == plan_expect["provider_kind"]
        if "reasons_contains" in plan_expect:
            reasons_text = (
                " ".join(plan.get("explanations", [])) + " " + plan.get("reasons", "")
            )
            for snippet in plan_expect["reasons_contains"]:
                assert snippet in reasons_text
        if "rationale_contains" in plan_expect:
            rationale = plan.get("rationale", "")
            for snippet in plan_expect["rationale_contains"]:
                assert snippet in rationale
