from app.graph.nodes import health
from unittest.mock import patch, MagicMock
import pytest
from app.graph.state import BodyState
from app.config import settings
from elasticsearch import TransportError


@pytest.fixture(autouse=True)
def mock_embed_and_settings():
    # Mock embed for all tests in this module
    health.embed = MagicMock()
    health.embed.return_value = [[0.1] * 384]  # Mock embedding output
    settings.es_public_index = "test_public_index"


def test_health_knn_then_bm25_fallback(sample_docs, monkeypatch):
    hits_func, fever_doc, ibu_warn, warf_inter, abdomen_doc = sample_docs

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

    # Ensure settings.embeddings_model is not "__stub__" for this test
    monkeypatch.setattr(settings, "embeddings_model", "test_model")

    # Force reload the health module to pick up the patched get_es_client
    import importlib
    import app.graph.nodes.health

    importlib.reload(app.graph.nodes.health)

    state: BodyState = {"user_query": "I have a fever of 38.5C", "messages": []}
    out = reloaded_health.run(state)
    assert out.get(
        "public_snippets"
    ), "BM25 fallback should supply docs when kNN is empty"
    assert out.get("citations") == ["file://fever.md"]

    # Second search call corresponds to BM25 body
    assert mock_es_instance.search.call_count == 2
    bm25_call = mock_es_instance.search.call_args_list[1]
    bm25_body = bm25_call.kwargs["body"]
    should = bm25_body["query"]["bool"]["should"]
    assert any(
        clause.get("match", {}).get("text", {}).get("query")
        == "I have a fever of 38.5C"
        for clause in should
        if isinstance(clause, dict)
    )


def test_interaction_alert_requires_two_user_meds(sample_docs, monkeypatch, fake_es):
    hits, fever_doc, ibu_warn, warf_inter, abdomen_doc = sample_docs

    def handler(index, body):
        if index == "test_public_index":
            should = body.get("query", {}).get("bool", {}).get("should", [])
            search_terms: list[str] = []
            for clause in should:
                match = clause.get("match", {})
                for payload in match.values():
                    if isinstance(payload, dict):
                        term = payload.get("query")
                        if isinstance(term, str):
                            search_terms.append(term)
                    elif isinstance(payload, str):
                        search_terms.append(payload)

            if "ibuprofen" in search_terms and "warfarin" not in search_terms:
                return True
        return False

    fake_es.add_handler(handler, hits([ibu_warn]))
    monkeypatch.setattr("app.graph.nodes.health.get_es_client", lambda: fake_es)

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


@patch("app.tools.es_client.get_es_client")
def test_health_dedupes_citations_and_alerts(
    mock_get_es_client, sample_docs, monkeypatch
):
    hits, _, _, _, _ = sample_docs
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
    out = reloaded_health.run(state)

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
    out = reloaded_health.run(state)
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
    out = reloaded_health.run(state)
    assert not out.get("public_snippets")  # No snippets should be added


def test_health_default_guidance_message(fake_es, sample_docs):
    hits, _, _, _, _ = sample_docs
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


def test_health_raises_error_if_no_user_query(fake_es):
    state: BodyState = BodyState({"messages": []})  # type: ignore[typeddict-item]
    with pytest.raises(KeyError):
        health.run(state)


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

    result_state = reloaded_health.run(state)
    assert "public_snippets" in result_state


