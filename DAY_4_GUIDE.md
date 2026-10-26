# Day 4 — searchable papers with OpenSearch BM25

## Outcome and scope

Today you build the retrieval part of RAG. PostgreSQL holds canonical paper records; OpenSearch holds a rebuildable copy optimized for keyword ranking. FastAPI exposes POST /api/v1/search, and a terminal command lets you inspect results without starting the API.

Your Day 3 output confirmed five seeded papers, migration 0001 and repeatable seeding. Those are today's inputs. They contain authored summaries, not downloaded full papers or original abstracts. No embeddings, PDF parsing, vector database or model call is required today. /ask stays at its Day 2 placeholder behavior (501); Day 5 can connect retrieved evidence to generation.

Budget: 20 minutes reading/backup, 35 minutes services and indexing, 45 minutes code walkthrough, 30 minutes API/testing, 30 minutes debugging, 20 minutes log/commit = 3 hours. If this is a weekend, use the extra hour for experiments with title boost and queries; do not make stretch work a completion requirement.

## 1. Apply this incremental update

Stop your existing Uvicorn process with Ctrl+C first. Keep Docker Desktop running.

Download PaperLens_Day4_Update.zip to Downloads, then run:

```bash
cd "/Users/mayanktomar/Desktop/My Development/paperlense-rag"

git status --short

DAY4_EXTRACT_DIR="$(mktemp -d /tmp/paperlens-day4.XXXXXX)"
unzip "$HOME/Downloads/PaperLens_Day4_Update.zip" -d "$DAY4_EXTRACT_DIR"

rsync -avn "$DAY4_EXTRACT_DIR/paperlens-day4/" ./

DAY4_BACKUP_DIR="$(dirname "$PWD")/paperlens-day4-backup-$(date +%Y%m%d-%H%M%S)"
rsync -av --backup --backup-dir="$DAY4_BACKUP_DIR" "$DAY4_EXTRACT_DIR/paperlens-day4/" ./

uv sync --locked --dev
```

The first rsync is a preview. The second copies files, backs up overwritten files outside the repository and does not delete other files. Review any custom changes in those backups. This is an update over Day 3, not a standalone repository. Your .env, database credentials, migrations, fixture data, previous logs and PostgreSQL volume are preserved.

No Python dependency was added: the adapter uses the existing HTTPX dependency. pyproject.toml and uv.lock update the project version to 0.4.0.

## 2. Configuration and Docker services

Defaults work without editing .env. search.env.example documents optional overrides; it is not loaded automatically.

| Setting | Default | Purpose |
|---|---|---|
| RAG_SEARCH_BASE_URL | http://127.0.0.1:59200 | Python client address |
| RAG_SEARCH_INDEX | paperlens-papers-v1 | Search index name |
| RAG_SEARCH_TIMEOUT_SECONDS | 20 | Request timeout |
| RAG_SEARCH_PORT | 59200 | Compose host port |

If needed, copy individual settings into your existing .env. Do not replace .env with search.env.example: that would discard existing settings.

```bash
docker info
docker compose up -d --wait postgres opensearch
docker compose ps

curl -fsS http://127.0.0.1:59200
curl -fsS http://127.0.0.1:59200/_cluster/health

uv run --locked python -m scripts.check_db
```

If Docker is not running, launch Docker Desktop with `open -a Docker` and wait for its engine before retrying. The first OpenSearch image download/startup can take several minutes.

The Compose file preserves the Day 3 PostgreSQL service and volume. It adds OpenSearch 2.19.0, a persistent search volume, one node and a 512 MiB Java heap. Native memory is additional to that heap. Search binds only to localhost and authentication is disabled for this local exercise; this Compose setup is not for a public deployment.

PostgreSQL remains on port 55432; OpenSearch uses 59200. No Dashboards container is needed. The application index has one shard and zero replicas for a single-node exercise.

If check_db reports missing migrations or fixtures, run:
```bash
uv run --locked alembic upgrade head
uv run --locked python -m scripts.seed_papers
```

## 3. Index the five papers twice

```bash
uv run --locked python -m scripts.index_papers
uv run --locked python -m scripts.index_papers
curl -fsS http://127.0.0.1:59200/paperlens-papers-v1/_count
```

For the unchanged Day 3 fixture, both runs should print:

```text
Index complete: indexed=5, index_total=5
```

