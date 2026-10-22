# PaperLens — Day 3: PostgreSQL, migrations and repeatable seed data

## What you will finish today
By the end of this session, five paper records will be stored in PostgreSQL. Running the seed command again will leave the count unchanged. Restarting the database container will preserve the records. Your Day 2 API and tests continue to work.

Time budget: 3 hours.
- 20 minutes: understand the storage design.
- 35 minutes: apply the update, start Docker and PostgreSQL.
- 45 minutes: read the model, migration and repository; migrate and seed.
- 40 minutes: offline checks, repeat seed, rollback check and restart persistence check.
- 40 minutes: troubleshooting, record results, commit and inspect CI.

This update builds on Day 1 and Day 2. It does not need Ollama running. There is no search index or new paper API endpoint yet; Day 4 adds keyword retrieval. /ask still intentionally returns 501.

## 1. Apply the ZIP from Downloads
In your existing project Terminal:
```bash
cd "/Users/mayanktomar/Desktop/My Development/paperlense-rag"
ls src/config.py src/main.py pyproject.toml
git status --short
```
The three files must exist. If you have unfinished changes, review/commit them first or retain them with the backup below.

Extract to a fresh temporary directory:
```bash
DAY3_EXTRACT_DIR="$(mktemp -d /tmp/paperlens-day3.XXXXXX)"
unzip "$HOME/Downloads/PaperLens_Day3_Update.zip" -d "$DAY3_EXTRACT_DIR"
```
Preview:
```bash
rsync -avn "$DAY3_EXTRACT_DIR/paperlens-day3/" ./
```
Apply with backup:
```bash
DAY3_BACKUP_DIR="$(dirname "$PWD")/paperlens-day3-backup-$(date +%Y%m%d-%H%M%S)"
rsync -av --backup --backup-dir="$DAY3_BACKUP_DIR" \
  "$DAY3_EXTRACT_DIR/paperlens-day3/" ./
```
The update replaces pyproject.toml and uv.lock. It adds compose.yml, database files, migrations, fixtures, scripts, tests, a PostgreSQL CI workflow and this guide. It does not overwrite .env, src/config.py, Day 1's Ollama client, the Day 2 API, your existing CI workflow or daily logs. If you previously customized a same-named file, compare its backup before proceeding.

## 2. Install dependencies
```bash
uv sync --locked --dev
```
New direct dependencies:
- SQLAlchemy: models, SQL statements, connections and transactions.
- psycopg[binary]: PostgreSQL driver, with a prebuilt implementation to avoid compiling libpq locally.
- Alembic: versioned database schema changes.

Docker runs PostgreSQL; your uv virtual environment runs Python and the driver. PostgreSQL is not installed inside .venv.

The existing Rosetta Python environment can attempt this install. If uv reports a missing wheel, send that error; do not install an ARM Python into the existing x86 virtual environment. We can rebuild the environment with a native ARM interpreter if needed.

## 3. Start Docker Desktop
```bash
open -a Docker
```
Wait until Docker Desktop reports it is running, then:
```bash
docker info
docker compose version
```
If docker info cannot connect, wait for Docker Desktop to finish starting before continuing.

Start only PostgreSQL:
```bash
docker compose up -d --wait postgres
docker compose ps
```
Expected: the postgres service is running and healthy. The first run downloads the image.

The Compose file uses PostgreSQL 16's official Alpine image. The major version is fixed; the image's minor/patch release can advance with the tag. This is a local learning setup, not a production deployment.

### Connection defaults
| Setting | Value | Reason |
|---|---|---|
| Host | 127.0.0.1 | Python runs directly on your Mac |
| Mac port | 55432 | Avoids the usual 5432 port used by other projects |
| Container port | 5432 | PostgreSQL's internal listener |
| Database | paperlens | This project's data |
| User | paperlens | Local development account |
| Password | paperlens_local_only | Public tutorial credential for localhost only |

These defaults are shared by Compose and DatabaseSettings, so no .env edit is required. database.env.example documents optional overrides; it is not automatically loaded. If you customize a value, add it to your existing .env without removing the Ollama entries.

Compose's connection is bound to 127.0.0.1. Do not reuse these credentials for a publicly exposed database. Environment variables exported in your shell override .env values; mismatched settings can cause connection failures.

PostgreSQL initializes credentials on its first use of the volume. Editing the password later does not change the already-created database user's password automatically.

## 4. Create the database schema
```bash
uv run --locked alembic upgrade head
uv run --locked alembic current
uv run --locked alembic check
```
Expected revision: 0001 (head). The check should report no new upgrade operations.

What happens:
1. Alembic loads migrations/env.py.
2. That file builds the SQLAlchemy engine using your DB settings.
3. Alembic runs 0001_create_papers.py if it has not already run.
4. PostgreSQL creates papers and Alembic tracks the applied revision in alembic_version.

Running upgrade head again should be safe: the applied migration is not repeated.
We deliberately do not create tables automatically when the API starts.

