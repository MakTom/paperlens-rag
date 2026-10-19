# PaperLens — Day 2 update
This ZIP is an incremental update for your existing Day 1 repository, including your folder named paperlense-rag. It is not a standalone project.

## Goal (3 hours)
Create a running FastAPI application, define the question/answer contract, verify input validation, and automate offline tests on GitHub.
- 25 minutes: read this guide and schemas.
- 65 minutes: merge files, install dependencies, run and inspect the API.
- 50 minutes: study and run tests; try invalid requests.
- 40 minutes: record results, review changes and push.

Ollama and Docker do not need to run for Day 2. If the Day 1 real model smoke check remains unfinished, keep it as an explicit pending item.

## Apply this update
1. Extract the ZIP into Downloads. It contains a folder named paperlens-day2.
2. Open Terminal in your existing repository (the folder containing your .git, .env and src/config.py).
3. Use the commands below. Adjust the source path if the extraction location differs.

First preview:
```bash
rsync -avn "$HOME/Downloads/paperlens-day2/" ./
```
Then merge, saving replaced files outside the repository:
```bash
rsync -av --backup --backup-dir="$PWD/../paperlens-day2-backup-$(date +%Y%m%d-%H%M%S)" "$HOME/Downloads/paperlens-day2/" ./
```
This merges individual files, including the hidden .github folder. It does not delete existing files. Do not replace the whole src folder in Finder.

The update replaces pyproject.toml and uv.lock and adds the files listed below. Your .env, .env.example, .gitignore, src/config.py, Day 1 Ollama client, scripts, README and existing daily log are not included and remain intact. If you customized pyproject.toml, review its backup and carry those changes forward deliberately before re-locking.

## Install and run
From your existing project root:
```bash
uv sync --locked --dev
uv run --locked ruff check src scripts tests
uv run --locked pytest -q
uv run --locked uvicorn src.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```
Keep the server Terminal open. Open http://127.0.0.1:8000/docs in your browser.

In another Terminal:
```bash
curl http://127.0.0.1:8000/api/v1/health
```
Expected JSON (app_name uses your .env):
```json
{"status":"ok","app_name":"paperlens-rag","version":"0.2.0","scope":"api_only"}
```

Test a valid question:
```bash
curl -i -X POST http://127.0.0.1:8000/api/v1/ask \
  -H 'Content-Type: application/json' \
  -d '{"query":"What is RAG?","top_k":5}'
```
**Expected: HTTP 501**, with a message that generation arrives on Day 5. This is an explicit temporary scaffold; it does not generate or fabricate an answer.

Test invalid input:
```bash
curl -i -X POST http://127.0.0.1:8000/api/v1/ask \
  -H 'Content-Type: application/json' \
  -d '{"query":"   ","top_k":0}'
```
**Expected: HTTP 422**, containing validation errors. FastAPI rejects the request before the endpoint runs.

Stop the development server with Control+C.

## What each new file does
| File | Purpose |
|---|---|
| src/main.py | create_app builds an isolated FastAPI application and registers routers |
| src/dependencies.py | Supplies the app's settings using FastAPI dependency injection |
| src/routers/ping.py | GET /api/v1/health confirms the API process is responding |
| src/routers/ask.py | Validates incoming questions and explicitly returns 501 until Day 5 |
| src/schemas/api/ask.py | Defines allowed question fields and future answer fields |
| src/schemas/api/health.py | Defines the health response structure |
| src/services/interfaces.py | Protocol describing a text generator; existing OllamaClient already fits it |
| tests/conftest.py | Supplies a test app and blocks external socket connections |
| tests/test_api.py | Checks 200/422/501/404 behavior, defaults and OpenAPI contracts |
| .github/workflows/ci.yml | Installs dependencies, lints and tests on pushes/pull requests |
| pyproject.toml / uv.lock | Adds FastAPI, Uvicorn, pytest and Ruff; locks resolved versions |
| docs/day-02-log.md | Records your actual progress without replacing Day 1's log |

## Concepts to understand
- **FastAPI:** turns functions into HTTP endpoints and uses schemas for validation.
- **Uvicorn:** serves your FastAPI application over HTTP.
- **Router:** groups related endpoints, such as health or questions.
- **Schema:** defines acceptable input and the planned response shape. Unknown fields are rejected; top_k must be an integer 1–20, query must contain text.
- **Dependency injection:** the health function receives validated settings from the current app. Tests can create an app with explicit test settings without editing .env.
- **Factory:** create_app returns a new app instance. That is why the launch command includes --factory.
- **Protocol:** describes required methods without requiring inheritance. OllamaClient has generate(prompt) and satisfies TextGenerator structurally; no provider is invoked by today's endpoints.
- **Liveness:** /health checks this API only. It makes no claim about Ollama or database readiness.
- **TestClient:** exercises HTTP behavior in-process without starting Uvicorn.
- **CI:** GitHub runs the same checks after a push. Dependency installation requires internet; test execution needs no external model/database credentials.
- **Day 2 contract:** AskResponse appears in OpenAPI as the future successful response, while this day's valid requests intentionally return 501.

## Acceptance checks
- [ ] Locked install succeeds.
- [ ] Ruff passes.
- [ ] 18 offline tests pass.
- [ ] /health returns 200 and identifies api_only scope.
- [ ] /docs displays the request and response schemas.
- [ ] Invalid question returns 422.
- [ ] Valid question explicitly returns 501.
- [ ] .github/workflows/ci.yml is visible in git status.
- [ ] GitHub Actions passes after pushing.

## Commit and push
Complete docs/day-02-log.md, then:
```bash
git status --short
git add pyproject.toml uv.lock src/main.py src/dependencies.py \
  src/routers src/schemas src/services/interfaces.py tests \
  .github/workflows/ci.yml docs/day-02-log.md DAY_2_GUIDE.md
git diff --cached --stat
git diff --cached
git commit -m "feat: add API contracts health checks and offline CI"
git push
```
Use your existing repository and remote; do not git init again. If the branch has no upstream, use git push -u origin followed by your actual branch name. In GitHub, open Actions to view the run.

## Troubleshooting
- Import error for src.config: you applied the update outside the Day 1 project. Merge it into the existing repository.
- Address already in use: choose --port 8001 and update browser/curl URLs.
- A local modification causes Ruff to fail: read its file/line report and fix that specific issue before committing.
- CI workflow not appearing: verify the hidden .github folder was merged and committed.
- 501 from /ask: expected today. Do not change the test to accept generic 500 errors.
- Server starts but no Ollama response: today's API does not call Ollama. Use the Day 1 smoke script for that separate check.

## Validation before delivery
The update was merged into an isolated copy of the original Day 1 Python modules and checked on Python 3.12/Linux. Mac execution and GitHub-hosted CI still need your checks.

## References
https://fastapi.tiangolo.com/tutorial/testing/
https://docs.astral.sh/uv/guides/integration/github/

Next: Day 3 adds PostgreSQL and repeatable paper seed data.

