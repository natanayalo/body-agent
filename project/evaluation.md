# Evaluation & Quality

How we keep quality predictable across unit, integration, and end-to-end tests.

## Test Matrix

- Unit: individual nodes/utilities (e.g., supervisor, risk_ml, answer_gen fallbacks).
- Integration: compiled graph via FastAPI app (fixtures stub external models).
- E2E: live API with ES running, seeded indices, stub models for determinism.

## Acceptance Checks

- RAG recall: Ensure at least one relevant snippet is returned for a seeded symptom in `public_medical_kb`.
- Risk thresholds: Verify `urgent_care`/`see_doctor` triggers at configured thresholds (`RISK_THRESHOLDS`).
- SSE contract: Streamed `final` event is emitted last; node deltas appear in graph order.

## Synthetic Fixtures

- Meds interactions: seed small doc pairs verifying NSAID/warfarin warnings.
- Providers: deterministic ordering fixture to test ranking preferences.

## Commands

- Unit+integration with coverage: `venv/bin/pytest` (95% gate).
- Golden tests: `make eval`.
- E2E (CI parity): `make e2e-local`.
