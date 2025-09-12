from app.graph.nodes import health
from unittest.mock import patch, MagicMock
import pytest
from app.graph.state import BodyState
from app.config import settings


@pytest.fixture(autouse=True)
def mock_embed_and_settings():
    # Mock embed for all tests in this module
    health.embed = MagicMock()
    health.embed.return_value = [[0.1] * 384]  # Mock embedding output
    settings.es_public_index = "test_public_index"


def test_health_knn_then_bm25_fallback(sample_docs, monkeypatch):
    hits_func, fever_doc, ibu_warn, warf_inter = sample_docs

    mock_es_instance = MagicMock()
    mock_es_instance.search.side_effect = [
        {"hits": {"hits": []}},  # First call (kNN) returns no hits
        {
            "hits": {"hits": [{"_source": fever_doc}]}
        },  # Directly provide the expected structure
    ]
    # Patch get_es_client to return our mock instance
    monkeypatch.setattr("app.tools.es_client.get_es_client", lambda: mock_es_instance)

    # Force reload the health module to pick up the patched get_es_client
    import importlib
    import app.graph.nodes.health

    importlib.reload(app.graph.nodes.health)
    from app.graph.nodes import (
        health as reloaded_health,
    )  # Use a different name to avoid confusion

    state: BodyState = {"user_query": "I have a fever of 38.5C", "messages": []}
    out = reloaded_health.run(state, None)  # Call the reloaded module's run function
    assert out.get(
        "public_snippets"
    ), "BM25 fallback should supply docs when kNN is empty"
    assert out.get("citations") == ["file://fever.md"]


@patch("app.tools.es_client.get_es_client")
def test_interaction_alert_requires_two_user_meds(
    mock_get_es_client, sample_docs, monkeypatch
):
    hits, fever_doc, ibu_warn, warf_inter = sample_docs

    mock_es_instance = MagicMock()
    mock_es_instance.search.side_effect = [
        hits([ibu_warn, warf_inter]),  # First search (kNN)
        hits([ibu_warn, warf_inter]),  # Second search (BM25, if fallback occurs)
    ]
    mock_get_es_client.return_value = mock_es_instance

    import importlib
    import app.graph.nodes.health

    importlib.reload(app.graph.nodes.health)
    from app.graph.nodes import health as reloaded_health

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
    out = reloaded_health.run(state, None)
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
    # Reset mock for the second run
    mock_es_instance.search.reset_mock()
    mock_es_instance.search.side_effect = [
        hits([ibu_warn, warf_inter]),  # First search (kNN)
        hits([ibu_warn, warf_inter]),  # Second search (BM25, if fallback occurs)
    ]
    out2 = reloaded_health.run(state, None)
    alerts2 = out2.get("alerts", [])
    assert any(
        "Warfarin — interactions" in a for a in alerts2
    ), "Interaction should show when both meds present"


@patch("app.tools.es_client.get_es_client")
def test_health_dedupes_citations_and_alerts(
    mock_get_es_client, sample_docs, monkeypatch
):
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

    mock_es_instance = MagicMock()
    mock_es_instance.search.side_effect = [
        hits([doc1, doc2]),  # First search (kNN)
        hits([doc1, doc2]),  # Second search (BM25, if fallback occurs)
    ]
    mock_get_es_client.return_value = mock_es_instance

    import importlib
    import app.graph.nodes.health

    importlib.reload(app.graph.nodes.health)
    from app.graph.nodes import health as reloaded_health

    state: BodyState = {"user_query": "Ibuprofen", "messages": []}
    out = reloaded_health.run(state, None)

    assert out.get("citations", []) == ["file://ibuprofen.md"]
    assert out.get("alerts", []) == ["Check: Ibuprofen — warnings"]


@patch("app.tools.es_client.get_es_client")
def test_health_knn_search_exception(mock_get_es_client, monkeypatch):
    mock_es_instance = MagicMock()
    mock_es_instance.search.side_effect = Exception("k-NN search failed")
    mock_get_es_client.return_value = mock_es_instance

    import importlib
    import app.graph.nodes.health

    importlib.reload(app.graph.nodes.health)
    from app.graph.nodes import health as reloaded_health

    state: BodyState = {"user_query": "test", "messages": []}
    out = reloaded_health.run(state, None)
    assert not out.get("public_snippets")  # No snippets should be added


@patch("app.tools.es_client.get_es_client")
def test_health_bm25_search_exception(mock_get_es_client, monkeypatch):
    mock_es_instance = MagicMock()
    mock_es_instance.search.side_effect = [
        {"hits": {"hits": []}},  # k-NN returns no hits
        Exception("BM25 search failed"),  # BM25 raises exception
    ]
    mock_get_es_client.return_value = mock_es_instance

    import importlib
    import app.graph.nodes.health

    importlib.reload(app.graph.nodes.health)
    from app.graph.nodes import health as reloaded_health

    state: BodyState = {"user_query": "test", "messages": []}
    out = reloaded_health.run(state, None)
    assert not out.get("public_snippets")  # No snippets should be added


