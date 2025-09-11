Here’s the most valuable **next step** to land as a single, tidy PR.

# Next PR: “Privacy + Paths + CI polish”

Bundle the small-but-impactful fixes we discussed into one change. Scope:

1. **Wire the PII scrubber** into the graph

   * Add a `scrub` node right after the supervisor.
   * Ensure all logging + any future external calls use `state["user_query_redacted"]` (never the raw).
   * Acceptance: a log test proves raw emails/phones aren’t written.

2. **Unify the data directory (no more `/app/app/data`)**

   * Add `APP_DATA_DIR=/app/data` to `.env.example`.
   * In code, write ICS and other artifacts to `settings.data_dir` (not hardcoded paths).
   * Compose: mount a writable volume for `/app/data`.
   * Acceptance: new ICS files appear under `/app/data` and tests pass.

3. **Intent exemplars, explicit + offline-safe**

   * In `build_intent_exemplars.py` load MASSIVE with `"all_1.1"` (or catch failure and fall back to curated seeds).
   * Default output to `/app/data/intent_exemplars.json`; set `INTENT_EXEMPLARS_PATH` accordingly.
   * Acceptance: script works online; falls back cleanly offline.

4. **Risk model “stub” for tests/CI**

   * If `RISK_MODEL_ID="__stub__"`, return deterministic scores (no HF download).
   * Tests/CI set stub and assert gating behavior.
   * Acceptance: CI runs fast and stable.

5. **VS Code / pytest quality-of-life**

   * `pytest.ini`: keep `asyncio_mode = strict`; simplify `addopts`.
   * `.vscode/settings.json`: set `cwd` to `services/api` and discover tests in `tests`.
   * Acceptance: Test Explorer shows pass/fail; terminal `pytest` works with no extra env.

---

## Checklist (acceptance criteria)

* [ ] **Scrubber:** logs contain `[email]`/`[phone]` placeholders; raw PII not present.
* [ ] **Paths:** `POST /api/graph/run` produces ICS under `/app/data`, not `/app/app/data`.
* [ ] **Exemplars:** `build_intent_exemplars.py` writes to `/app/data/intent_exemplars.json` and app loads it if present.
* [ ] **Stubbed risk:** `RISK_MODEL_ID="__stub__"` makes tests pass without downloading a model.
* [ ] **CI:** green run without the VS Code adapter crash; coverage still on core nodes.

---

## Minimal diffs you’ll make

* `config.py`: add `data_dir` from `APP_DATA_DIR` (default `/app/data`).
* `calendar_tools.py` (and any writers): use `settings.data_dir`.
* `docker-compose.yml`: mount `./services/api/app/data:/app/data:rw`.
* `graph/main`: insert `scrub` node early; pass redacted text to any egress/logging.
* `risk_ml.py`: add `__stub__` branch.
* `build_intent_exemplars.py`: use `"all_1.1"` with offline fallback; default `--out /app/data/...`.
* `pytest.ini`, `.vscode/settings.json`: apply the config we discussed.
* Tests: enable the redaction test (remove xfail) and add a small supervisor smoke test (EN+HE) using exemplars.

---

## Quick verification commands

```bash
# Rebuild and run
docker compose up -d --build

# Generate exemplars (optional)
docker compose exec api python scripts/build_intent_exemplars.py \
  --langs en he --per-intent 40 --out /app/data/intent_exemplars.json
docker compose restart api

# Healthz
curl -s localhost:8000/healthz

# Run tests in container (stubbed risk)
docker compose exec -e RISK_MODEL_ID=__stub__ api pytest -q

# Create an appointment → check path
curl -s http://localhost:8000/api/graph/run \
  -H 'content-type: application/json' \
  -d '{"user_id":"demo-user","query":"Book a lab appointment tomorrow morning near me"}' | jq '.plan.event_path'

# Confirm files land under /app/data
docker compose exec api ls -l /app/data
```

---

## After that PR (next-next steps)

* **Provider ranking w/ preferences** (max distance, preferred hours/kind, reasons).
* **/debug endpoints** for risk scores + routing scores.
* **StateGraph migration** (compile & trace) once the linear pipeline is stable.

If you want, I can package this as `0008-privacy-paths-ci.patch` next.
