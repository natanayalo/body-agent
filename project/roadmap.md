# Roadmap (MVP → v1)

## Now — Milestone 1 (Meds “onset” relevance)

- Language detection + HE→EN pivot for retrieval (PR 18)
- Med normalization lexicon + sub-intent classification (PR 19–20)
- Planner/risk gating updates for onset flows (PR 21–22)
- Deterministic med-facts micro-KB powering onset answers (PR 23)

## Next — Milestone 2 (Retrieval quality & cleanliness)

- BM25 fallback with medication boosts when kNN misses (PR 24)
- Citation dedupe with URL normalization (PR 25)
- Language-aware answer rendering in `answer_gen` (PR 26)
- Optional, safe LLM polish behind flags:
  - Paraphrase deterministic onset facts (no new numbers) via Ollama (PR 32)
  - Neutral LLM fallback when no onset fact exists (no timings/doses) (PR 33)

## Later — Milestones 3 & 4 (Stability + privacy)

- Idempotent seed job, SSE contract test, docs polish (PR 27–29)
- Intent exemplar hot-reload refinements + expanded PII scrub rules (PR 30–31)
-- Longer-term: client-side field encryption, calendar integration, vetted MCP adapters

See `project/roadmap/pr-stack.md` for current PR slices and acceptance criteria.