def test_health_default_guidance_message(fake_es, sample_docs):
    hits, _, _, _ = sample_docs
    # Mock ES to return no relevant documents, so no specific alerts/messages are generated
    fake_es.add_handler(lambda i, b: i.endswith("public_medical_kb"), hits([]))
    state: BodyState = {"user_query": "test", "messages": []}
    out = health.run(state, fake_es)
    assert "messages" in out
    assert len(out["messages"]) == 1
    assert (
        "I found guidance and possible warnings. Review the summary and citations."
        in out["messages"][0]["content"]
    )


def test_health_raises_error_if_no_user_query(fake_es):
    state: BodyState = BodyState({"messages": []})  # type: ignore[typeddict-item]
    with pytest.raises(ValueError, match="user_query is required in state"):
        health.run(state, fake_es)


def test_health_with_memory_facts_and_empty_ing(monkeypatch):
    mock_es_instance = MagicMock()
    mock_es_instance.search.return_value = {"hits": {"hits": []}}
    monkeypatch.setattr("app.tools.es_client.get_es_client", lambda: mock_es_instance)

    import importlib
    import app.graph.nodes.health

    importlib.reload(app.graph.nodes.health)
    from app.graph.nodes import health as reloaded_health

    state = BodyState(
        user_query="test query",
        memory_facts=[
            {"name": "", "entity": "medication"},  # Empty name
            {"name": None, "entity": "medication"},  # None name
            {"name": "  ", "entity": "medication"},  # Whitespace name
            {
                "name": "Valid Ing",
                "entity": "medication",
                "normalized": {"ingredient": "valid ing"},
            },
        ],
    )

    result_state = reloaded_health.run(state, None)
    assert "public_snippets" in result_state


def test_health_warning_section(monkeypatch):
    mock_es_instance = MagicMock()
    mock_es_instance.search.return_value = {
        "hits": {
            "hits": [
                {
                    "_source": {
                        "title": "Ibuprofen Warnings",
                        "section": "warnings",
                        "text": "Do not take if you have stomach ulcers.",
                        "source_url": "http://example.com/warnings",
                    }
                }
            ]
        }
    }
    monkeypatch.setattr("app.tools.es_client.get_es_client", lambda: mock_es_instance)

    import importlib
    import app.graph.nodes.health

    importlib.reload(app.graph.nodes.health)
    from app.graph.nodes import health as reloaded_health

    state = BodyState(user_query="test query")

    result_state = reloaded_health.run(state, None)
    assert "Check: Ibuprofen Warnings — warnings" in result_state["alerts"]
    assert "http://example.com/warnings" in result_state["citations"]


def test_health_with_memory_facts_no_medication_entity(monkeypatch):
    mock_es_instance = MagicMock()
    mock_es_instance.search.return_value = {"hits": {"hits": []}}
    monkeypatch.setattr("app.tools.es_client.get_es_client", lambda: mock_es_instance)

    import importlib
    import app.graph.nodes.health

    importlib.reload(app.graph.nodes.health)
    from app.graph.nodes import health as reloaded_health

    state = BodyState(
        user_query="test query",
        memory_facts=[
            {"name": "Doctor Visit", "entity": "appointment"},
            {"name": "Exercise", "entity": "activity"},
        ],
    )
    result_state = reloaded_health.run(state, None)
    assert "public_snippets" in result_state
    assert result_state["alerts"] == []
    assert result_state["citations"] == []
    assert any(
        "I found guidance and possible warnings." in msg["content"]
        for msg in result_state["messages"]
    )


def test_health_messages_not_empty_and_messages_generated(monkeypatch):
    mock_es_instance = MagicMock()
    mock_es_instance.search.return_value = {
        "hits": {
            "hits": [
                {
                    "_source": {
                        "title": "Ibuprofen Warnings",
                        "section": "warnings",
                        "text": "Do not take if you have stomach ulcers.",
                        "source_url": "http://example.com/warnings",
                    }
                }
            ]
        }
    }
    monkeypatch.setattr("app.tools.es_client.get_es_client", lambda: mock_es_instance)

    import importlib
    import app.graph.nodes.health

    importlib.reload(app.graph.nodes.health)
    from app.graph.nodes import health as reloaded_health

    state = BodyState(
        user_query="test query",
        messages=[{"role": "assistant", "content": "Existing message."}],
    )
    result_state = reloaded_health.run(state, None)
    assert len(result_state["messages"]) == 2  # Original message + message from warning
    assert result_state["messages"][0]["content"] == "Existing message."
    assert any(
        "I found guidance and possible warnings." in msg["content"]
        for msg in result_state["messages"]
    )
