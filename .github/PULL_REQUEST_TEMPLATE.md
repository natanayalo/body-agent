## Outcome
What user problem does this change solve?

## Demo
Paste runnable steps (60–90s max):
```bash
# example:
curl -s http://localhost:8000/api/graph/run \
  -H 'content-type: application/json' \
  -d '{"user_id":"demo","query":"אקמול מתי משפיע?"}' |
  jq '.state.messages[-1].content'
```

## Acceptance Checks
- [ ] Test added/updated (name: `test_...`)
- [ ] Docs updated (link)
- [ ] If not demoable, explain why and the next step (≤ 3 days)
