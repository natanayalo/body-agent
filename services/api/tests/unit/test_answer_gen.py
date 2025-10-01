import os
import builtins
import sys
import json

import pytest

from app.graph.nodes import answer_gen
from app.graph.state import BodyState
from app.tools import med_facts


def test_answer_gen_skips_when_provider_none(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "none")
    state = BodyState(user_query="Help", messages=[])
    out = answer_gen.run(state)
    assert out.get("messages", []) == []


def test_answer_gen_meds_onset_uses_med_facts(monkeypatch):
    med_facts.clear_cache()
    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    def fail_generate(
        provider: str, prompt: str, language: str
    ):  # pragma: no cover - should not run
        raise AssertionError("LLM provider should not be called for meds onset")

    monkeypatch.setattr(answer_gen, "_generate_with_provider", fail_generate)

    state = BodyState(
        user_query="אקמול מתי משפיע",
        user_query_redacted="אקמול מתי משפיע",
        intent="meds",
        sub_intent="onset",
        language="he",
        debug={"normalized_query_meds": ["acetaminophen"]},
        messages=[],
    )

    out = answer_gen.run(state)
    message = out["messages"][-1]
    content = message["content"]

    assert "אקמול" in content
    assert "מקור" in content or "Source" in content
    assert answer_gen.LANG_CONFIG["he"]["disclaimer"] in content
    citations = out.get("citations", [])
    assert len(citations) == 1
    assert citations[0].startswith("https://")


def test_answer_gen_meds_onset_paraphrases_when_enabled(monkeypatch):
    med_facts.clear_cache()
    monkeypatch.setenv("PARAPHRASE_ONSET", "true")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    def fake_call(prompt: str, language: str):
        assert "JSON" in prompt
        payload = {
            "summary": "אקמול מתחיל להקל לרוב בתוך 30–60 דקות.",
            "follow_up": "עקבו אחר ההרגשה; אם אין שיפור תוך כשעה, פנו לרופא.",
        }
        return json.dumps(payload)

    monkeypatch.setattr(answer_gen, "_call_ollama", fake_call)

    state = BodyState(
        user_query="אקמול מתי משפיע",
        user_query_redacted="אקמול מתי משפיע",
        intent="meds",
        sub_intent="onset",
        language="he",
        debug={"normalized_query_meds": ["acetaminophen"]},
        messages=[],
    )

    out = answer_gen.run(state)
    content = out["messages"][-1]["content"]

    assert "עקבו אחר ההרגשה" in content
    assert "30" in content
    assert "Source: NHS" in content
    assert answer_gen.LANG_CONFIG["he"]["disclaimer"] in content


def test_answer_gen_meds_onset_paraphrase_rejects_new_numbers(monkeypatch):
    med_facts.clear_cache()
    monkeypatch.setenv("PARAPHRASE_ONSET", "true")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    def bad_call(prompt: str, language: str):
        payload = {
            "summary": "אקמול מתחיל לפעול אחרי 45 דקות בדיוק.",
            "follow_up": "אם אין שיפור תוך שעתיים, פנו לרופא.",
        }
        return json.dumps(payload)

    monkeypatch.setattr(answer_gen, "_call_ollama", bad_call)

    state = BodyState(
        user_query="אקמול מתי משפיע",
        user_query_redacted="אקמול מתי משפיע",
        intent="meds",
        sub_intent="onset",
        language="he",
        debug={"normalized_query_meds": ["acetaminophen"]},
        messages=[],
    )

    out = answer_gen.run(state)
    content = out["messages"][-1]["content"]

    # Falls back to canonical wording when validation fails
    assert "45" not in content
    assert "אקמול בדרך כלל" in content


