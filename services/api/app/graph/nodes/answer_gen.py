from __future__ import annotations

import logging
import os
from typing import List

from app.config import settings
from app.graph.state import BodyState

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "**Disclaimer:** This assistant does not replace professional medical advice."
)
URGENT_LINE = "If you develop concerning or worsening symptoms, seek urgent evaluation."
FALLBACK_HIGHLIGHT_LENGTH = 160
URGENT_TRIGGERS = {"urgent_care", "see_doctor"}


def _resolve_provider() -> str:
    return os.getenv("LLM_PROVIDER", settings.llm_provider).strip().lower()


def _should_skip(state: BodyState) -> bool:
    provider = _resolve_provider()
    return provider in {"", "none", "disabled"}


def _risk_triggers(state: BodyState) -> List[str]:
    debug = state.get("debug") or {}
    risk = debug.get("risk") or {}
    return [t.get("label") for t in risk.get("triggered", []) if t.get("label")]


def _build_prompt(state: BodyState) -> str:
    user_query = state.get("user_query_redacted", state.get("user_query", ""))
    snippets = state.get("public_snippets", []) or []
    memory_facts = state.get("memory_facts", []) or []
    parts: List[str] = [
        "You are a cautious health assistant. Summarise guidance based strictly on the provided data.",
        "Avoid diagnoses; cite numbered sources when available.",
        f"User question: {user_query}",
    ]

    if snippets:
        formatted = [
            f"[{idx+1}] {snip.get('title', 'Untitled')} - {snip.get('section', '')}: {snip.get('text', '')}"
            for idx, snip in enumerate(snippets)
        ]
        parts.append("Sources:\n" + "\n".join(formatted))

    if memory_facts:
        memories = [
            f"- {fact.get('entity', 'fact')}: {fact.get('name', fact.get('value', ''))}"
            for fact in memory_facts
        ]
        parts.append("Relevant personal context:\n" + "\n".join(memories))

    triggers = _risk_triggers(state)
    if triggers:
        parts.append("Risk flags triggered: " + ", ".join(triggers))

    return "\n\n".join(parts)


def _call_ollama(prompt: str) -> str | None:
    model = os.getenv("OLLAMA_MODEL", "llama3")
    try:
        import ollama  # type: ignore

        logger.debug("Calling Ollama model %s", model)
        response = ollama.chat(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You produce concise, safety-first health summaries.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        return response.get("message", {}).get("content")  # type: ignore[arg-type]
    except Exception as exc:  # pragma: no cover - depends on external runtime
        logger.warning("Ollama generation failed: %s", exc)
        return None


def _call_openai(prompt: str) -> str | None:
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY missing; falling back to template response")
        return None
    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=api_key)
        logger.debug("Calling OpenAI model %s", model)
        chat = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You produce concise, safety-first health summaries.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        if not chat.choices:
            logger.warning("OpenAI generation returned no choices")
            return None
        return chat.choices[0].message.content  # type: ignore[index]
    except Exception as exc:  # pragma: no cover - depends on external runtime
        logger.warning("OpenAI generation failed: %s", exc)
        return None


def _fallback_message(state: BodyState) -> str:
    parts: List[str] = []
    user_query = state.get("user_query_redacted", state.get("user_query", ""))
    if user_query:
        parts.append(f"Summary for: {user_query}")

    snippets = state.get("public_snippets", []) or []
    if snippets:
        highlights = []
        for idx, snip in enumerate(snippets, start=1):
            title = snip.get("title") or snip.get("section") or "Guidance"
            text = snip.get("text") or ""
            snippet = text.strip()
            truncated = snippet[:FALLBACK_HIGHLIGHT_LENGTH].strip()
            ellipsis = "..." if len(snippet) > FALLBACK_HIGHLIGHT_LENGTH else ""
            highlights.append(f"[{idx}] {title}: {truncated}{ellipsis}")
        parts.append("Key points:\n" + "\n".join(highlights))

    triggers = _risk_triggers(state)
    if triggers:
        parts.append("Risk notice: " + ", ".join(triggers))

    return (
        "\n\n".join(parts)
        if parts
        else "Here is a recap based on the available information."
    )


def _build_reply(content: str, state: BodyState) -> str:
    triggers = _risk_triggers(state)
    sections = [content.strip(), DISCLAIMER]
    if any(t in URGENT_TRIGGERS for t in triggers):
        sections.append(URGENT_LINE)
    return "\n\n".join(section for section in sections if section)


def _generate_with_provider(provider: str, prompt: str) -> str | None:
    if provider == "ollama":
        return _call_ollama(prompt)
    if provider == "openai":
        return _call_openai(prompt)
    logger.warning("Unknown LLM provider '%s'; falling back to template", provider)
    return None


def run(state: BodyState) -> BodyState:
    if _should_skip(state):
        return state

    provider = _resolve_provider()
    prompt = _build_prompt(state)
    content = _generate_with_provider(provider, prompt)
    if not content:
        content = _fallback_message(state)

    reply = _build_reply(content, state)
    message = {
        "role": "assistant",
        "content": reply,
        "citations": state.get("citations", []),
    }
    state.setdefault("messages", []).append(message)
    return state
