# Idea Catalogue

Use the status column to see whether an idea is already shipped, queued up in the PR stack, or still in the backlog. Promote 🧭 items into `pr-stack.md` when they are ready.

**Status legend**

- ✅ Shipped
- 🔄 Scheduled / in-progress (see PR stack)
- 🧭 Backlog / exploratory

## Implemented (reference only)

| Status | Idea | Summary | Notes |
| --- | --- | --- | --- |
| ✅ | PII scrubber node | Incoming queries are scrubbed for PII before any external connector runs. | Shipped in PR 5. Owner: @natanayalo. Rollback: set `SCRUBBER_ENABLED=false`. Demo: `curl -s http://localhost:8000/api/graph/run -d '{"user_id":"demo","query":"my SSN is 123-45-6789"}' | jq '.state.user_query_redacted'`. |
| ✅ | Debug trace & risk endpoints | `/api/debug/trace` records node order/timings; `/api/debug/risk` shows last classification + thresholds. | Shipped in PR 12. Owner: @natanayalo. Rollback: hide debug endpoints via `DEBUG_ENDPOINTS_ENABLED=false`. Demo: `curl -s http://localhost:8000/api/debug/risk`. |
| ✅ | ICS generator | Generate calendar `.ics` files with unique filenames for scheduling flows. | Shipped in PR 11. Owner: @natanayalo. Rollback: set `ICS_ENABLED=false`. Demo: `curl -s http://localhost:8000/api/calendar/ics | head`. |
| ✅ | Intent exemplar registry | Maintain bilingual exemplars in JSONL and hot-reload in dev. Keeps supervisor adaptable without code edits. | Shipped in PR 13. Owner: @natanayalo. Rollback: set `INTENT_EXEMPLARS_WATCH=false`. Demo: `curl -s http://localhost:8000/api/graph/run -d '{"user_id":"demo","query":"איפה המרפאה"}' | jq '.state.intent'`. |
| ✅ | Pattern-based fallback templates | Provide localized symptom templates when retrieval is empty; include disclaimers and risk notices. | Shipped in PR 15. Owner: @natanayalo. Rollback: `FALLBACK_TEMPLATES_ENABLED=false`. Demo: `curl -s http://localhost:8000/api/graph/run -d '{"user_id":"demo","query":"I have itchy eyes"}' | jq '.state.messages[-1].content'`. |
| ✅ | Retrieval expansion | Synonym/translation boosts and section boosting for health retrieval (e.g., "כאבי בטן" → "abdominal pain"). | Shipped in PR 14. Owner: @natanayalo. Rollback: revert to default query builder via `RETRIEVAL_EXPANSION_ENABLED=false`. Demo: `curl -s http://localhost:8000/api/graph/run -d '{"user_id":"demo","query":"I have abdominal cramps"}' | jq '.state.citations'`. |
| ✅ | Structured symptom registry | Map symptom slugs → vetted doc refs and language variants; inject before ES search. | Shipped in PR 16. Owner: @natanayalo. Rollback: set `SYMPTOM_REGISTRY_ENABLED=false`. Demo: `curl -s http://localhost:8000/api/graph/run -d '{"user_id":"demo","query":"I feel dizzy"}' | jq '.state.debug.symptom_registry'`. |
| ✅ | Docs & roadmap refresh | Added architecture/config/privacy/evaluation docs and aligned README streaming guidance. | Shipped in PR 17. Owner: @natanayalo. |
| ✅ | Language detect & EN pivot | Detect Hebrew queries and expose `user_query_pivot` so downstream retrieval stays stable. | Shipped in PR 18. Owner: @natanayalo. Rollback: `LANGUAGE_PIVOT_ENABLED=false`. Demo: `curl -s http://localhost:8000/api/graph/run -d '{"user_id":"demo","query":"יש לי כאב ראש"}' | jq '.state.user_query_pivot'`. |
| ✅ | Med normalization | Normalize common brands → ingredients during ingest and supervisor flows. | Shipped in PR 19. Owner: @natanayalo. Rollback: unset `MED_NORMALIZE_ENABLED`. Demo: `curl -s http://localhost:8000/api/graph/run -d '{"user_id":"demo","query":"I take Advil"}' | jq '.state.debug.normalized_meds'`. |
| ✅ | Meds sub-intent classification | Classify meds queries into onset/interaction/schedule/etc. for deterministic routing. | Shipped in PR 20. Owner: @natanayalo. Rollback: `MED_SUBINTENT_ENABLED=false`. Demo: `curl -s http://localhost:8000/api/graph/run -d '{"user_id":"demo","query":"When do ibuprofen effects start?"}' | jq '.state.sub_intent'`. |
| ✅ | Planner suppression for meds | Skip schedule plans unless `sub_intent == "schedule"`. | Shipped in PR 21. Owner: @natanayalo. Rollback: set `PLANNER_MED_SUPPRESS=false`. Demo: `curl -s http://localhost:8000/api/graph/run -d '{"user_id":"demo","query":"How should I take my medications?"}' | jq '.state.plan'`. |
| ✅ | Risk gating for meds onset | Relax risk thresholds for benign onset questions while keeping red-flag escalations. | Shipped in PR 22. Owner: @natanayalo. Rollback: remove custom `RISK_THRESHOLDS`. Demo: `curl -s http://localhost:8000/api/graph/run -d '{"user_id":"demo","query":"אקמול מתי משפיע?"}' | jq '.state.alerts'`. |
| ✅ | Deterministic meds onset answers | Serve onset guidance from vetted facts with localized copy and single citation. | Shipped in PR 23. Owner: @natanayalo. Rollback: `MED_FACTS_ENABLED=false`. Demo: `curl -s http://localhost:8000/api/graph/run -d '{"user_id":"demo","query":"When does acetaminophen kick in?"}' | jq '.state.messages[-1].content'`. |
| ✅ | Med interaction recall & language-aware answers | Boost BM25 combos, dedupe citations, and follow `state.language` in answers. | Shipped in PR 24. Owner: @natanayalo. Rollback: revert to baseline retrieval weights. Demo: `curl -s http://localhost:8000/api/graph/run -d '{"user_id":"demo","query":"Can I take ibuprofen with warfarin?"}' | jq '.state.citations'`. |
| ✅ | Preference expansion (distance filter) | Respect user travel radius when ranking providers and expose the applied limit in planner reasons. | Shipped in PR 35. Owner: @natanayalo. Rollback: `PREFERENCE_TRAVEL_LIMIT_ENABLED=false`. Demo: `curl -s http://localhost:8000/api/graph/run -d '{"user_id":"demo","query":"Find a clinic nearby","preferences":{"max_travel_km":5}}' | jq '.state.candidates | map({name, distance_km})'`. |