## 5. Insert the fixed corpus
```bash
uv run --locked python -m scripts.seed_papers
```
On an empty database:
```text
Seed complete: inserted=5, skipped=0, total=5
```
Run exactly the same command again:
```bash
uv run --locked python -m scripts.seed_papers
```
Expected:
```text
Seed complete: inserted=0, skipped=5, total=5
```

If you already have other papers, total may be greater than five. The important checks are zero inserted on the second run and an unchanged total.

### What is in the corpus?
Real arXiv IDs and titles for:
- Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks
- Attention Is All You Need
- BERT
- Dense Passage Retrieval
- BART

The short text in each abstract field is an original tutorial summary, explicitly marked text_kind=authored_summary. It is NOT a downloaded or verbatim paper abstract. The source_url links to the real paper. Live ingestion of source abstracts arrives later.

The fixture is checked into Git, making future baseline retrieval repeatable without an arXiv network call.

## 6. Inspect the records
```bash
uv run --locked python -m scripts.check_db
```
Expected first line:
```text
PASS: PostgreSQL reachable; migration=0001; papers=5
```
The command also lists IDs, titles and text_kind.

To inspect PostgreSQL directly using the installed psql inside the container:
```bash
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT arxiv_id, title, text_kind FROM papers ORDER BY arxiv_id;"'
```
This uses the container's configured username/database and does not require psql installed on your Mac.

## 7. Verify transactions and repeated execution
```bash
uv run --locked python -m scripts.verify_day3
```
This live check:
- Seeds the fixture twice.
- Confirms the second run inserts nothing and count is unchanged.
- Checks that creation timestamps do not change.
- Temporarily edits one title inside a transaction, rolls it back, and verifies the original title remains.

Expected:
```text
PASS: 5 fixture IDs present; second seed inserted=0; rollback verified.
```
It inserts missing fixture rows but does not delete existing papers or change committed titles.

## 8. Verify persistence after restart
```bash
docker compose restart postgres
docker compose up -d --wait postgres
uv run --locked python -m scripts.check_db
```
Expected: the same five fixture records still exist.

Why: PostgreSQL writes to the named Docker volume paperlens_postgres_data, whose Compose-managed name is normally prefixed by the project name. A container restart preserves that volume.

At the end of your session, stop the service with:
```bash
docker compose stop postgres
```
Start it again with compose up -d --wait postgres. Do not use docker compose down -v unless you intentionally want to delete the project's database volume.

## 9. Run offline checks
```bash
uv run --locked ruff check src scripts tests migrations
uv run --locked pytest -q
```
Expected: lint passes, 27 tests pass. The existing Starlette/httpx deprecation warning may still appear. It is separate from the database tests.

These tests do not need PostgreSQL or Ollama. They verify the API contracts from Day 2 plus:
- Fixture size, uniqueness and source labels.
- Rejection of duplicate input IDs.
- Rejection of invalid paper data.
- SQL compilation includes ON CONFLICT protection and RETURNING.
- The model declares the arXiv ID as its primary key.

Offline SQL compilation is not proof of live database behavior. Steps 4–8 and the new CI job cover that.

## How the code is organized
| File | Responsibility |
|---|---|
| compose.yml | Local PostgreSQL, healthcheck and persistent volume |
| database.env.example | Optional DB settings template |
| src/db/settings.py | Validated DB settings, password masking, safe URL creation |
| src/db/session.py | Declarative base and connection-engine creation |
| src/models/paper.py | Python representation of the papers table |
| src/schemas/paper.py | Validates input before it reaches storage |
| src/repositories/paper.py | Insert-if-missing, count and list queries |
| migrations/versions/0001_create_papers.py | Explicit table creation and reverse operation |
| migrations/env.py | Connects Alembic to model metadata and database |
| alembic.ini | Locates migrations |
| fixtures/papers.seed.json | Versioned, fixed corpus |
| scripts/seed_papers.py | Validate all records, then insert in one transaction |
| scripts/check_db.py | Read-only connectivity, migration and data inspection |
| scripts/verify_day3.py | Live idempotency and rollback checks |
| tests/test_persistence_contracts.py | Offline validation and SQL contract tests |
| .github/workflows/postgres.yml | Live PostgreSQL checks on GitHub |
| docs/day-03-log.md | Your execution evidence and decisions |

## Read the core code in this order

### A. DatabaseSettings
Inherits BaseSettings, like your Day 1 configuration. The prefix RAG_DB_ maps host to RAG_DB_HOST, port to RAG_DB_PORT, and so on.

SecretStr masks the password when the settings object is displayed. It does not encrypt the password. get_secret_value() retrieves it for the driver.

URL.create builds the connection URL safely from separate values, including passwords with special characters. We avoid hand-concatenating passwords into a string.

### B. Engine, Base and Session
build_engine creates a SQLAlchemy engine: a connection/pooling manager. Creating the engine does not itself create the papers table.
pool_pre_ping checks pooled connections before reuse. connect_timeout bounds connection setup; statement_timeout bounds individual SQL statements.

Base is the parent of your ORM models. Its metadata describes the tables Alembic compares against the database.
A Session manages ORM operations and a transaction; it is not the same thing as the engine.

