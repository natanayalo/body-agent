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

## Scheduled (see `pr-stack.md`)

| Status | Idea | Summary | Notes |
| --- | --- | --- | --- |
| 🔄 | Intent exemplar registry | Maintain bilingual exemplars in JSONL and hot-reload in dev. Keeps supervisor adaptable without code edits. | Proposed as PR 13. Pair with env-driven thresholds. See docs/roadmap/pr-stack.md. |
| 🔄 | Retrieval expansion | Synonym/translation boosts (e.g., "כאבי בטן" → "stomach pain") plus section boosting while respecting doc language. | Proposed as PR 14. Shares config with structured registry. See docs/roadmap/pr-stack.md. |
| 🔄 | Pattern-based fallback templates | Audited EN/HE templates when RAG returns nothing; always include disclaimers/escalation. | Proposed as PR 15. See docs/roadmap/pr-stack.md. |
| 🔄 | Structured symptom registry | Map symptom slugs → vetted doc IDs, risk flags, and language variants; inject before ES search. | Proposed as PR 16. See docs/roadmap/pr-stack.md. |
| 🔄 | KB seeding & translation pipeline | Extend ingestion scripts to seed HE symptom guidance so fallback rarely fires. | Proposed as PR 17. See docs/roadmap/pr-stack.md. |
| 🔄 | Lightweight meds registry | Small YAML of common OTC classes (uses, avoid_if, interactions) to supplement answers without adding many KB pages; no dosing. | Proposed as PR 18. See docs/roadmap/pr-stack.md. |

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

When you pick up an idea:

1. Flesh out acceptance criteria in `pr-stack.md` (or move the row into the scheduled section).
2. Once shipped, move the row to the **Implemented** table (or archive it with a link to the PR).