def test_paraphrase_helper_handles_code_fence(monkeypatch):
    monkeypatch.setenv("PARAPHRASE_ONSET", "true")

    def fenced_call(prompt: str, language: str):
        return '```json\n{"summary": "איבופרופן מפחית כאב תוך 20–30 דקות.", "follow_up": ""}\n```'

    monkeypatch.setattr(answer_gen, "_call_ollama", fenced_call)
    fact = {
        "summary": "איבופרופן לרוב מתחיל להקל על כאב או חום תוך 20–30 דקות מהנטילה.",
        "follow_up": "",
    }

    summary, follow_up = answer_gen._paraphrase_onset_fact(fact, "he")
    assert "20" in summary and "30" in summary
    assert follow_up is None


def test_paraphrase_helper_rejects_invalid_json(monkeypatch):
    monkeypatch.setenv("PARAPHRASE_ONSET", "true")

    monkeypatch.setattr(answer_gen, "_call_ollama", lambda prompt, language: "not-json")

    fact = {
        "summary": "אקמול בדרך כלל מתחיל להשפיע תוך 30–60 דקות.",
        "follow_up": "אם אין שיפור תוך כשעה, פנו לרופא.",
    }

    assert answer_gen._paraphrase_onset_fact(fact, "he") is None


def test_paraphrase_helper_blocks_new_numbers_when_none_present(monkeypatch):
    monkeypatch.setenv("PARAPHRASE_ONSET", "true")

    def introduce_number(prompt: str, language: str):
        return json.dumps({"summary": "התרופה פועלת תוך 5 דקות.", "follow_up": ""})

    monkeypatch.setattr(answer_gen, "_call_ollama", introduce_number)

    fact = {"summary": "התרופה פועלת במהירות.", "follow_up": ""}

    assert answer_gen._paraphrase_onset_fact(fact, "he") is None


def test_paraphrase_helper_parses_embedded_json(monkeypatch):
    monkeypatch.setenv("PARAPHRASE_ONSET", "true")

    def embedded(prompt: str, language: str):
        return 'prefix {"summary": "Ibuprofen eases symptoms within 20–30 minutes.", "follow_up": "Follow up if symptoms persist."} suffix'

    monkeypatch.setattr(answer_gen, "_call_ollama", embedded)

    fact = {
        "summary": "Ibuprofen usually begins easing pain or fever within 20–30 minutes after a dose.",
        "follow_up": "If there is no improvement after about an hour or symptoms worsen, speak with a clinician.",
    }

    summary, follow_up = answer_gen._paraphrase_onset_fact(fact, "en")
    assert "20" in summary and "30" in summary
    assert "Follow up" in follow_up


def test_paraphrase_helper_handles_invalid_embedded_json(monkeypatch):
    monkeypatch.setenv("PARAPHRASE_ONSET", "true")

    def invalid(prompt: str, language: str):
        return 'prefix {"summary": } suffix'

    monkeypatch.setattr(answer_gen, "_call_ollama", invalid)

    fact = {
        "summary": "Ibuprofen usually begins easing pain or fever within 20–30 minutes after a dose.",
        "follow_up": "If there is no improvement after about an hour or symptoms worsen, speak with a clinician.",
    }

    assert answer_gen._paraphrase_onset_fact(fact, "en") is None


def test_paraphrase_helper_requires_summary(monkeypatch):
    monkeypatch.setenv("PARAPHRASE_ONSET", "true")

    def fail(prompt: str, language: str):  # pragma: no cover
        raise AssertionError("_call_ollama should not run when summary missing")

    monkeypatch.setattr(answer_gen, "_call_ollama", fail)

    fact = {"summary": "", "follow_up": ""}

    assert answer_gen._paraphrase_onset_fact(fact, "he") is None


def test_paraphrase_helper_returns_none_when_call_fails(monkeypatch):
    monkeypatch.setenv("PARAPHRASE_ONSET", "true")

    monkeypatch.setattr(answer_gen, "_call_ollama", lambda prompt, language: None)

    fact = {
        "summary": "אקמול בדרך כלל מתחיל להשפיע תוך 30–60 דקות.",
        "follow_up": "אם אין שיפור תוך כשעה, פנו לרופא.",
    }

    assert answer_gen._paraphrase_onset_fact(fact, "he") is None