### C. Paper versus PaperInput
PaperInput is a Pydantic schema for validating incoming data.
Paper is a SQLAlchemy model mapping valid records to database columns.

The distinction:
- Input schema: is the value acceptable to this application?
- Database schema: how is it stored and what constraints does storage enforce?

arxiv_id is a primary key. PostgreSQL enforces uniqueness even if two processes insert the same ID simultaneously. A pre-insert Python count alone would not provide that guarantee.

categories is JSON. created_at is a timezone-aware timestamp populated by the database.

### D. Insert-if-missing
The repository builds a PostgreSQL INSERT with:
ON CONFLICT (arxiv_id) DO NOTHING
RETURNING arxiv_id

If insertion succeeds, PostgreSQL returns the ID; the method returns True.
If the ID already exists, PostgreSQL skips it; no ID is returned and the method returns False.

Repeated seeding is idempotent for the fixed corpus: it creates missing rows without duplicating or updating existing rows. Editing a fixture and rerunning does NOT update an existing paper. Later ingestion will implement deliberate update/version handling.

### E. Transactions
The seed command first parses and validates the complete input.
Then:
```python
with Session(engine) as session, session.begin():
    ...
```
If all database operations succeed, the transaction commits.
If an insert fails, the transaction rolls back.
This avoids a partially inserted fixture after a mid-run failure.
The repository does not commit by itself; the caller owns the transaction boundary.

### F. Migrations
A migration is a versioned change to database structure. Changing a Python model alone does not change the actual table. You must introduce and run a migration.
upgrade() creates the table. downgrade() removes it and would delete its records; you do not need to run downgrade for today's acceptance checks.
alembic check compares metadata to the migrated schema to catch drift.

## Why PostgreSQL before search?
PostgreSQL stores the canonical paper records and provenance. Day 4 will build an OpenSearch index from those records.
This separation lets us rebuild the search index without needing to rediscover the original papers. We are not generating embeddings or storing vectors today.

## Commit and push
Complete docs/day-03-log.md with the actual output, then:
```bash
git status --short
git add pyproject.toml uv.lock compose.yml database.env.example alembic.ini \
  migrations fixtures src/db src/models src/repositories src/schemas/paper.py \
  scripts/seed_papers.py scripts/check_db.py scripts/verify_day3.py \
  tests/test_persistence_contracts.py .github/workflows/postgres.yml \
  docs/day-03-log.md DAY_3_GUIDE.md
git diff --cached --stat
git diff --cached
git commit -m "feat: persist paper metadata with repeatable seed data"
git push
```
Your existing .env remains ignored. The new database.env.example is a public development template.
Two workflows should appear in GitHub Actions:
1. Existing Offline checks.
2. New PostgreSQL checks: fresh database, migration rerun, schema consistency, seed idempotency and rollback.

## Troubleshooting
| Symptom | Likely cause / next action |
|---|---|
| Cannot connect to Docker | Start Docker Desktop; wait and rerun docker info |
| Port 55432 already allocated | Set RAG_DB_PORT=55433 in .env, then rerun compose up and Python commands |
| Connection refused | Check compose ps, port and RAG_DB_HOST |
| Authentication failed | Compare .env/shell values with first-run volume credentials; do not delete an existing volume to guess a fix |
| relation papers does not exist | Run alembic upgrade head |
| Migration revision missing | Verify migrations folder and alembic.ini were merged |
| Second seed skips 5 | Expected; primary-key conflict protection is working |
| Seed fails before DB connection | Validate fixture JSON, duplicate IDs and matching source URLs |
| API health stays ok while DB is stopped | Expected: Day 2 health is API liveness only |
| /ask returns 501 | Expected until Day 5 |
| Offline tests pass, live checks fail | Inspect Docker readiness, migration state and DB credentials |
| Need detailed PostgreSQL logs | Run docker compose logs --tail=80 postgres |

## Acceptance checklist
- [ ] Docker reports healthy PostgreSQL.
- [ ] Alembic revision is 0001; alembic check passes.
- [ ] First seed inserts five on an empty DB.
- [ ] Second seed inserts zero and count stays unchanged.
- [ ] check_db lists the five records.
- [ ] verify_day3 passes.
- [ ] Count survives restart.
- [ ] Lint and 27 offline tests pass.
- [ ] GitHub workflows pass after push.
- [ ] I can explain primary key, transaction, migration, engine and session.

## Validation and limits
Before delivery, dependency installation, lint, 27 offline tests and PostgreSQL migration SQL generation passed in Python 3.12/Linux. This environment has no usable PostgreSQL/Docker server, so real PostgreSQL migration/seed/restart checks were NOT run here. The included Mac commands and GitHub service-container job are the live acceptance checks; do not mark those complete until they actually pass.

References:
- https://docs.sqlalchemy.org/en/20/dialects/postgresql.html
- https://alembic.sqlalchemy.org/en/latest/tutorial.html
- https://hub.docker.com/_/postgres
Paper sources and provenance are in fixtures/README.md.

## Next
Day 4: derive an OpenSearch index from these records and implement BM25 keyword retrieval.

