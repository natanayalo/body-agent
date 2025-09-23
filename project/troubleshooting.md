# Troubleshooting & Ops

Common issues and quick fixes during local dev and CI.

## Elasticsearch & vectors

- Vector dims mismatched / cosine errors: ensure embedding size matches index mapping. In stub mode, embeddings are deterministic; avoid all-zero vectors for cosine.
- If indices are stale/corrupted, run `make e2e-local-clean` then re-seed (`make e2e-local-up`).

## Permissions

- Logs: in local E2E, the API writes to `/tmp/api.log`; tail via `make e2e-local-logs`.
- Data: `data/` is container-owned; avoid editing inside from host; seeds are copied by CI to `/app/data`.

## Startup

- API not up yet: `make e2e-local-wait` pings `/healthz` for up to 60s and dumps `/tmp/api.log` on failure.
- Check routes at `GET /__routes` to confirm the app booted and the graph compiled.
