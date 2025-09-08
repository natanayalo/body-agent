from app.graph.nodes import health


def test_health_knn_then_bm25_fallback(fake_es, sample_docs):
    hits, fever_doc, ibu_warn, warf_inter = sample_docs

    # First call (kNN) returns no hits; second (BM25) returns fever doc
    def pred_knn(idx, body):
        return idx.endswith("public_medical_kb") and "knn" in body

    def pred_bm25(idx, body):
        return idx.endswith("public_medical_kb") and "query" in body

    fake_es.add_handler(pred_knn, {"hits": {"hits": []}})
    fake_es.add_handler(pred_bm25, hits([fever_doc]))

    state = {"user_query": "I have a fever of 38.5C", "messages": []}
    out = health.run(state)
    assert out["public_snippets"], "BM25 fallback should supply docs when kNN is empty"
    assert out["citations"] == ["file://fever.md"]


def test_interaction_alert_requires_two_user_meds(fake_es, sample_docs):
    hits, fever_doc, ibu_warn, warf_inter = sample_docs
    # Always return both warning and interaction docs
    fake_es.add_handler(
        lambda i, b: i.endswith("public_medical_kb"), hits([ibu_warn, warf_inter])
    )

    # Case 1: only ibuprofen in memory → NO interaction alert
    state = {
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
