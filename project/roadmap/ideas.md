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
| ✅ | Docs & roadmap refresh | Added architecture/config/privacy/evaluation docs and aligned README streaming guidance. | Shipped in PR 17; terminology stays consistent across guides. |
| ✅ | Language detect & EN pivot | Detect Hebrew queries and expose `user_query_pivot` so downstream retrieval stays stable. | Shipped in PR 18; health/risk nodes reuse the pivot text. |
| ✅ | Med normalization | Normalize common brands → ingredients during ingest and supervisor flows. | Shipped in PR 19; table-driven alias coverage. |
| ✅ | Meds sub-intent classification | Classify meds queries into onset/interaction/schedule/etc. for deterministic routing. | Shipped in PR 20; bilingual keyword rules + tests. |
| ✅ | Planner suppression for meds | Skip schedule plans unless `sub_intent == "schedule"`. | Shipped in PR 21; planner tests assert gating. |
| ✅ | Risk gating for meds onset | Relax risk thresholds for benign onset questions while keeping red-flag escalations. | Shipped in PR 22; parametrized risk tests. |
| ✅ | Deterministic meds onset answers | Serve onset guidance from vetted facts with localized copy and single citation. | Shipped in PR 23; med_facts helper + integration coverage. |
| ✅ | Med interaction recall & language-aware answers | Boost BM25 combos, dedupe citations, and follow `state.language` in answers. | Shipped in PR 24; interaction flow integration updated. |
| ✅ | Preference expansion (distance filter) | Respect user travel radius when ranking providers and expose the applied limit in planner reasons. | Shipped in PR 35; `places` node filters by `max_travel_km`. |

## Scheduled (see `pr-stack.md`)

| Status | Idea | Summary | Notes |
| --- | --- | --- | --- |
| 🔄 | Paraphrase onset facts (flagged) | Optional Ollama paraphrase for deterministic onset answers; no new numbers. | Planned as PR 25. See pr-stack. |
| 🔄 | Neutral onset fallback (flagged) | Safe LLM blurb when no med fact exists (no timings/doses). | Planned as PR 26. See pr-stack. |

## Backlog / To Evaluate

### Planning & Preferences

| Status | Idea | Summary | Notes |
| --- | --- | --- | --- |
| 🔄 | Calendar rationale templates | Add short “why this slot” explanations in EN/HE so planner output is transparent. | Planned as PR 36; leverage planner debug trace for copy hints. **Kill if:** after 2 iterations, rationales do not improve planner satisfaction scores in E2E evals. |

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
| 🔄 | Preference-aware provider scoring | Blend semantic score with distance, hours fit, insurance match using configurable weights. | Planned as PR 37; expand provider metadata and scoring tests. **Kill if:** weighted scoring fails to increase top-match click-through in manual QA after two tuning passes. |
| 🧭 | Lightweight meds registry | Small YAML of common OTC classes (uses, avoid_if, interactions) to supplement answers without dosing. | Consider after Milestone 2; overlap with med facts work. |
| 🧭 | KB seeding & translation pipeline | Extend ingestion scripts to translate vetted symptom docs into Hebrew and store provenance. | Requires `scripts/ingest_public_kb.py` updates + seeding automation. |

When you pick up an idea:

1. Flesh out acceptance criteria in `pr-stack.md` (or move the row into the scheduled section).
2. Once shipped, move the row to the **Implemented** table (or archive it with a link to the PR).

### Licensing & provenance

- Public KB seeds: use permissively licensed health sources (e.g., NHS, Medline); link provenance in PRs that add content.
- `med_facts.json`: human-curated; each entry must include `source_title` + `source_url`. PRs modifying facts should update citations or explain provenance.
