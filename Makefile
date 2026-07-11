# The Volt System — developer & ops entry points
.PHONY: install lint test test-unit test-integration test-agents reliability api frontend up down logs ps clean

PY ?= python

install:            ## Install python deps (app + api extras)
	pip install -r requirements.txt -r infrastructure/docker/requirements.txt

lint:               ## Static checks (ruff)
	ruff check .

test:               ## Full test suite
	pytest tests -q

reliability:        ## Run tests via agent-data-fabric: record run + flakiness/trend report
	pip install -q git+https://github.com/KhaledBakhtriIA/agent-data-fabric.git
	$(PY) -m reliability run .

test-unit:          ## Fast unit tests only
	pytest tests/unit -q

test-integration:   ## Integration tests
	pytest tests/integration -q

test-agents:        ## Agent-fleet tests
	pytest tests/agent_tests -q

api:                ## Run the FastAPI gateway locally
	uvicorn api.rest.app:app --reload --port 8000

frontend:           ## Run the React control-plane dashboard
	cd frontend && npm run dev

up:                 ## Full prod-like stack: API + Redpanda + Redis + Prometheus + Grafana
	docker compose up --build -d

down:               ## Stop the stack
	docker compose down

logs:               ## Tail API logs
	docker compose logs -f volt-data-api

ps:                 ## Show stack status
	docker compose ps

clean:              ## Remove caches
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} +
