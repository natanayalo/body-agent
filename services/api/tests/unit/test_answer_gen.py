import pytest

from app.graph.nodes import answer_gen
from app.graph.state import BodyState


def test_answer_gen_skips_when_provider_none(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "none")
    state = BodyState(user_query="Help", messages=[])
    out = answer_gen.run(state)
    assert out.get("messages", []) == []


def test_answer_gen_uses_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    captured = {}

    def fake_generate(provider: str, prompt: str):
        captured["provider"] = provider
        captured["prompt"] = prompt
        return "Here is a helpful summary with citations [1]."

    monkeypatch.setattr(answer_gen, "_generate_with_provider", fake_generate)

    state = BodyState(
        user_query="I have a fever",
        public_snippets=[
            {"title": "Fever Care", "section": "general", "text": "Rest."}
        ],
    )
    out = answer_gen.run(state)

    assert captured["provider"] == "ollama"
    assert out["messages"]
    message = out["messages"][-1]
    assert "helpful summary" in message["content"].lower()
    assert answer_gen.DISCLAIMER in message["content"]


def test_answer_gen_fallback_adds_urgent_warning(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    def no_generation(provider: str, prompt: str):
        return None

    monkeypatch.setattr(answer_gen, "_generate_with_provider", no_generation)

    state = BodyState(
        user_query="Chest pain",
        public_snippets=[
            {"title": "Chest Pain", "section": "warning", "text": "Seek care."}
        ],
        citations=["file://chest.md"],
        debug={
            "risk": {
                "triggered": [
                    {"label": "urgent_care", "score": 0.9},
                ]
            }
        },
    )

    out = answer_gen.run(state)
    message = out["messages"][-1]
    assert "risk notice" in message["content"].lower()
    assert answer_gen.URGENT_LINE in message["content"]
    assert message["citations"] == ["file://chest.md"]


def test_generate_with_unknown_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "unknown")

    state = BodyState(user_query="Ping", messages=[], citations=[])
    out = answer_gen.run(state)
    message = out["messages"][-1]
    lower = message["content"].lower()
    # Allow either generic recap or pattern-based template fallback
    assert ("summary for" in lower) or ("recap" in lower) or ("self-care" in lower)
    assert answer_gen.DISCLAIMER in message["content"]


def test_call_helpers_handle_missing_backends():
    # No ollama module installed
    assert answer_gen._call_ollama("prompt") is None

    # Missing API key means early exit
    assert answer_gen._call_openai("prompt") is None


def test_call_ollama_success(monkeypatch):
    import sys
    import types

    messages_seen = {}

    def fake_chat(model: str, messages):  # type: ignore[override]
        messages_seen["model"] = model
        messages_seen["messages"] = messages
        return {"message": {"content": "Generated"}}

    module = types.SimpleNamespace(chat=fake_chat)
    monkeypatch.setitem(sys.modules, "ollama", module)
    monkeypatch.setenv("OLLAMA_MODEL", "mini")

    try:
        content = answer_gen._call_ollama("prompt text")
        assert content == "Generated"
        assert messages_seen["model"] == "mini"
    finally:
        sys.modules.pop("ollama", None)


def test_call_openai_success(monkeypatch):
    import sys
    import types

    class FakeCompletions:
        def create(self, model, messages):  # type: ignore[override]
            assert model == "gpt-4o-mini"

            class Choice:
                message = types.SimpleNamespace(content="OpenAI response")

            return types.SimpleNamespace(choices=[Choice()])

    class FakeClient:
        def __init__(self, api_key):
            assert api_key == "secret"
            self.chat = types.SimpleNamespace(completions=FakeCompletions())

    module = types.SimpleNamespace(OpenAI=FakeClient)
    monkeypatch.setitem(sys.modules, "openai", module)
    monkeypatch.setenv("OPENAI_API_KEY", "secret")

    try:
        content = answer_gen._call_openai("Tell me")
        assert content == "OpenAI response"
    finally:
        sys.modules.pop("openai", None)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def test_call_openai_handles_empty_choices(monkeypatch):
    import sys
    import types

    class FakeCompletions:
        def create(self, model, messages):  # type: ignore[override]
            assert model == "gpt-4o-mini"
            return types.SimpleNamespace(choices=[])

    class FakeClient:
        def __init__(self, api_key):
            assert api_key == "secret"
            self.chat = types.SimpleNamespace(completions=FakeCompletions())

    module = types.SimpleNamespace(OpenAI=FakeClient)
    monkeypatch.setitem(sys.modules, "openai", module)
    monkeypatch.setenv("OPENAI_API_KEY", "secret")

    try:
        content = answer_gen._call_openai("Summarise")
        assert content is None
    finally:
        sys.modules.pop("openai", None)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def test_fallback_highlights_include_ellipsis_when_truncated():
    long_text = "A" * (answer_gen.FALLBACK_HIGHLIGHT_LENGTH + 20)
    state = BodyState(
        public_snippets=[{"title": "Long Guidance", "text": long_text}],
    )

    fallback = answer_gen._fallback_message(state)
    assert "Long Guidance" in fallback
    assert "..." in fallback