Here indexed means records submitted successfully, not newly created documents. Every paper uses its arXiv ID as the OpenSearch document ID. The second run overwrites those same documents, so the count remains five.

The indexer reads PostgreSQL in batches of 100, writes bulk NDJSON, checks every bulk operation, explicitly refreshes the index, then reads the count. A bulk request can partially succeed; failure is reported and a rerun can safely overwrite successful records. This is not an atomic transaction across PostgreSQL and OpenSearch.

Deletion synchronization is not implemented today. Removing a PostgreSQL row does not remove its search document. Likewise, changed DB records are not searchable until you rerun indexing.

## 4. Search and verify

```bash
uv run --locked python -m scripts.search_papers "Dense Passage Retrieval" --top-k 3
uv run --locked python -m scripts.search_papers "retrieval" --category cs.CL
uv run --locked python -m scripts.verify_day4
```

With only the original five papers, the verification script should finish with:
```text
PASS: stable index count=5; 3 known-paper checks, category filters and no-match behavior verified.
```

This is an early retrieval smoke evaluation: three known-source queries must include the expected paper in the top five. It also checks repeated indexing, category filtering and zero matches for a nonsense token. With five documents, top-five recall is a weak benchmark; later days should expand the corpus and add harder, independently written evaluation queries.

Ranking uses BM25 keyword relevance over title and abstract. The English analyzer tokenizes text, removes common stop words and applies stemming. The title field has boost 2; this favors title matches but does not mean twice the probability of correctness. Multiple query terms use OR. Multiple category filters use OR within the selected categories.

A high score is not a confidence probability. A query about an unknown subject can still match shared words, so this endpoint does not yet decide whether enough evidence exists to answer a question.

## 5. Start and exercise the API

Terminal A:
```bash
uv run --locked uvicorn src.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

Terminal B:
```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"Dense Passage Retrieval","top_k":3}'

curl -sS -X POST http://127.0.0.1:8000/api/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"retrieval","top_k":5,"categories":["cs.CL"]}'

