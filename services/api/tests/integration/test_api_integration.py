import pytest
from unittest.mock import patch


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_graph_run_end_to_end(client, fake_es, fake_pipe, sample_docs):
    hits, fever_doc, ibu_warn, warf_inter = sample_docs
    # Return warning + interaction docs from public KB
    fake_es.add_handler(
        lambda i, b: i.endswith("public_medical_kb"), hits([ibu_warn, warf_inter])
    )

    # Risk model: urgent care fires
    fake_pipe.run(urgent_care=0.8, see_doctor=0.1, self_care=0.1, info_only=0.0)

    payload = {"user_id": "demo-user", "query": "I have a fever of 39C"}
    r = client.post("/api/graph/run", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["state"]["intent"] in {"symptom", "meds", "appointment", "other"}
    assert isinstance(data["state"].get("public_snippets"), list)
    assert any("ML risk: urgent_care" in a for a in data["state"].get("alerts", []))
    assert "citations" in data["state"]


# @pytest.mark.xfail(reason="Pending logging redaction hook in API logging")
# def test_logs_use_redacted(monkeypatch, client, caplog):
#     # When the app logs user input, it should use redacted version
#     # This test is xfail until logging calls are wired to use state["user_query_redacted"].
#     caplog.set_level("INFO")
#     raw = "email me at user@example.com"
#     payload = {"user_id": "demo-user", "query": raw}
#     client.post("/api/graph/run", json=payload)
#     joined = "\n".join(m.message for m in caplog.records)
#     assert "user@example.com" not in joined
#     assert "[email]" in joined


def test_legacy_run_endpoint(client, fake_es, fake_pipe):
    r = client.post("/api/run", json={"user_id": "test", "query": "hello"})
    assert r.status_code == 200
    assert "state" in r.json()


def test_routes_endpoint(client):
    r = client.get("/__routes")
    assert r.status_code == 200
    paths = r.json()
    assert "/__routes" in paths
    assert "/api/run" in paths


@patch("app.main.embed", return_value=[[0.1, 0.2, 0.3]])
@patch("app.main.get_es_client")
def test_add_med_endpoint(mock_get_es_client, mock_embed, client):
    payload = {"user_id": "test", "name": "Ibuprofen 200mg"}
    r = client.post("/api/memory/add_med", json=payload)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    mock_get_es_client.return_value.index.assert_called_once()
    args, kwargs = mock_get_es_client.return_value.index.call_args
    assert kwargs["document"]["name"] == "Ibuprofen 200mg"


@patch("app.main._invoke_graph", side_effect=Exception("Graph error"))
def test_run_graph_exception(mock_invoke, client):
    with pytest.raises(Exception) as e:
        client.post("/api/graph/run", json={"user_id": "test", "query": "hello"})
    assert "Graph error" in str(e.value)


def test_symptom_flow_with_stub_risk(client, fake_es, fake_pipe, sample_docs):
    hits, fever_doc, _, _ = sample_docs
    fake_es.add_handler(lambda i, b: i.endswith("public_medical_kb"), hits([fever_doc]))

    # Stub the risk model to be non-urgent
    fake_pipe.run(urgent_care=0.1, see_doctor=0.2, self_care=0.8, info_only=0.1)

    payload = {"user_id": "demo-user", "query": "I have a fever"}
    r = client.post("/api/graph/run", json=payload)
    assert r.status_code == 200
    data = r.json()

    # Check intent and basic structure
    assert data["state"]["intent"] == "symptom"
    assert "public_snippets" in data["state"]
    assert "citations" in data["state"]

    # Check alerts - should not have ML risk alerts
    alerts = data["state"].get("alerts", [])
    assert not any("ML risk" in a for a in alerts)


def test_enforce_non_empty_query(client):
    payload = {"user_id": "test-user", "query": ""}
    r = client.post("/api/graph/run", json=payload)
    assert r.status_code == 422
    assert "query" in r.json()["detail"][0]["loc"]
    assert "String should have at least 1 character" in r.json()["detail"][0]["msg"]


def test_e2e_medication_interaction_flow(client, fake_es, sample_docs):
    hits, fever_doc, ibu_warn, warf_inter = sample_docs

    # Configure fake_es to return memory facts and interaction documents
    user_id = "test-user-med-interaction"

    mock_memory_fact_ibuprofen = {
        "user_id": user_id,
        "entity": "medication",
        "name": "Ibuprofen 200mg",
        "normalized": {"ingredient": "ibuprofen"},
    }
    mock_memory_fact_warfarin = {
        "user_id": user_id,
        "entity": "medication",
        "name": "Warfarin 5mg",
        "normalized": {"ingredient": "warfarin"},
    }

    def memory_search_predicate(index, body):
        if index == "private_user_memory":
            term_query = body.get("query", {}).get("term", {})
            if term_query.get("user_id") == user_id:
                return True
        return False

    fake_es.add_handler(
        memory_search_predicate,
        hits([mock_memory_fact_ibuprofen, mock_memory_fact_warfarin]),
    )

    def interaction_search_predicate(index, body):
        if index == "public_medical_kb":
            query_bool = body.get("query", {}).get("bool", {})
            should_clauses = query_bool.get("should", [])

            # Check if any of the should clauses match "title": "ibuprofen" or "title": "warfarin"
            for clause in should_clauses:
                match_title = clause.get("match", {}).get("title")
                if match_title and (
                    match_title == "ibuprofen" or match_title == "warfarin"
                ):
                    return True
            return False

    fake_es.add_handler(interaction_search_predicate, hits([ibu_warn, warf_inter]))

    user_id = "test-user-med-interaction"
    # 1. Add first medication
    add_med_payload_1 = {"user_id": user_id, "name": "Ibuprofen 200mg"}
    response_1 = client.post("/api/memory/add_med", json=add_med_payload_1, timeout=15)
    assert response_1.status_code == 200
    assert response_1.json().get("ok") is True

    # 2. Add second medication
    add_med_payload_2 = {"user_id": user_id, "name": "Warfarin 5mg"}
    response_2 = client.post("/api/memory/add_med", json=add_med_payload_2, timeout=15)
    assert response_2.status_code == 200
    assert response_2.json().get("ok") is True

    # 3. Query about a health issue that might trigger an interaction alert
    query_payload = {
        "user_id": user_id,
        "query": "What are the interactions between Ibuprofen and Warfarin?",
    }
    response_3 = client.post("/api/graph/run", json=query_payload, timeout=15)
    assert response_3.status_code == 200
    data = response_3.json()

    # 4. Verify that an interaction alert is present
    alerts = data["state"].get("alerts", [])
    assert any("Warfarin — interactions" in a for a in alerts) or any(
        "Ibuprofen — warnings" in a for a in alerts
    ), f"Expected interaction alert, but got: {alerts}"

    # 5. Verify citations are present and normalized
    citations = data["state"].get("citations", [])
    assert len(citations) > 0
    assert all(c.startswith("http") or c.startswith("file") for c in citations)
    # Check for deduplication and normalization (e.g., no utm_ params, consistent slashes)
    # This is a basic check, more robust checks would involve parsing URLs
    assert len(set(citations)) == len(citations), "Citations should be deduplicated"