def test_answer_gen_hebrew_fallback(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    def no_generation(provider: str, prompt: str):
        assert provider == "ollama"
        return None

    monkeypatch.setattr(answer_gen, "_generate_with_provider", no_generation)

    state = BodyState(
        user_query="יש לי חום",
        user_query_redacted="יש לי חום",
        public_snippets=[
            {
                "title": "חום גבוה",
                "section": "כללי",
                "text": "מומלץ לנוח ולשתות הרבה מים",
                "language": "he",
            }
        ],
        messages=[],
        language="he",
    )

    out = answer_gen.run(state)
    message = out["messages"][-1]
    assert answer_gen.LANG_CONFIG["he"]["disclaimer"] in message["content"]
    assert "נקודות עיקריות" in message["content"]


def test_answer_gen_hebrew_fallback_uses_english_when_needed(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    def no_generation(provider: str, prompt: str):
        return None

    monkeypatch.setattr(answer_gen, "_generate_with_provider", no_generation)

    state = BodyState(
        user_query="חיפוש",
        public_snippets=[
            {
                "title": "Fever Home Care",
                "section": "general",
                "text": "Hydrate well; rest; light clothing.",
                "language": "en",
            }
        ],
        messages=[],
        language="he",
    )

    out = answer_gen.run(state)
    message = out["messages"][-1]["content"]
    assert "נקודות עיקריות" in message
    assert "Fever Home Care" in message


def test_pattern_fallback_gi_when_no_snippets(monkeypatch):
    # Force provider to return None so fallback path is taken
    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    def no_generation(provider: str, prompt: str):
        return None

    monkeypatch.setattr(answer_gen, "_generate_with_provider", no_generation)

    state = BodyState(
        user_query="What can I take to relieve stomach pain?",
        public_snippets=[],
        messages=[],
        language="en",
        debug={"risk": {"triggered": [{"label": "monitor_symptoms", "score": 0.4}]}},
    )

    out = answer_gen.run(state)
    msg = out["messages"][-1]["content"]
    assert "stomach" in msg.lower() or "self-care" in msg.lower()
    assert answer_gen.DISCLAIMER in msg
    # No dosing information should appear in templates
    assert " mg" not in msg.lower()
    assert answer_gen.LANG_CONFIG["en"]["fallback_risk_label"] in msg
    assert "monitor_symptoms" in msg


def test_pattern_fallback_hebrew_gi_when_no_snippets(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")

    def no_generation(provider: str, prompt: str):
        return None

    monkeypatch.setattr(answer_gen, "_generate_with_provider", no_generation)

    state = BodyState(
        user_query="מה אפשר לקחת לכאבי בטן?",
        user_query_redacted="מה אפשר לקחת לכאבי בטן?",
        public_snippets=[],
        messages=[],
        language="he",
    )
    out = answer_gen.run(state)
    msg = out["messages"][-1]["content"]
    assert "בטן" in msg
    assert answer_gen.LANG_CONFIG["he"]["disclaimer"] in msg


def test_bucketize_symptom_variants_en():
    assert answer_gen._bucketize_symptom("Stomach cramps and nausea", "en") == "gi"
    assert answer_gen._bucketize_symptom("Bad cough and sore throat", "en") == "resp"
    assert answer_gen._bucketize_symptom("Headache with dizziness", "en") == "neuro"
    assert answer_gen._bucketize_symptom("Random text", "en") == "general"


def test_bucketize_symptom_variants_he():
    assert answer_gen._bucketize_symptom("כאבי בטן חזקים", "he") == "gi"
    assert answer_gen._bucketize_symptom("שיעול וליחה", "he") == "resp"
    assert answer_gen._bucketize_symptom("כאב ראש וסחרחורת", "he") == "neuro"
    assert answer_gen._bucketize_symptom("טקסט כללי", "he") == "general"


def test_template_fallback_general_when_unknown_lang(monkeypatch):
    state = BodyState(user_query="zzz", language="xx")
    # Force language config to default; template should still return a string
    content = answer_gen._template_fallback(state)
    assert isinstance(content, str)
    assert content


def test_load_templates_from_file(monkeypatch, tmp_path):
    # Prepare a minimal JSON templates file overriding GI EN bucket
    p = tmp_path / "safety_templates.json"
    p.write_text(
        '{"gi": {"en": "FILE GI TEMPLATE", "he": "תבנית GI"}}', encoding="utf-8"
    )

    # Point the module to the file and enable watch, then trigger reload
    monkeypatch.setattr(answer_gen, "_TEMPLATES_PATH", str(p))
    monkeypatch.setattr(answer_gen, "_TEMPLATES_WATCH", True)
    # Ensure reload occurs
    answer_gen._maybe_reload_templates()

    state = BodyState(user_query="stomach pain", language="en")
    content = answer_gen._template_fallback(state)
    assert "FILE GI TEMPLATE" in content


def test_load_templates_unknown_extension(monkeypatch, tmp_path):
    p = tmp_path / "safety_templates.txt"
    p.write_text('{"gi": {"en": "X"}}', encoding="utf-8")
    assert answer_gen._load_templates_from_file(str(p)) is None


def test_init_templates_map_with_missing_and_invalid(monkeypatch, tmp_path):
    # Missing path → keep defaults
    monkeypatch.setattr(answer_gen, "_TEMPLATES_PATH", None)
    answer_gen._init_templates_map()

    # Invalid (empty parsed) content → warn and keep defaults
    p = tmp_path / "safety_templates.json"
    p.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(answer_gen, "_TEMPLATES_PATH", str(p))
    answer_gen._init_templates_map()


def test_maybe_reload_templates_handles_flags(monkeypatch, tmp_path):
    # Watch disabled → no-op
    monkeypatch.setattr(answer_gen, "_TEMPLATES_WATCH", False)
    answer_gen._maybe_reload_templates()


def test_build_prompt_includes_memory_and_triggers():
    state = BodyState(
        user_query="Test",
        public_snippets=[{"title": "X", "text": "Short"}],
        memory_facts=[{"entity": "allergy", "name": "penicillin"}],
        debug={"risk": {"triggered": [{"label": "see_doctor", "score": 0.6}]}},
    )
    prompt = answer_gen._build_prompt(state)
    assert "Relevant personal context" in prompt or "הקשר אישי" in prompt
    assert "allergy" in prompt
    assert "see_doctor" in prompt


def test_init_templates_map_loads_valid_json(monkeypatch, tmp_path):
    p = tmp_path / "safety_templates.json"
    p.write_text('{"general": {"en": "GEN", "he": "כללי"}}', encoding="utf-8")
    monkeypatch.setattr(answer_gen, "_TEMPLATES_PATH", str(p))
    answer_gen._init_templates_map()
    state = BodyState(user_query="zzz", language="en")
    content = answer_gen._template_fallback(state)
    assert content.startswith("GEN")


def test_load_yaml_templates(monkeypatch, tmp_path):
    pytest.importorskip("yaml")
    p = tmp_path / "safety_templates.yaml"
    p.write_text("gi:\n  en: GI from YAML\n", encoding="utf-8")
    out = answer_gen._load_templates_from_file(str(p))
    assert out is not None
    assert out.get("gi", {}).get("en") == "GI from YAML"


def test_parse_templates_obj_variants():
    # Non-dict input returns empty
    assert answer_gen._parse_templates_obj([1, 2, 3]) == {}
    # Dict with non-dict bucket value is skipped
    assert answer_gen._parse_templates_obj({"gi": "text"}) == {}
    # Dict with non-string value is skipped
    assert answer_gen._parse_templates_obj({"gi": {"en": 123}}) == {}
    # Valid map passes through
    out = answer_gen._parse_templates_obj({"gi": {"en": "X"}})
    assert out == {"gi": {"en": "X"}}


def test_fallback_message_empty_when_no_data():
    state = BodyState(user_query="", public_snippets=[], messages=[])
    msg = answer_gen._fallback_message(state)
    # Should return the language-specific empty recap string
    assert isinstance(msg, str) and len(msg) > 0
