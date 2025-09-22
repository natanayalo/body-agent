from __future__ import annotations

import logging
import os
from typing import List, Tuple, Dict, Optional, Any

from app.config import settings
from app.graph.state import BodyState
from app.tools.language import DEFAULT_LANGUAGE

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

# Lightweight, reviewed fallback templates for symptom buckets (EN/HE)
FALLBACK_TEMPLATES: Dict[str, Dict[str, str]] = {
    "gi": {
        "en": (
            "Self-care for mild stomach pain\n"
            "- Rest, hydrate (small sips), and try bland foods (e.g., rice, toast).\n"
            "- Avoid alcohol; consider pausing NSAIDs if they upset your stomach.\n"
            "- Seek urgent care for severe/worsening pain, persistent vomiting, blood in stool, high fever, chest pain, or shortness of breath."
        ),
        "he": (
            "עזרה עצמית לכאב בטן קל\n"
            "- לנוח, לשתות לאט ולנסות מזון קל (למשל אורז, טוסט).\n"
            "- להימנע מאלכוהול; לשקול הימנעות מ-NSAIDs אם יש גירוי בקיבה.\n"
            "- פנו בדחיפות אם הכאב חמור/מחמיר, יש הקאות ממושכות, דם בצואה, חום גבוה, כאב בחזה או קוצר נשימה."
        ),
    },
    "resp": {
        "en": (
            "Self-care for mild cough/cold\n"
            "- Rest, fluids, and humidified air may help.\n"
            "- Honey (for adults/children >1y) can soothe cough; avoid smoking/vaping.\n"
            "- Seek care for breathing difficulty, chest pain, high fever, or if symptoms persist/worsen."
        ),
        "he": (
            "עזרה עצמית לשיעול/התקררות קלים\n"
            "- מנוחה, שתייה וחדר מאוורר/מאוּדה עשויים לעזור.\n"
            "- דבש (למבוגרים/ילדים מעל שנה) עשוי להקל; להימנע מעישון.\n"
            "- פנו לרופא אם יש קושי בנשימה, כאב בחזה, חום גבוה או החמרה."
        ),
    },
    "neuro": {
        "en": (
            "Self-care for mild headache\n"
            "- Rest in a quiet, dark room; hydrate and consider a light snack.\n"
            "- Limit screen time and ensure regular sleep.\n"
            "- Seek urgent care for "
            "sudden worst headache, neurologic symptoms (weakness, confusion), head injury, or fever with stiff neck."
        ),
        "he": (
            "עזרה עצמית לכאב ראש קל\n"
            "- מנוחה בחדר שקט ומוחשך; שתייה קלה וחטיף קל.\n"
            "- להפחית זמן מסך ולשמור על שינה סדירה.\n"
            "- פנו בדחיפות אם זה 'כאב הראש הגרוע ביותר', יש סימנים נוירולוגיים, חבלת ראש או חום עם נוקשות צוואר."
        ),
    },
    "general": {
        "en": (
            "General self-care\n"
            "- Rest, hydrate, and avoid triggers when possible.\n"
            "- Monitor symptoms and seek medical advice if they persist or worsen."
        ),
        "he": (
            "עזרה עצמית כללית\n"
            "- מנוחה, שתייה והימנעות מטריגרים.\n"
            "- עקבו אחר התסמינים ופנו לייעוץ רפואי אם יש החמרה או התמדה."
        ),
    },
}

_TEMPLATES_PATH: Optional[str] = os.getenv("FALLBACK_TEMPLATES_PATH")
_TEMPLATES_WATCH: bool = (
    os.getenv("FALLBACK_TEMPLATES_WATCH", "false").strip().lower() == "true"
)
_TEMPLATES_MTIME: Optional[float] = None
_TEMPLATES_MAP: Dict[str, Dict[str, str]] = dict(FALLBACK_TEMPLATES)


def _parse_templates_obj(obj: Any) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    if isinstance(obj, dict):
        for bucket, per_lang in obj.items():
            if not isinstance(per_lang, dict):
                continue
            lang_map: Dict[str, str] = {}
            for lang, text in per_lang.items():
                if isinstance(lang, str) and isinstance(text, str) and text.strip():
                    lang_map[lang] = text
            if lang_map:
                out[str(bucket)] = lang_map
    return out