def test_health_expands_hebrew_symptom_and_boosts_sections(fake_es, sample_docs):
    hits, _, _, _, abdomen_doc = sample_docs

    def registry_predicate(index, body):
        must = body.get("query", {}).get("bool", {}).get("must", [])
        return any(
            clause.get("match_phrase", {}).get("title") == "Abdominal Pain Home Care"
            for clause in must
        )

    fake_es.add_handler(registry_predicate, hits([abdomen_doc]))
    fake_es.add_handler(lambda index, body: "knn" in body, {"hits": {"hits": []}})

    hebrew_doc = {
        "title": "טיפול בכאב בטן",
        "section": "general",
        "language": "he",
        "jurisdiction": "israel",
        "source_url": "file://abdominal_pain.md",
        "updated_on": "2025-01-01T00:00:00Z",
        "text": "התחל בלגימות קטנות של נוזלים צלולים ואכול מזון קל לעיכול.",
    }

    def bm25_predicate(index, body):
        if index != settings.es_public_index:
            return False
        query = body.get("query", {})
        bool_clause = query.get("bool", {}) if isinstance(query, dict) else {}
        return bool_clause.get("should") is not None

    fake_es.add_handler(bm25_predicate, hits([hebrew_doc]))

    state = BodyState(
        user_query="כאבי בטן חזקים בערב",
        user_query_redacted="כאבי בטן חזקים בערב",
        messages=[],
        language="he",
    )

    out = health.run(state, es_client=fake_es)

    assert out["public_snippets"], "Expect registry doc injection"

    titles = [doc["title"] for doc in out["public_snippets"]]
    assert "טיפול בכאב בטן" in titles
    assert "Abdominal Pain Home Care" in titles
    assert out["public_snippets"][0]["language"] == "he"

    bm25_calls = [
        call
        for call in fake_es.calls
        if isinstance(call, tuple)
        and len(call) >= 2
        and call[0] == settings.es_public_index
        and isinstance(call[1], dict)
        and "query" in call[1]
        and "bool" in call[1]["query"]
    ]
    assert bm25_calls, "Expected BM25 search call"
    bm25_body = bm25_calls[-1][1]
    should = bm25_body["query"]["bool"]["should"]

    assert any(
        clause.get("match", {}).get("title", {}).get("query") == "abdominal pain"
        for clause in should
    ), "Expected abdominal pain expansion in BM25 clauses"
    assert any(
        clause.get("match", {}).get("section", {}).get("query") == "general"
        and clause.get("match", {}).get("section", {}).get("boost") == 1.5
        for clause in should
    ), "Expected general section boost"

    assert any(
        call[0] == "msearch" for call in fake_es.calls
    ), "Registry lookup should use msearch"


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

    result_state = reloaded_health.run(state)
    assert "Check: Ibuprofen Warnings — warnings" in result_state.get("alerts", [])
    assert "http://example.com/warnings" in result_state.get("citations", [])


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
    result_state = reloaded_health.run(state)
    assert "public_snippets" in result_state
    assert result_state.get("alerts", []) == []
    assert result_state.get("citations", []) == []
    assert any(
        "I found guidance and possible warnings." in msg["content"]
        for msg in result_state.get("messages", [])
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
    result_state = reloaded_health.run(state)
    assert (
        len(result_state.get("messages", [])) == 2
    )  # Original message + message from warning
    assert result_state.get("messages", [])[0]["content"] == "Existing message."
    assert any(
        "I found guidance and possible warnings." in msg["content"]
        for msg in result_state.get("messages", [])
    )


def test_prioritize_language_moves_preferred_docs_first():
    docs = [
        {"title": "English Guidance", "language": "en"},
        {"title": "הנחיות בעברית", "language": "he"},
        {"title": "Second English", "language": "en"},
    ]

    ordered = health._prioritize_language(docs, "he")
    assert ordered[0]["title"] == "הנחיות בעברית"
    assert {doc["title"] for doc in ordered[1:]} == {
        "English Guidance",
        "Second English",
    }


def test_norm_med_terms_extracts_from_name_only():
    mem = [
        {"entity": "medication", "name": "Optalgin 500mg"},
        {"entity": "medication", "normalized": {"ingredient": "dipyrone"}},
    ]
    assert health._norm_med_terms(mem) == ["optalgin", "dipyrone"]


def test_doc_identity_without_source_url():
    doc = {"title": "Optalgin", "section": "general", "language": "he"}
    identity = health._doc_identity(doc)
    assert identity.startswith("title::Optalgin::general")


def test_merge_docs_skips_duplicate_identity():
    doc = {"title": "Doc", "section": "general", "language": "en"}
    merged = health._merge_docs([doc], [doc])
    assert merged == [doc]


def test_fetch_registry_docs_handles_transport_error():
    es = MagicMock()
    es.msearch.side_effect = TransportError(500, "boom")
    docs = health._fetch_registry_docs(es, [{"source_url": "http://example.com"}])
    assert docs == []


def test_fetch_registry_docs_ignores_non_dict_refs():
    es = MagicMock()
    docs = health._fetch_registry_docs(es, ["bad_ref", None])
    assert docs == []
