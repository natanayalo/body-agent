from __future__ import annotations

import logging
import os
from typing import List, Tuple

from app.config import settings
from app.graph.state import BodyState
from app.tools.language import DEFAULT_LANGUAGE, normalize_language_code

logger = logging.getLogger(__name__)

LANG_CONFIG = {
    "en": {
        "prompt_intro": [
            "You are a cautious health assistant. Summarise guidance based strictly on the provided data.",
            "Avoid diagnoses; cite numbered sources when available.",
        ],
        "user_question_label": "User question:",
        "sources_label": "Sources:",
        "context_label": "Relevant personal context:",
        "risk_flags_label": "Risk flags triggered:",
        "fallback_summary_label": "Summary for:",
        "fallback_key_points_label": "Key points:",
        "fallback_risk_label": "Risk notice:",
        "fallback_empty": "Here is a recap based on the available information.",
        "disclaimer": "**Disclaimer:** This assistant does not replace professional medical advice.",
        "urgent_line": "If you develop concerning or worsening symptoms, seek urgent evaluation.",
    },
    "he": {
        "prompt_intro": [
            "אתה עוזר בריאות זהיר. סכם הנחיות על בסיס המידע שסופק בלבד.",
            "הימנע מאבחנות; ציין מקורות ממוספרים כשאפשר.",
        ],
        "user_question_label": "שאלת המשתמש:",
        "sources_label": "מקורות:",
        "context_label": "הקשר אישי רלוונטי:",
        "risk_flags_label": "התראות סיכון:",
        "fallback_summary_label": "סיכום עבור:",
        "fallback_key_points_label": "נקודות עיקריות:",
        "fallback_risk_label": "התראת סיכון:",
        "fallback_empty": "להלן סיכום המבוסס על המידע הזמין.",
        "disclaimer": "**הבהרה:** הכלי אינו מחליף ייעוץ רפואי מקצועי.",
        "urgent_line": "אם תופיע החמרה או תסמינים מדאיגים, פנו לטיפול דחוף.",
    },
}

DISCLAIMER = LANG_CONFIG[DEFAULT_LANGUAGE]["disclaimer"]
URGENT_LINE = LANG_CONFIG[DEFAULT_LANGUAGE]["urgent_line"]
FALLBACK_HIGHLIGHT_LENGTH = 160
URGENT_TRIGGERS = {"urgent_care", "see_doctor"}


def _resolve_provider() -> str:
    return os.getenv("LLM_PROVIDER", settings.llm_provider).strip().lower()


def _language_config(state: BodyState) -> Tuple[str, dict]:
    lang: str = DEFAULT_LANGUAGE
    lang_value = state.get("language")
    if isinstance(lang_value, str) and lang_value in LANG_CONFIG:
        lang = lang_value
    return lang, LANG_CONFIG[lang]


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
    preferred_lang, config = _language_config(state)
    parts: List[str] = [
        *config["prompt_intro"],
        f"{config['user_question_label']} {user_query}",
    ]

    if snippets:
        formatted = [
            f"[{idx+1}] {snip.get('title', 'Untitled')} - {snip.get('section', '')}: {snip.get('text', '')}"
            for idx, snip in enumerate(snippets)
        ]
        parts.append(f"{config['sources_label']}\n" + "\n".join(formatted))

    if memory_facts:
        memories = [
            f"- {fact.get('entity', 'fact')}: {fact.get('name', fact.get('value', ''))}"
            for fact in memory_facts
        ]
        parts.append(f"{config['context_label']}\n" + "\n".join(memories))

    triggers = _risk_triggers(state)
    if triggers:
        parts.append(f"{config['risk_flags_label']} " + ", ".join(triggers))

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
    preferred_lang, config = _language_config(state)
    parts: List[str] = []
    user_query = state.get("user_query_redacted", state.get("user_query", ""))
    if user_query:
        parts.append(f"{config['fallback_summary_label']} {user_query}")

    snippets = state.get("public_snippets", []) or []
    if snippets:
        preferred_highlights: List[str] = []
        fallback_highlights: List[str] = []
        for idx, snip in enumerate(snippets, start=1):
            title = snip.get("title") or snip.get("section") or "Guidance"
            text = snip.get("text") or ""
            snippet = text.strip()
            truncated = snippet[:FALLBACK_HIGHLIGHT_LENGTH].strip()
            ellipsis = "..." if len(snippet) > FALLBACK_HIGHLIGHT_LENGTH else ""
            highlight = f"[{idx}] {title}: {truncated}{ellipsis}"
            fallback_highlights.append(highlight)

            snippet_lang = normalize_language_code(snip.get("language"))
            if snippet_lang == preferred_lang:
                preferred_highlights.append(highlight)

        selected = preferred_highlights or fallback_highlights
        if selected:
            parts.append(
                f"{config['fallback_key_points_label']}\n" + "\n".join(selected)
            )

    triggers = _risk_triggers(state)
    if triggers:
        parts.append(f"{config['fallback_risk_label']} " + ", ".join(triggers))

    return "\n\n".join(parts) if parts else config["fallback_empty"]


def _build_reply(content: str, state: BodyState) -> str:
    triggers = _risk_triggers(state)
    _, config = _language_config(state)
    sections = [content.strip(), config["disclaimer"]]
    if any(t in URGENT_TRIGGERS for t in triggers):
        sections.append(config["urgent_line"])
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
