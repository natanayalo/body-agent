## Outcome
<!--
Describe the user-facing impact (1–2 sentences). Keep it outcome-focused, not implementation detail.
Example: “Medication onset answers are now deterministic and sourced instead of LLM-generated.”
-->

## Demo
<!--
Provide ≤90s runnable steps that exercise the change end-to-end. Prefer user-facing commands (curl, make, UI script).
If automated tests are the only surface, state that explicitly.
Example:
```bash
curl -s http://localhost:8000/api/graph/run \
  -H 'content-type: application/json' \
  -d '{"user_id":"demo","query":"אקמול מתי משפיע?"}' \
  | jq '.state | {language, citations, reply: .messages[-1].content}'
```
-->

## Acceptance checks
<!-- Replace the guidance below with the checks you actually ran. -->
- [ ] **Unit / integration**: <!-- e.g. `services/api/tests/unit/test_answer_gen.py::test_answer_gen_meds_onset_uses_memory_fact` -->
- [ ] **i18n / locale**: <!-- What multilingual behaviour did you validate? -->
- [ ] **Observability**: <!-- Log/metric/debug signal showing the path is used. -->
- [ ] **Safety / disclaimers**: <!-- Confirm risk messaging, disclaimers, or red-flag behaviour. -->

## Scope
**Included**
- <!-- Bullet the work shipped in this PR. -->

**Excluded**
- <!-- Call out intentionally deferred items. -->

## Data & provenance
<!-- Note datasets/files touched, sources/licenses, and how to refresh/extend them. -->

## Rollback / Flags
<!-- Explain how to disable or revert the change (env flag, config toggle, etc.). -->

## Risks / Mitigations
<!-- Highlight key risks and how you’re mitigating or monitoring them. -->

## Docs & follow-up
- <!-- Link to updated docs or “N/A”. Add follow-up tasks if needed. -->
