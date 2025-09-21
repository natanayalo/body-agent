# Idea Backlog

The items below are scoped concepts that build on the current multilingual Body Agent. They are not yet scheduled; when you are ready to tackle one, promote it into the PR stack inside `pull_request_template.md`.

## Symptom Flexibility

| Idea | Summary | Notes |
| --- | --- | --- |
| Intent exemplar registry | Maintain bilingual exemplars in JSONL and hot-reload them in dev so the supervisor can adapt without code changes. | Pair with threshold knobs via env vars. |
| Retrieval expansion | Add synonym/translation boosts (e.g., "כאבי בטן" → "stomach pain") and adjust ES scoring so language preference still applies. | Keep boosts configurable; reuse for other symptom families. |
| Pattern-based fallback templates | Provide audited EN/HE templates per symptom bucket when RAG returns nothing. | Always include disclaimers and escalation rules. |
| Structured symptom registry | Map canonical symptoms to vetted doc IDs and escalation metadata. Inject those docs ahead of ES search. | Lives alongside the KB; supports quick onboarding of new content. |
| KB seeding + translation pipeline | Extend ingestion scripts to fetch/translate core symptom guidance to Hebrew. | Adds seed coverage for the items above. |

## Planning & Preferences

| Idea | Summary | Notes |
| --- | --- | --- |
| Preference expansion | Store `max_travel_km`, `insurance_network`, and richer availability preferences; surface reasons in planner output. | Requires schema + planner scoring adjustments. |
| Calendar rationale templates | Add short “why this slot” messages in EN/HE so planners explain decisions clearly. | Reuses planner debug info. |

## Connectors & Automation

| Idea | Summary | Notes |
| --- | --- | --- |
| CalDAV connector | Sync with self-hosted CalDAV servers behind feature flag; expose `calendar_mode`. | Ensure scrubber runs before outbound calls. |
| Google Calendar OAuth | Optional connector for users who approve external sync; gated behind explicit env flag. | Needs secure token storage plan. |
| MCP adapters for health sites | Domain-restricted search (gov/edu/WHO) behind a toggle. | Must pass through scrubber and rate limiting. |

## Observability & Evaluation

| Idea | Summary | Notes |
| --- | --- | --- |
| Risk eval harness | Extend the golden tests with EN/HE prompts specifically targeting risk thresholds. | Helps tune the zero-shot thresholds before release. |
| Request-id propagation | Attach per-run UUIDs through logs and debug endpoints so multi-user debugging stays sane. | Works well with the new trace endpoint. |

When you pick up an idea:

1. Flesh out acceptance criteria in `pull_request_template.md`.
2. Link back here when the feature ships so we can mark the item as done or archive it.
