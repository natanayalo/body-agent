# Architecture Overview (MVP)

This is the concise, living map for contributors. See `docs/architecture.md` for the full spec; this page focuses on the graph, event order, and where we hit Elasticsearch (ES).

## Node Block Diagram

scrub → supervisor → memory → { health | places } → risk_ml → planner → answer_gen → critic → END

- scrub: PII redaction of the incoming query; produces `user_query_redacted`.
- supervisor: intent routing via exemplar embeddings (EN/HE); sets `intent`.
- memory: fetches `private_user_memory` facts for `user_id`.
- health: retrieves public medical snippets; prioritizes `language` and section boosts.
- places: finds providers/slots; applies simple ranking and preference hints.
- risk_ml: NLI-based signals → `debug.risk.triggered` (e.g., urgent_care).
- planner: produces a plan (appointment/med schedule/none), or converges.
- answer_gen: optional LLM; safe fallback recaps; pattern templates when empty.
- critic: guards final message (citations present, disclaimers added).

## Sequences

### A) Med interaction/safety (symptom phrasing)

1. scrub: redacts PII.
2. supervisor: `intent = symptom`.
3. memory: user facts (meds/allergies) → `memory_facts` (ES: private index).
4. health: retrieve public docs (ES: public index; kNN + BM25 hybrid).
5. risk_ml: classify risk (urgent/self-care/etc.).
6. planner: no appointment; set `plan = none`.
7. answer_gen: provider present? generate summary; else recap or pattern fallback (templates) with disclaimers.
8. critic: enforce safety/citations.

ES hits: (3) private_user_memory, (4) public_medical_kb.

Streaming (SSE): memory → health → risk_ml → planner → answer_gen → critic → final.

### B) Appointment planning

1. scrub → supervisor: `intent = appointment`.
2. memory: preferences (distance, kind, hours) from private index.
3. places: search providers (ES: providers_places; geo + keyword).
4. planner: select top candidate; produce ICS; attach reasons.
5. answer_gen: optional summary.
6. critic → END.

SSE order: memory → places → planner → answer_gen → critic → final.

## Indices and Queries

- private_user_memory: term filter on `user_id`; optional vector for semantic match; encrypted fields.
- public_medical_kb: language filter; section boosts (general/warnings); kNN + BM25.
- providers_places: geo + structured filters; semantic fallback.

## Final Event Contract

- `/api/graph/stream`: the `final` event is always the last message and contains the exact final `state`.
- `/api/graph/run`: returns `{ "state": { ... } }` envelope.
