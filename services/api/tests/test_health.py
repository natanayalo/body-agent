from app.graph.nodes import health
from unittest.mock import patch
import pytest
from app.graph.state import BodyState


def test_health_knn_then_bm25_fallback(fake_es, sample_docs):
    hits, fever_doc, ibu_warn, warf_inter = sample_docs

    # First call (kNN) returns no hits; second (BM25) returns fever doc
    def pred_knn(idx, body):
        return idx.endswith("public_medical_kb") and "knn" in body

    def pred_bm25(idx, body):
        return idx.endswith("public_medical_kb") and "query" in body

    fake_es.add_handler(pred_knn, {"hits": {"hits": []}})
    fake_es.add_handler(pred_bm25, hits([fever_doc]))

    state: BodyState = {"user_query": "I have a fever of 38.5C", "messages": []}
    out = health.run(state)
    assert out.get(
        "public_snippets"
    ), "BM25 fallback should supply docs when kNN is empty"
    assert out.get("citations") == ["file://fever.md"]


def test_interaction_alert_requires_two_user_meds(fake_es, sample_docs):
    hits, fever_doc, ibu_warn, warf_inter = sample_docs
    # Always return both warning and interaction docs
    fake_es.add_handler(
        lambda i, b: i.endswith("public_medical_kb"), hits([ibu_warn, warf_inter])
    )

    # Case 1: only ibuprofen in memory → NO interaction alert
    state: BodyState = {
        "user_query": "Can I take something for fever?",
        "messages": [],
        "memory_facts": [
            {
                "entity": "medication",
                "name": "Ibuprofen 200mg",
                "normalized": {"ingredient": "ibuprofen"},
            },
        ],
    }
    out = health.run(state)
    alerts = out.get("alerts", [])
    assert any("Ibuprofen — warnings" in a for a in alerts)
    assert not any(
        "Warfarin — interactions" in a for a in alerts
    ), "Should not show interaction without both meds"

    # Case 2: ibuprofen + warfarin in memory → interaction alert appears
    state["memory_facts"].append(
        {
            "entity": "medication",
            "name": "Warfarin 5mg",
            "normalized": {"ingredient": "warfarin"},
        }
    )
    out2 = health.run(state)
    alerts2 = out2.get("alerts", [])
    assert any(
        "Warfarin — interactions" in a for a in alerts2
    ), "Interaction should show when both meds present"


def test_health_dedupes_citations_and_alerts(fake_es, sample_docs):
    hits, _, _, _ = sample_docs
    doc1 = {
        "title": "Ibuprofen",
        "section": "warnings",
        "source_url": "file://ibuprofen.md",
        "text": "Do not combine with warfarin",
    }
    doc2 = {
        "title": "Ibuprofen",
        "section": "warnings",
        "source_url": "file://ibuprofen.md",
        "text": "Do not combine with warfarin",
    }
    fake_es.add_handler(
        lambda i, b: i.endswith("public_medical_kb"), hits([doc1, doc2])
    )

    state: BodyState = {"user_query": "Ibuprofen", "messages": []}
    out = health.run(state)

    assert out.get("citations", []) == ["file://ibuprofen.md"]
    assert out.get("alerts", []) == ["Check: Ibuprofen — warnings"]


@patch("app.graph.nodes.health.es")
def test_health_knn_search_exception(mock_es):
    mock_es.search.side_effect = Exception("k-NN search failed")
    state: BodyState = {"user_query": "test", "messages": []}
    out = health.run(state)
    assert not out.get("public_snippets")  # No snippets should be added


@patch("app.graph.nodes.health.es")
def test_health_bm25_search_exception(mock_es):
    # Mock k-NN to return no hits, then BM25 to raise exception
    mock_es.search.side_effect = [
        {"hits": {"hits": []}},  # k-NN returns no hits
        Exception("BM25 search failed"),  # BM25 raises exception
    ]
    state: BodyState = {"user_query": "test", "messages": []}
    out = health.run(state)
    assert not out.get("public_snippets")  # No snippets should be added


def test_health_default_guidance_message(fake_es, sample_docs):
    hits, _, _, _ = sample_docs
    # Mock ES to return no relevant documents, so no specific alerts/messages are generated
    fake_es.add_handler(lambda i, b: i.endswith("public_medical_kb"), hits([]))
    state: BodyState = {"user_query": "test", "messages": []}
    out = health.run(state)
    assert "messages" in out
    assert len(out["messages"]) == 1
    assert (
        "I found guidance and possible warnings. Review the summary and citations."
        in out["messages"][0]["content"]
    )


def test_health_raises_error_if_no_user_query():
    state: BodyState = {"messages": []}  # Missing user_query
    with pytest.raises(ValueError, match="user_query is required in state"):
        health.run(state)
