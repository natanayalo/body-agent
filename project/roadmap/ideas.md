# Idea Catalogue

Use the status column to see whether an idea is already shipped, queued up in the PR stack, or still in the backlog. Promote 🧭 items into `pr-stack.md` when they are ready.

**Status legend**

- ✅ Shipped
- 🔄 Scheduled / in-progress (see PR stack)
- 🧭 Backlog / exploratory

## Implemented (reference only)

| Status | Idea | Summary | Notes |
| --- | --- | --- | --- |
| ✅ | PII scrubber node | Incoming queries are scrubbed for PII before any external connector runs. | Implemented via `scrub.run`; keep extending regexes as new connectors appear. |
| ✅ | Debug trace & risk endpoints | `/api/debug/trace` records node order/timings; `/api/debug/risk` shows last classification + thresholds. | Added in PR 12 for observability. |
| ✅ | ICS generator | Generate calendar `.ics` files with unique filenames for scheduling flows. | Baseline calendar UX without external sync. |
| ✅ | Intent exemplar registry | Maintain bilingual exemplars in JSONL and hot-reload in dev. Keeps supervisor adaptable without code edits. | Shipped in PR 13; default path `/app/data/intent_exemplars.jsonl`. |
| ✅ | Pattern-based fallback templates | Provide localized symptom templates when retrieval is empty; include disclaimers and risk notices. | Shipped in PR 15; templates now keep safety messaging when providers fail. |
| ✅ | Retrieval expansion | Synonym/translation boosts and section boosting for health retrieval (e.g., "כאבי בטן" → "abdominal pain"). | Shipped in PR 14; tuned boosts while respecting doc language. |
| ✅ | Structured symptom registry | Map symptom slugs → vetted doc refs and language variants; inject before ES search. | Shipped in PR 16; deduping preserves localized snippets. |

## Scheduled (see `pr-stack.md`)

| Status | Idea | Summary | Notes |
| --- | --- | --- | --- |
| 🔄 | KB seeding & translation pipeline | Extend ingestion scripts to seed HE symptom guidance so fallback rarely fires. | Current PR 17. See project/roadmap/pr-stack.md. |
| 🔄 | Language detect & EN pivot | Detect HE and pivot query text to EN for stable retrieval; thread `user_query_pivot`. | Planned as PR 18. See pr-stack. |
| 🔄 | Med normalization | Minimal lexicon to normalize brands → ingredients; enrich memory facts. | Planned as PR 19. See pr-stack. |
| 🔄 | Meds sub-intent | Classify meds sub-intent (onset, interaction, schedule, etc.) for flow gating. | Planned as PR 20. See pr-stack. |
| 🔄 | Planner suppression (meds) | Do not emit schedule for meds flows unless sub-intent is `schedule`. | Planned as PR 21. See pr-stack. |
| 🔄 | Risk gating for onset | Raise thresholds/short-circuit risk for benign meds onset flows. | Planned as PR 22. See pr-stack. |
| 🔄 | Med facts micro-KB | Deterministic onset metadata and citations for common meds; render localized answers. | Planned as PR 23. See pr-stack. |

## Backlog / To Evaluate

### Planning & Preferences

| Status | Idea | Summary | Notes |
| --- | --- | --- | --- |
| 🧭 | Preference expansion | Store `max_travel_km`, `insurance_network`, richer availability prefs; surface reasons in planner output. | Needs schema extension + planner scoring changes. |
| 🧭 | Calendar rationale templates | Add short “why this slot” explanations in EN/HE so planner output is transparent. | Can reuse planner debug trace. |

### Connectors & Automation

| Status | Idea | Summary | Notes |
| --- | --- | --- | --- |
| 🧭 | CalDAV connector | Sync with self-hosted CalDAV servers behind feature flag; expose `calendar_mode`. | Ensure scrubber runs before outbound calls; consider ICS fallback. |
| 🧭 | Google Calendar OAuth | Optional Google sync gated behind explicit env flag. | Requires secure token storage + consent flow. |
| 🧭 | MCP adapters for health sites | Domain-restricted web search (gov/edu/WHO) behind toggle. | Must pass scrubber + rate limiting. |
| 🧭 | Domain allow-list enforcement | Enforce and document a strict domain allow-list for any outbound web connector. | Configurable via env; fail closed. |

### Observability & Evaluation

| Status | Idea | Summary | Notes |
| --- | --- | --- | --- |
| 🧭 | Risk eval harness | Extend the golden tests with EN/HE prompts geared toward tuning risk thresholds. | Helps sanity-check NLI thresholds before release. |
| 🧭 | Request-id propagation | Attach per-run UUID through logs/debug endpoints so multi-user debugging stays sane. | Works well with new trace endpoint; consider log format change. |
| 🧭 | Structured, PII-safe logs | Emit structured application logs (no raw user text) to improve debugging without privacy risk. | Align with scrubber; document redaction guarantees. |
| 🧭 | Risk highest-severity gating | Show only the single highest-severity ML risk banner (urgent_care > see_doctor) to avoid stacking. | Keep full scores in debug payload. |

### Security & Privacy

| Status | Idea | Summary | Notes |
| --- | --- | --- | --- |
| 🧭 | Client-side encryption plan | Encrypt `private_user_memory` values client-side (field-level) when remote storage is used. | Keys per user; ties into tenancy story.

### Miscellaneous

| Status | Idea | Summary | Notes |
| --- | --- | --- | --- |
| 🧭 | Preference-aware provider scoring | Blend semantic score with distance, hours fit, insurance match using configurable weights. | Requires more provider metadata + tests. |
| 🧭 | Lightweight meds registry | Small YAML of common OTC classes (uses, avoid_if, interactions) to supplement answers without dosing. | Consider after Milestone 2; overlap with med facts work. |
| 🧭 | LLM paraphrase for onset facts | When a deterministic med fact exists, paraphrase it into the user’s language via Ollama (no new numbers/claims) behind a feature flag. | Enforce validators to reject added numbers; always include “Source: …”. |
| 🧭 | LLM neutral fallback (no fact) | If no onset fact is found, generate a neutral, non‑timed guidance blurb (no dosing/times) behind a feature flag. | Safer than guessing; reject outputs with numbers/time words; include disclaimer.

When you pick up an idea:

1. Flesh out acceptance criteria in `pr-stack.md` (or move the row into the scheduled section).
2. Once shipped, move the row to the **Implemented** table (or archive it with a link to the PR).