curl -i -X POST http://127.0.0.1:8000/api/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"   ","top_k":3}'
```

Open http://127.0.0.1:8000/docs to try requests interactively.

Responses contain query, search_mode="bm25", total, took_ms and hits. Each hit includes arxiv_id, title, abstract, source_url, categories, text_kind and score. total counts all matching documents; hits is capped by top_k. took_ms is OpenSearch processing time, not total API/network latency.

Validation: nonblank query, maximum 4000 characters; integer top_k from 1 to 20; optional maximum 10 nonblank categories. Unexpected fields are rejected. Invalid requests return 422. A valid query with no matches returns 200 and an empty hits list. An unavailable service or missing index returns 503, rather than pretending there were no matches.

Optional outage check, with the API running:
```bash
docker compose stop opensearch
curl -i -X POST http://127.0.0.1:8000/api/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"retrieval"}'
docker compose up -d --wait opensearch
```
Expect HTTP 503 during the outage and normal results after restart. The existing health endpoint is a liveness check; it does not prove OpenSearch readiness.

## 6. Tests and persistence

```bash
uv run --locked ruff check src scripts tests
uv run --locked pytest -q
uv run --locked python -m scripts.verify_day4
docker compose restart opensearch
docker compose up -d --wait opensearch
curl -fsS http://127.0.0.1:59200/paperlens-papers-v1/_count
```

Offline validation of the merged Day 1–4 code passed: 51 tests and Ruff. The existing Starlette/HTTPX deprecation warning remains nonfatal. The offline suite covers query construction, validation, mocked transport failures, bulk item failure detection, stable document IDs, API statuses and database-to-index batching.

Live Docker/PostgreSQL/OpenSearch verification was not available in the packaging environment; run the live commands above on your Mac. A separate GitHub Actions search workflow is included to run migrations, fixtures and live retrieval checks on Linux. Its result must be confirmed after pushing.

Expected persistence check: count remains five after restart. Do not run `docker compose down -v`: that deletes the project volumes, including PostgreSQL data.

## 7. Understand the code in this order

1. src/services/search/settings.py: validates search configuration independently of model settings.
2. src/services/search/index_definition.py: declares searchable text fields, exact keyword fields and a schema marker.
3. src/services/search/query.py: translates your validated request to an OpenSearch query; title boost, filters and deterministic ID tie-breaks live here.
4. src/services/search/client.py: owns HTTP calls, bulk writes, mapping checks, refresh, count and response validation. Converts expected backend problems into SearchServiceError.
5. src/services/search/indexer.py: reads canonical database rows and sends bounded batches to the adapter.
6. src/schemas/api/search.py and src/routers/search.py: define the public contract, manage the client lifetime and map backend failures to 503.
7. scripts/index_papers.py, scripts/search_papers.py, scripts/verify_day4.py: operational commands and the early evaluation.
8. tests/test_search.py: executable examples of expected behavior and failures.

Data flow: indexing copies records from PostgreSQL into OpenSearch. At query time, the API searches OpenSearch and returns ranked evidence. It does not call PostgreSQL or Ollama for each search. This split lets us rebuild search data from canonical records and later compare other retrieval strategies.

An existing index is reused only when its schema marker matches. The code will not silently delete an incompatible index. This marker is a basic guard, not a full migration system.

## 8. Troubleshooting

- Docker HTTP 500 / missing engine: restart Docker Desktop normally, confirm docker info includes Server, then retry the project services. Do not reset Docker or delete all containers.
- Slow startup or exit code 137: inspect `docker compose logs --tail=100 opensearch` and Docker Desktop resource usage. You already run other containers; pause only workloads you recognize and do not need.
- Bootstrap vm.max_map_count error: retain the exact log message and resolve the Docker VM setting before retrying. The Linux CI workflow configures this explicitly.
- Port 59200 occupied: set RAG_SEARCH_PORT=59201 and RAG_SEARCH_BASE_URL=http://127.0.0.1:59201 in .env, recreate the service with docker compose up -d --wait opensearch, restart the API and adjust curl URLs.
- Missing index / 503: start OpenSearch and run scripts.index_papers.
- Indexed zero papers: verify database configuration, migration and seed; the indexer intentionally does not seed data.
- Different schema error: use a new index name such as paperlens-papers-v2 in .env, index it, and restart the API. Keep the previous index until you intentionally clean it up.
- No hits: check that indexing completed, inspect the CLI query, and avoid stop-word-only queries. Category names match exactly.
- Unexpected count above five: inspect whether you previously indexed extra records. Upsert does not delete stale documents.
- Failed bulk operation: read the failed IDs, fix the source/mapping issue, then rerun indexing. Never equate HTTP 200 alone with complete bulk success.

## 9. Record, commit and push

Fill in docs/day-04-log.md with your actual results and one thing you learned. Note any live checks you did not run.

```bash
git diff --check
git status --short
git diff --stat

git add compose.yml pyproject.toml uv.lock search.env.example DAY_4_GUIDE.md
git add src/main.py src/routers/ping.py src/routers/search.py
git add src/schemas/api/search.py src/services/search
git add scripts/index_papers.py scripts/search_papers.py scripts/verify_day4.py
git add tests/test_api.py tests/test_search.py docs/day-04-log.md
git add .github/workflows/search.yml

git diff --cached --stat
git commit -m "feat: index papers and expose BM25 search"
git push
```

These commands assume the GitHub upstream from your earlier days is configured. If it is not, use `git push -u origin "$(git branch --show-current)"` after confirming origin is your repository. The explicit staging list does not include .env or local backups. If earlier Day 3 changes are still uncommitted, review and commit that completed work separately.

Core acceptance: services healthy, five indexed records, repeated indexing preserves count, three known-source checks pass, category/no-match behavior works, valid search 200, blank query 422, backend failure 503, lint/tests pass and commit pushed.

Stretch only: add more labeled queries, experiment with title weighting, inspect an OpenSearch explain response. Record observations; do not present five-fixture checks as evidence of production retrieval quality.

Interview explanation: "I kept PostgreSQL as the source of truth, built a repeatable bulk indexer using stable paper IDs, and exposed a validated BM25 search API. I tested service failures separately from no-match results and added a small known-source retrieval evaluation. The current index is a rebuildable copy; deletion synchronization and stronger retrieval evaluation remain future work."

References:
- https://docs.opensearch.org/docs/2.19/query-dsl/full-text/multi-match/
- https://docs.opensearch.org/latest/install-and-configure/install-opensearch/docker/
- https://docs.opensearch.org/latest/api-reference/document-apis/bulk/

