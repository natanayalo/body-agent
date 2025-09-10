import pytest
from unittest.mock import patch
from app.tools.es_client import ensure_indices
from app.tools.embeddings import embed


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
@patch("app.main.es")
def test_add_med_endpoint(mock_es, mock_embed, client):
    payload = {"user_id": "test", "name": "Ibuprofen 200mg"}
    r = client.post("/api/memory/add_med", json=payload)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    mock_es.index.assert_called_once()
    args, kwargs = mock_es.index.call_args
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


@patch("app.tools.es_client.es")
def test_ensure_indices_creates_missing(mock_es):
    mock_es.indices.exists.side_effect = [
        False,
        False,
        False,
    ]  # All indices don't exist
    mock_es.indices.create.reset_mock()  # Reset call count
    ensure_indices()
    assert mock_es.indices.create.call_count == 3  # Should create all three


@patch("app.tools.es_client.es")
def test_ensure_indices_does_not_create_existing(mock_es):
    mock_es.indices.exists.side_effect = [True, True, True]  # All indices exist
    mock_es.indices.create.reset_mock()  # Reset call count
    ensure_indices()
    assert mock_es.indices.create.call_count == 0  # Should not create any


def test_embed_single_string():
    text = "hello world"
    result = embed(text)
    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], list)
