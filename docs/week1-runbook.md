# Week 1 runbook

## Existing checkout

Prerequisites: Python 3.12 via uv, Git, Docker Desktop with engine running, and native Ollama with the model selected in .env installed. Copy .env.example to .env only if .env does not exist; never replace existing settings.

```bash
make bootstrap
make check
make serve
```

In another terminal at the same repository:
```bash
make verify-live
make evaluate
```

Review Day 6 output manually. Full setup defaults use PostgreSQL 55432, OpenSearch 59200, API 8000 and Ollama 11434. Custom .env ports must agree with Compose and Python settings.

## Direct commands if make is unavailable

```bash
uv sync --locked --dev
docker compose up -d --wait postgres opensearch
uv run --locked alembic upgrade head
uv run --locked python -m scripts.seed_papers
uv run --locked python -m scripts.index_papers
uv run --locked ruff check src scripts tests migrations
uv run --locked python -m scripts.evaluate --validate-only
uv run --locked pytest -q
uv run --locked uvicorn src.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

In a second terminal:
```bash
uv run --locked python -m scripts.verify_week1
```

## Isolated clean-checkout exercise after pushing Day 7

Use a dedicated terminal. Stop the current API first; leave Ollama running. Make sure ports 55433 and 59201 are available. This exercise starts two additional containers; check Docker Desktop capacity if other workloads are running.

From the existing repository:
```bash
DAY7_REMOTE_URL="$(git remote get-url origin)"
DAY7_BRANCH="$(git branch --show-current)"
DAY7_CLEAN_DIR="$(dirname "$PWD")/paperlens-clean-check-$(date +%Y%m%d-%H%M%S)"
git clone --branch "$DAY7_BRANCH" "$DAY7_REMOTE_URL" "$DAY7_CLEAN_DIR"
cd "$DAY7_CLEAN_DIR"

cp -n .env.example .env
cat >> .env <<'EOF'

RAG_DB_PORT=55433
RAG_SEARCH_PORT=59201
RAG_SEARCH_BASE_URL=http://127.0.0.1:59201
EOF

export COMPOSE_PROJECT_NAME=paperlens-week1-check
make bootstrap
make check
make serve
```

COMPOSE_PROJECT_NAME selects a separate project and named volumes. On the first run this gives fresh DB/search storage; repeating this same exercise reuses its test volumes. No command removes either project.

If your usual model differs from .env.example, set RAG_OLLAMA_MODEL in this new .env to the installed model before generation checks. Do not copy unrelated secrets into the fresh checkout.

In a second terminal, change into the exact new directory printed by the clone command:
```bash
cd "/absolute/path/to/your/paperlens-clean-check-directory"
export COMPOSE_PROJECT_NAME=paperlens-week1-check
make verify-live
```

Use the actual directory, not the placeholder above. Record the tested commit with git rev-parse HEAD. Stop the API with Ctrl+C afterwards. From that clean-checkout terminal, stop only the test services:
```bash
docker compose stop
```

Keep the environment export scoped to this terminal. Your original project uses its original ports and .env. Do not run docker compose down -v or broad Docker cleanup to obtain a clean test.

## Failure diagnosis

- install: inspect uv errors and Python version; do not regenerate the lock to hide a mismatch.
- up: confirm Docker engine, free ports and resources; read docker compose logs --tail=100.
- migrate: confirm DB settings agree with Compose and review the migration error.
- seed/index: inspect the failed stage; repeated seed/index should not multiply fixture records.
- evaluation preflight: the index must match the exact original five-record corpus.
- api_contract: restart from Day 7 code, confirm port 8000 and health version 0.7.0.
- ollama_generation: start Ollama, check model name and configured URL.
- api_rag_smoke: inspect answer/evidence reports; small-model citation failures are not service success.
- malformed upstream response: HTTP 503 is intentional. Fix the backend; do not return an empty result to hide corruption.

The Week 1 stage report records scope and stage status, not remote CI status or semantic answer quality.

