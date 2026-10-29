# Run from the repository root. Recipe lines use tabs.
.DEFAULT_GOAL := help
.NOTPARALLEL:
.PHONY: help install up migrate seed index bootstrap lint test check serve verify-live verify-retrieval evaluate

help:
	@echo "make bootstrap         Install, start services, migrate, seed, index (no deletes)"
	@echo "make check             Lint, validate labels, run offline tests"
	@echo "make serve             Start FastAPI on 127.0.0.1:8000"
	@echo "make verify-retrieval  Check DB, retrieval and development retrieval evaluation"
	@echo "make verify-live       Also check Ollama and running API; no holdout queries"
	@echo "make evaluate          Run full Day 6 development evaluation"

install:
	uv sync --locked --dev
up:
	docker compose up -d --wait postgres opensearch
migrate:
	uv run --locked alembic upgrade head
seed:
	uv run --locked python -m scripts.seed_papers
index:
	uv run --locked python -m scripts.index_papers
bootstrap:
	$(MAKE) install
	$(MAKE) up
	$(MAKE) migrate
	$(MAKE) seed
	$(MAKE) index
lint:
	uv run --locked ruff check src scripts tests migrations
test:
	uv run --locked python -m scripts.evaluate --validate-only
	uv run --locked pytest -q
check:
	$(MAKE) lint
	$(MAKE) test
serve:
	uv run --locked uvicorn src.main:create_app --factory --reload --host 127.0.0.1 --port 8000
verify-retrieval:
	uv run --locked python -m scripts.verify_week1 --skip-generation
verify-live:
	uv run --locked python -m scripts.verify_week1
evaluate:
	uv run --locked python -m scripts.evaluate
