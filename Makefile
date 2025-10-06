SHELL := /bin/bash

# Config
ES_HOST ?= http://localhost:9200
API_BASE_URL ?= http://localhost:8000
APP_DATA_DIR ?= $(PWD)/data
HOST ?= 0.0.0.0
PORT ?= 8000
LOG_LEVEL ?= debug

# Prefer local venv tools when present
PY := $(shell if [ -x venv/bin/python ]; then echo venv/bin/python; else echo python; fi)
PYTEST := $(shell if [ -x venv/bin/pytest ]; then echo venv/bin/pytest; else echo pytest; fi)

.PHONY: e2e-local e2e-local-up e2e-local-api e2e-local-wait e2e-local-test e2e-local-down e2e-local-logs e2e-local-clean eval

e2e-local: e2e-local-up e2e-local-api e2e-local-wait e2e-local-test

e2e-local-up:
	@echo "[e2e-local] Starting Elasticsearch container..."
	docker compose up -d --build elasticsearch
	@echo "[e2e-local] Waiting for Elasticsearch... ($(ES_HOST))"
	ES_HOST=$(ES_HOST) PYTHONPATH=services/api \
		$(PY) scripts/wait_for_es.py
	@echo "[e2e-local] Ensuring indices..."
	PYTHONPATH=services/api ES_HOST=$(ES_HOST) \
		$(PY) -c "from app.tools.es_client import ensure_indices; ensure_indices(); print('OK: indices ensured')"
	@echo "[e2e-local] Seeding ES with stub embeddings..."
	mkdir -p $(APP_DATA_DIR)
	ES_HOST=$(ES_HOST) APP_DATA_DIR=$(APP_DATA_DIR) EMBEDDINGS_MODEL=__stub__ \
		$(PY) scripts/es_bootstrap.py
	ES_HOST=$(ES_HOST) APP_DATA_DIR=$(APP_DATA_DIR) EMBEDDINGS_MODEL=__stub__ \
		$(PY) scripts/ingest_providers.py
	ES_HOST=$(ES_HOST) APP_DATA_DIR=$(APP_DATA_DIR) EMBEDDINGS_MODEL=__stub__ \
		$(PY) scripts/ingest_public_kb.py

e2e-local-api:
	@echo "[e2e-local] Starting API (stub mode) on $(API_BASE_URL)..."
	mkdir -p /tmp/body-agent
	PYTHONPATH=services/api \
		ES_HOST=$(ES_HOST) \
		APP_DATA_DIR=$(APP_DATA_DIR) \
		EMBEDDINGS_MODEL=__stub__ \
		RISK_MODEL_ID=__stub__ \
		LLM_PROVIDER=none \
		nohup $(PY) -m uvicorn app.main:app \
		  --host $(HOST) --port $(PORT) --log-level $(LOG_LEVEL) \
		  > /tmp/api.log 2>&1 &
	@echo "[e2e-local] API logs: /tmp/api.log"

e2e-local-wait:
	@echo "[e2e-local] Waiting for API healthz at $(API_BASE_URL)/healthz ..."
	@for i in $$(seq 1 60); do \
		if curl -sf "$(API_BASE_URL)/healthz" | grep -q '"ok":true'; then \
			echo "API is ready"; exit 0; \
		fi; \
		echo "Waiting for API... ($$i/60)"; sleep 2; \
	done; \
	echo "API failed to become ready. --- /tmp/api.log ---"; \
	(tail -n +1 /tmp/api.log || true); \
	exit 7

e2e-local-test:
	@echo "[e2e-local] Running E2E tests..."
	API_BASE_URL=$(API_BASE_URL) RISK_MODEL_ID=__stub__ \
		$(PYTEST) --no-cov services/api/tests/e2e/

e2e-local-logs:
	@echo "--- /tmp/api.log ---"
	@tail -n 200 /tmp/api.log || true

e2e-local-down:
	@echo "[e2e-local] Tearing down containers..."
	docker compose down -v || true

e2e-local-clean:
	@echo "[e2e-local] Deleting indices on $(ES_HOST) ..."
	-@curl -s -o /dev/null -XDELETE $(ES_HOST)/private_user_memory
	-@curl -s -o /dev/null -XDELETE $(ES_HOST)/public_medical_kb
	-@curl -s -o /dev/null -XDELETE $(ES_HOST)/providers_places
	@echo "[e2e-local] Clean done. Re-run 'make e2e-local-up' to recreate."

eval:
	@echo "[eval] Running golden evaluation tests..."
	PYTHONPATH=services/api $(PYTEST) --no-cov services/api/tests/golden