## Scheduled (see `pr-stack.md`)

| Status | Idea | Summary | Notes |
| --- | --- | --- | --- |
| 🔄 | Paraphrase onset facts (flagged) | Optional Ollama paraphrase for deterministic onset answers; no new numbers. | Planned as PR 25. See pr-stack. **Kill if:** two evaluation runs show paraphrased outputs drift from numeric facts or increase hallucination rate. |
| 🔄 | Neutral onset fallback (flagged) | Safe LLM blurb when no med fact exists (no timings/doses). | Planned as PR 26. See pr-stack. **Kill if:** fallback responses score <90% on safety checklist or add latency >1s after two tuning passes. |

## Backlog / To Evaluate

### Planning & Preferences

| Status | Idea | Summary | Notes |
| --- | --- | --- | --- |
| 🔄 | Calendar rationale templates | Add short “why this slot” explanations in EN/HE so planner output is transparent. | Planned as PR 36; leverage planner debug trace for copy hints. **Kill if:** after 2 iterations, rationales do not improve planner satisfaction scores in E2E evals. |

### Connectors & Automation

| Status | Idea | Summary | Notes |
| --- | --- | --- | --- |
| 🧭 | CalDAV connector | Sync with self-hosted CalDAV servers behind feature flag; expose `calendar_mode`. | Ensure scrubber runs before outbound calls; consider ICS fallback. **Kill if:** CalDAV sync prototype requires persistent credentials or network egress that violates privacy guardrails. |
| 🧭 | Google Calendar OAuth | Optional Google sync gated behind explicit env flag. | Requires secure token storage + consent flow. **Kill if:** OAuth flow adds unmanaged PII storage or exceeds 100ms latency budget for planner availability lookup. |
| 🧭 | MCP adapters for health sites | Domain-restricted web search (gov/edu/WHO) behind toggle. | Must pass scrubber + rate limiting. **Kill if:** adapter fails to keep citation provenance or the allow-list adds >3 new domains without legal review. |
| 🧭 | Domain allow-list enforcement | Enforce and document a strict domain allow-list for any outbound web connector. | Configurable via env; fail closed. **Kill if:** connector audit demonstrates false positives >5% on vetted partners after tuning. |

