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
    assert "summary for" in lower or "recap" in lower
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