def test_answer_gen_meds_onset_falls_back_to_english(monkeypatch):
    med_facts.clear_cache()
    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    def fail_generate(
        provider: str, prompt: str, language: str
    ):  # pragma: no cover - should not run
        raise AssertionError("LLM provider should not be called for meds onset")

    monkeypatch.setattr(answer_gen, "_generate_with_provider", fail_generate)

    state = BodyState(
        user_query="When will ibuprofen start working?",
        intent="meds",
        sub_intent="onset",
        language="fr",
        debug={"normalized_query_meds": ["ibuprofen"]},
        messages=[],
    )

    out = answer_gen.run(state)
    message = out["messages"][-1]
    content = message["content"]

    assert "Ibuprofen" in content
    assert answer_gen.DISCLAIMER in content
    citations = out.get("citations", [])
    assert len(citations) == 1


def test_answer_gen_meds_onset_uses_memory_fact(monkeypatch):
    med_facts.clear_cache()
    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    def fail_generate(
        provider: str, prompt: str, language: str
    ):  # pragma: no cover - should not run
        raise AssertionError("LLM provider should not be called for meds onset")

    monkeypatch.setattr(answer_gen, "_generate_with_provider", fail_generate)

    state = BodyState(
        user_query="אקמול מתי משפיע",
        user_query_redacted="אקמול מתי משפיע",
        intent="meds",
        sub_intent="onset",
        language="he",
        memory_facts=[
            {
                "entity": "medication",
                "name": "אקמול",
                "normalized": {"ingredient": "ACETAMINOPHEN"},
            }
        ],
        debug={},
        messages=[],
    )

    out = answer_gen.run(state)
    content = out["messages"][-1]["content"]

    assert "אקמול" in content
    assert "אם אין שיפור" in content
    assert "Source: NHS" in content
    assert out["citations"] == [
        "https://www.nhs.uk/medicines/paracetamol-for-adults/about-paracetamol/"
    ]
    assert answer_gen.LANG_CONFIG["he"]["disclaimer"] in content


def test_answer_gen_uses_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    captured = {}

    def fake_generate(provider: str, prompt: str, language: str):
        captured["provider"] = provider
        captured["prompt"] = prompt
        captured["language"] = language
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
    assert captured["language"] == "en"
    assert out["messages"]
    message = out["messages"][-1]
    assert "helpful summary" in message["content"].lower()
    assert answer_gen.DISCLAIMER in message["content"]