### Observability & Evaluation

| Status | Idea | Summary | Notes |
| --- | --- | --- | --- |
| 🧭 | Risk eval harness | Extend the golden tests with EN/HE prompts geared toward tuning risk thresholds. | Helps sanity-check NLI thresholds before release. **Kill if:** harness setup cannot run under 60s or fails to catch regression cases in two test sprints. |
| 🧭 | Request-id propagation | Attach per-run UUID through logs/debug endpoints so multi-user debugging stays sane. | Works well with new trace endpoint; consider log format change. **Kill if:** propagation adds duplicate log volume >20% or leaks identifiers outside scrubbed fields. |
| 🧭 | Structured, PII-safe logs | Emit structured application logs (no raw user text) to improve debugging without privacy risk. | Align with scrubber; document redaction guarantees. **Kill if:** structured logging cannot meet 95% redaction accuracy in QA replay. |
| 🧭 | Risk highest-severity gating | Show only the single highest-severity ML risk banner (urgent_care > see_doctor) to avoid stacking. | Keep full scores in debug payload. **Kill if:** gating removes critical warnings in clinical QA scenarios. |

### Security & Privacy

| Status | Idea | Summary | Notes |
| --- | --- | --- | --- |
| 🧭 | Client-side encryption plan | Encrypt `private_user_memory` values client-side (field-level) when remote storage is used. | Keys per user; ties into tenancy story. **Kill if:** encryption prototype adds >15% latency or blocks auditing requirements. |

### Miscellaneous

| Status | Idea | Summary | Notes |
| --- | --- | --- | --- |
| 🔄 | Preference-aware provider scoring | Blend semantic score with distance, hours fit, insurance match using configurable weights. | Planned as PR 37; expand provider metadata and scoring tests. **Kill if:** weighted scoring fails to increase top-match click-through in manual QA after two tuning passes. |
| 🧭 | Lightweight meds registry | Small YAML of common OTC classes (uses, avoid_if, interactions) to supplement answers without dosing. | Consider after Milestone 2; overlap with med facts work. **Kill if:** registry introduces dosage guidance or conflicts with deterministic med facts. |
| 🧭 | KB seeding & translation pipeline | Extend ingestion scripts to translate vetted symptom docs into Hebrew and store provenance. | Requires `scripts/ingest_public_kb.py` updates + seeding automation. **Kill if:** translation costs exceed budget or accuracy drops below 95% in bilingual review. |

When you pick up an idea:

1. Flesh out acceptance criteria in `pr-stack.md` (or move the row into the scheduled section).
2. Once shipped, move the row to the **Implemented** table (or archive it with a link to the PR).

### Licensing & provenance

- Public KB seeds: use permissively licensed health sources (e.g., NHS, Medline); link provenance in PRs that add content.
- `med_facts.json`: human-curated; each entry must include `source_title` + `source_url`. PRs modifying facts should update citations or explain provenance.