def _load_templates_from_file(path: str) -> Optional[Dict[str, Dict[str, str]]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            if path.endswith(".json"):
                import json

                data = json.load(f)
                parsed = _parse_templates_obj(data)
            elif path.endswith(".yaml") or path.endswith(".yml"):
                try:
                    import yaml  # type: ignore
                except Exception:
                    logger.warning(
                        "PyYAML not installed; cannot parse YAML templates; using defaults."
                    )
                    return None
                data = yaml.safe_load(f)
                parsed = _parse_templates_obj(data)
            else:
                logger.warning(
                    "Unknown templates extension for %s (use .json/.yaml/.yml)", path
                )
                return None
        if parsed:
            return parsed
    except Exception as e:
        logger.warning("Failed loading fallback templates from %s: %s", path, e)
    return None


def _init_templates_map() -> None:
    global _TEMPLATES_MAP, _TEMPLATES_MTIME
    path = _TEMPLATES_PATH
    if path and os.path.exists(path):
        parsed = _load_templates_from_file(path)
        if parsed:
            _TEMPLATES_MAP = parsed
            try:
                _TEMPLATES_MTIME = os.path.getmtime(path)
            except OSError:
                _TEMPLATES_MTIME = None
            logger.info("Loaded fallback templates from %s", path)
        else:
            logger.warning("Templates file invalid/empty; using built-in defaults")
    else:
        logger.debug("FALLBACK_TEMPLATES_PATH not set or file missing; using defaults")


def _maybe_reload_templates() -> None:
    if not _TEMPLATES_WATCH:
        return
    path = _TEMPLATES_PATH
    if not path or not os.path.exists(path):
        return
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return
    global _TEMPLATES_MTIME, _TEMPLATES_MAP
    if _TEMPLATES_MTIME is None or mtime > _TEMPLATES_MTIME:
        parsed = _load_templates_from_file(path)
        if parsed:
            _TEMPLATES_MAP = parsed
            _TEMPLATES_MTIME = mtime
            logger.info("Reloaded fallback templates after file change")


_init_templates_map()


def _bucketize_symptom(text: str, lang: str) -> str:
    s = (text or "").lower()
    # Hebrew GI keywords
    gi_he = ["כאבי בטן", "כאב בטן", "בטן", "שלשול", "הקאה", "בחילה", "קיבה"]
    gi_en = [
        "stomach",
        "abdominal",
        "belly",
        "nausea",
        "vomit",
        "diarrhea",
        "indigestion",
    ]
    resp_he = ["שיעול", "צינון", "גרון", "ליחה", "נשימה", "קוצר נשימה"]
    resp_en = ["cough", "cold", "throat", "phlegm", "congestion", "breath", "wheez"]
    neuro_he = ["כאב ראש", "מיגרנה", "סחרחורת", "התעלפות"]
    neuro_en = ["headache", "migraine", "dizzi", "faint", "neurolog"]

    if lang == "he":
        if any(k in s for k in [*gi_he]):
            return "gi"
        if any(k in s for k in [*resp_he]):
            return "resp"
        if any(k in s for k in [*neuro_he]):
            return "neuro"
        return "general"
    else:
        if any(k in s for k in [*gi_en]):
            return "gi"
        if any(k in s for k in [*resp_en]):
            return "resp"
        if any(k in s for k in [*neuro_en]):
            return "neuro"
        return "general"


def _template_fallback(state: BodyState) -> str:
    _maybe_reload_templates()
    lang, _ = _language_config(state)
    query = state.get("user_query_redacted", state.get("user_query", ""))
    bucket = _bucketize_symptom(query, lang)
    source = _TEMPLATES_MAP if _TEMPLATES_MAP else FALLBACK_TEMPLATES
    template = source.get(bucket, source.get("general", {})).get(
        lang, source.get("general", {}).get(DEFAULT_LANGUAGE, "")
    )
    return template


def _resolve_provider() -> str:
    return os.getenv("LLM_PROVIDER", settings.llm_provider).strip().lower()


def _language_config(state: BodyState) -> Tuple[str, dict]:
    lang_choice: str = DEFAULT_LANGUAGE
    lang_value = state.get("language")
    if isinstance(lang_value, str) and lang_value in LANG_CONFIG:
        lang_choice = lang_value
    return lang_choice, LANG_CONFIG[lang_choice]


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
    _, config = _language_config(state)
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
        highlights: List[str] = []
        for idx, snip in enumerate(snippets, start=1):
            title = snip.get("title") or snip.get("section") or "Guidance"
            text = snip.get("text") or ""
            snippet = text.strip()
            truncated = snippet[:FALLBACK_HIGHLIGHT_LENGTH].strip()
            ellipsis = "..." if len(snippet) > FALLBACK_HIGHLIGHT_LENGTH else ""
            highlights.append(f"[{idx}] {title}: {truncated}{ellipsis}")

        if highlights:
            parts.append(
                f"{config['fallback_key_points_label']}\n" + "\n".join(highlights)
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
        # If no retrieved snippets, consult pattern-based templates; otherwise recap snippets
        snippets = state.get("public_snippets", []) or []
        content = (
            _template_fallback(state) if not snippets else _fallback_message(state)
        )

    reply = _build_reply(content, state)
    message = {
        "role": "assistant",
        "content": reply,
        "citations": state.get("citations", []),
    }
    state.setdefault("messages", []).append(message)
    return state