def test_answer_gen_fallback_adds_urgent_warning(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    def no_generation(provider: str, prompt: str, language: str):
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
    assert answer_gen._call_ollama("prompt", "en") is None

    # Missing API key means early exit
    assert answer_gen._call_openai("prompt", "en") is None


def test_call_ollama_success(monkeypatch):
    import types

    messages_seen = {}

    system_prompts = []

    def fake_chat(model: str, messages):  # type: ignore[override]
        messages_seen["model"] = model
        messages_seen["messages"] = messages
        if messages:
            system_prompts.append(messages[0]["content"])
        return {"message": {"content": "Generated"}}

    module = types.SimpleNamespace(chat=fake_chat)
    monkeypatch.setitem(sys.modules, "ollama", module)
    monkeypatch.setenv("OLLAMA_MODEL", "mini")

    try:
        content = answer_gen._call_ollama("prompt text", "he")
        assert content == "Generated"
        assert messages_seen["model"] == "mini"
        assert system_prompts == [answer_gen._system_prompt("he")]
    finally:
        sys.modules.pop("ollama", None)


def test_call_openai_success(monkeypatch):
    import types

    captured_messages = {}

    class FakeCompletions:
        def create(self, model, messages):  # type: ignore[override]
            assert model == "gpt-4o-mini"
            captured_messages["messages"] = messages

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
        content = answer_gen._call_openai("Tell me", "he")
        assert content == "OpenAI response"
        assert captured_messages["messages"][0]["content"] == answer_gen._system_prompt(
            "he"
        )
    finally:
        sys.modules.pop("openai", None)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def test_call_openai_handles_empty_choices(monkeypatch):
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
        content = answer_gen._call_openai("Summarise", "en")
        assert content is None
    finally:
        sys.modules.pop("openai", None)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def test_load_templates_unknown_extension_plain(tmp_path):
    path = tmp_path / "templates.txt"
    path.write_text("irrelevant", encoding="utf-8")
    assert answer_gen._load_templates_from_file(str(path)) is None


def test_load_templates_missing_yaml(monkeypatch, tmp_path):
    path = tmp_path / "templates.yaml"
    path.write_text("gi:\n  en: text", encoding="utf-8")

    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "yaml":
            raise ModuleNotFoundError("No module named 'yaml'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    assert answer_gen._load_templates_from_file(str(path)) is None


def test_load_templates_handles_exception(monkeypatch):
    def raise_ioerror(
        *args, **kwargs
    ):  # pragma: no cover - used to trigger except path
        raise IOError("boom")

    monkeypatch.setattr(builtins, "open", raise_ioerror)
    assert answer_gen._load_templates_from_file("/tmp/missing.json") is None


def test_init_templates_map_invalid_file(tmp_path, monkeypatch):
    path = tmp_path / "bad.json"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(answer_gen, "_TEMPLATES_PATH", str(path))
    monkeypatch.setattr(answer_gen, "_TEMPLATES_MAP", {})
    monkeypatch.setattr(answer_gen, "_TEMPLATES_MTIME", None)
    answer_gen._init_templates_map()
    assert answer_gen._TEMPLATES_MAP == {}


def test_init_templates_map_getmtime_failure(tmp_path, monkeypatch):
    path = tmp_path / "ok.json"
    path.write_text('{"general": {"en": "text"}}', encoding="utf-8")
    monkeypatch.setattr(answer_gen, "_TEMPLATES_PATH", str(path))
    monkeypatch.setattr(answer_gen, "_TEMPLATES_MAP", {})

    def fake_getmtime(_):
        raise OSError("boom")

    monkeypatch.setattr(os.path, "getmtime", fake_getmtime)
    answer_gen._init_templates_map()
    assert answer_gen._TEMPLATES_MTIME is None


def test_maybe_reload_templates_watch_true(tmp_path, monkeypatch):
    path = tmp_path / "templates.json"
    path.write_text('{"general": {"en": "text"}}', encoding="utf-8")

    monkeypatch.setattr(answer_gen, "_TEMPLATES_PATH", str(path))
    monkeypatch.setattr(answer_gen, "_TEMPLATES_WATCH", True)
    monkeypatch.setattr(answer_gen, "_TEMPLATES_MAP", {})
    monkeypatch.setattr(answer_gen, "_TEMPLATES_MTIME", 0)

    answer_gen._maybe_reload_templates()
    assert answer_gen._TEMPLATES_MTIME > 0


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

    def no_generation(provider: str, prompt: str, language: str):
        assert provider == "ollama"
        assert language == "he"
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

    def no_generation(provider: str, prompt: str, language: str):
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

    def no_generation(provider: str, prompt: str, language: str):
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

    def no_generation(provider: str, prompt: str, language: str):
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


def test_candidate_ingredients_dedupes_sources():
    state = BodyState(
        user_query="",
        debug={
            "normalized_query_meds": [
                " acetaminophen ",
                "Ibuprofen",
                None,
                "acetaminophen",
            ]
        },
        memory_facts=[
            {"normalized": {"ingredient": "ACETAMINOPHEN"}},
            {"normalized": {"ingredient": "ibuprofen"}},
        ],
    )

    ingredients = answer_gen._candidate_ingredients(state)
    assert ingredients == [" acetaminophen ", "Ibuprofen"]


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


def test_load_templates_unknown_extension_watch(monkeypatch, tmp_path):
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
