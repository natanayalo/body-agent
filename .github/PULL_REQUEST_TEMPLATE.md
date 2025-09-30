## Outcome
<!--
One sentence focused on the user impact. Avoid code- or implementation-speak.
Example: “Meds onset questions now return a sourced fact sheet instead of a generic LLM summary.”
-->

## Demo
<!--
Provide runnable steps that take ≤90 seconds and exercise the change end-to-end. Prefer
an API/CLI snippet (e.g., curl, make) that shows the user-facing behaviour. If tests are
the only option, note that in the steps.
Example:
```bash
curl -s http://localhost:8000/api/graph/run \
  -H 'content-type: application/json' \
  -d '{"user_id":"demo","query":"אקמול מתי משפיע?"}' \
  | jq '.state | {language, messages: .messages[-1].content}'
```
-->

## Acceptance
- [ ] Tests: <!-- List updated/added tests (e.g., `services/api/tests/unit/test_med_facts.py::test_onset_for_alias_hebrew_language`) -->
- [ ] Docs: <!-- Link to updated docs or say “N/A” -->
- [ ] Not demoable: <!-- If you cannot demo, explain why and next steps (≤3 days). Leave blank when demo is provided. -->
