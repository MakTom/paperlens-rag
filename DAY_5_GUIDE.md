# Day 5 — your first end-to-end RAG baseline

## What you build and why

Today connects Day 4 retrieval to the Day 1 Ollama client through the Day 2 question API. PostgreSQL contains canonical records; OpenSearch ranks searchable copies; Ollama generates an answer from supplied excerpts. No new Python packages, database migrations, index changes or Docker services are required.

This update assumes Days 1–4 are applied. Day 4 live success has not been confirmed in this chat: run its verification before debugging generation.

Learning objectives:
- Explain retrieval versus generation and why retrieval comes first.
- Construct a small, inspectable evidence context.
- Map model citation labels back to trusted source metadata.
- Distinguish no evidence, model abstention, bad reference formatting and service failure.
- Evaluate plumbing separately from factual grounding.

Three-hour schedule: 20 minutes apply and prerequisites; 40 minutes read code; 35 minutes first live answer; 30 minutes evaluation and manual review; 35 minutes debugging; 20 minutes log, commit and push. Weekend extra hour: test paraphrases and unsupported questions.

## 1. Apply over Day 4

Stop Uvicorn with Ctrl+C. Download PaperLens_Day5_Update.zip to Downloads.

```bash
cd "/Users/mayanktomar/Desktop/My Development/paperlense-rag"
git status --short

DAY5_EXTRACT_DIR="$(mktemp -d /tmp/paperlens-day5.XXXXXX)"
unzip "$HOME/Downloads/PaperLens_Day5_Update.zip" -d "$DAY5_EXTRACT_DIR"

rsync -avn "$DAY5_EXTRACT_DIR/paperlens-day5/" ./
DAY5_BACKUP_DIR="$(dirname "$PWD")/paperlens-day5-backup-$(date +%Y%m%d-%H%M%S)"
rsync -av --backup --backup-dir="$DAY5_BACKUP_DIR" \
  "$DAY5_EXTRACT_DIR/paperlens-day5/" ./

uv sync --locked --dev
```

The first rsync previews the update. The second backs up replaced files outside the repository. No files are deleted. Your .env, Compose file, database records, migrations and search index remain in place. Review custom edits in backed-up files. Commit any unfinished Day 4 changes separately before recording your Day 5 commit.

Project version becomes 0.5.0. Dependency versions remain unchanged; the lock updates only the root project version.

## 2. Confirm retrieval and the model independently

```bash
docker compose up -d --wait postgres opensearch
uv run --locked python -m scripts.check_db
uv run --locked python -m scripts.verify_day4

ollama list
uv run --locked python -m scripts.check_config
uv run --locked python -m scripts.smoke_llm
```

Ollama is a local Mac application/service, not a Python package inside .venv. Start the Ollama app, or run `ollama serve` in a separate terminal if you use its CLI service. Do not start a second server if one is already listening.

If your configured model is the original default and it is missing:
```bash
ollama pull llama3.2:1b
```

If .env selects another model, pull that model instead. Keep the default small model for the first attempt. This exercise does not automatically download or switch models. A small model may fail citation formatting or abstention; record that behavior honestly.

If PostgreSQL is empty, migrate and seed using Day 3 instructions. verify_day4 indexes records itself. A failing retrieval check must be resolved before expecting useful answers.

## 3. Start the API and ask a question

Terminal A:
```bash
uv run --locked uvicorn src.main:create_app \
  --factory --reload --host 127.0.0.1 --port 8000
```

Terminal B:
```bash
cd "/Users/mayanktomar/Desktop/My Development/paperlense-rag"
uv run --locked python -m scripts.ask \
  "How does Dense Passage Retrieval represent questions and passages?"
```

Equivalent HTTP request:
```bash
curl -sS --max-time 650 -X POST http://127.0.0.1:8000/api/v1/ask \
  -H 'Content-Type: application/json' \
  -d '{"query":"How does Dense Passage Retrieval represent questions and passages?","top_k":3}'
```

Interactive API: http://127.0.0.1:8000/docs

An illustrative successful answer might say: "Dense Passage Retrieval uses two encoders to learn representations of questions and passages. [S1]" The actual wording and source label depend on retrieval and the model. This example is not a captured live result.

## 4. Understand the response

| Field | Meaning |
|---|---|
| status | answered, no_evidence, insufficient_evidence or invalid_citations |
| answer | Model text only when reference checks pass; otherwise an application message |
| sources | URLs for cited evidence, assembled from indexed metadata |
| cited_ids | Unique labels in first-citation order, such as S1 |
| evidence | Exact excerpts supplied to the model, plus title, ID, URL and text provenance |
| chunks_used | Number of evidence records included in the prompt |
| search_mode | bm25 |
| query | Validated question |

Today one evidence record is a paper summary, not a PDF chunk. chunks_used retains the existing API field name. It counts supplied excerpts, including those the model did not cite. sources contains only cited records, so its length can be smaller.

top_k controls how many search hits are requested (1–20); the prompt includes at most the first three distinct usable hits. Each excerpt is capped at 1200 characters and each title at 300 characters. truncated tells you when an excerpt was shortened. These are character limits, not a tokenizer-aware context budget. The model uses num_ctx=8192 and num_predict=256; arbitrary future multilingual text may need stricter token budgeting.

All five starter records are authored_summary. Answers are grounded in those supplied summaries, not verified full-paper text.

## 5. Code walkthrough

Read these files in order:

1. src/schemas/api/ask.py: keeps the request fields and extends the answer with status, evidence and citation IDs.
2. src/services/rag.py: the orchestration layer. Calls retrieval, deduplicates and bounds excerpts, builds a JSON prompt, calls generation and checks citation IDs.
3. src/services/ollama.py: reuses HTTPX and the configured model. Adds a system prompt, a larger output budget, explicit context size and a check for output-limit truncation.
4. src/services/interfaces.py: a small generator protocol, now accepting an optional system prompt. Existing generate(prompt) calls still work.
5. src/routers/ask.py: wires search, model and configuration together; converts backend errors into HTTP 503.
6. scripts/ask.py: a terminal client for the running API.
7. scripts/verify_day5.py and fixtures/day5-evaluation.json: a four-case live smoke evaluation with a saved report.
8. tests/test_rag.py: offline coverage using fake retrieval/model services and mocked HTTP responses.

Request flow:
- Validate input.
- Retrieve BM25 hits from OpenSearch.
- Select up to three distinct nonempty excerpts.
- If there are none, return no_evidence without calling Ollama.
- Otherwise send the question and evidence as JSON data, alongside separate system instructions.
- Accept the exact INSUFFICIENT_EVIDENCE sentinel as model abstention.
- Otherwise require at least one valid square-bracket source label and reject unknown or malformed labels.
- Build returned source URLs from indexed metadata, never from model-generated links.

JSON encoding and system instructions reduce accidental mixing of instructions and document text. They do not guarantee resistance to prompt injection. This is a local baseline with curated fixtures.

The citation checker does NOT prove that every sentence is supported or even cited. It validates label syntax and membership only. A false claim followed by [S1] can still pass. This is why manual review is part of acceptance.

The service does not enforce a universal BM25 threshold: scores are query-dependent and not calibrated confidence. A question can retrieve irrelevant papers through shared words. Model abstention helps, but is not guaranteed.

## 6. Expected behavior and error handling

| Input or condition | HTTP | Result |
|---|---|---|
| Supported answer with valid citation labels | 200 | status=answered |
| No usable retrieved excerpts | 200 | status=no_evidence; no model call |
| Model returns exact abstention sentinel | 200 | status=insufficient_evidence |
| Missing, unknown or malformed citations | 200 | status=invalid_citations; raw answer withheld |
| Search/model unavailable, timeout or truncated generation | 503 | Actionable detail |
| Invalid request | 422 | Validation error |
| use_hybrid=true | 501 | Explicitly unsupported |
| model differs from configured model | 422 | Change .env and restart to switch |

Request model may be omitted or equal RAG_OLLAMA_MODEL. No arbitrary per-request switching is implemented. Backend failure is not represented as "no evidence."

Try no matches:
```bash
uv run --locked python -m scripts.ask "zzzxqvnonexistentfixturetoken"
```

Try a question the fixture cannot support:
```bash
uv run --locked python -m scripts.ask "What exact benchmark score did BART achieve?"
```

The second question is a manual negative test: retrieval may find BART, but its summary contains no score. Desired behavior is abstention. If the model invents a score, record a grounding failure even if its citation is syntactically valid.

## 7. Run offline and live evaluation

```bash
uv run --locked ruff check src scripts tests
uv run --locked pytest -q
uv run --locked python -m scripts.verify_day5
```

The first two commands need neither Docker nor Ollama. The merged Day 1–5 code passed 76 offline tests in the preparation environment. Ruff and the offline lock consistency check also passed. The existing Starlette/HTTPX deprecation warning remains nonfatal.

Live OpenSearch/Ollama evaluation was not run in that environment. Run it on your Mac with the API and services active. No live model quality or latency result is claimed.

The evaluation checks:
- DPR question cites the expected paper.
- BART question cites the expected paper.
- Transformer question cites the expected paper.
- A nonsense-token query returns no evidence.

It saves a timestamped report under reports/local/, excluded by your Day 1 .gitignore. Reports include answers, evidence, elapsed API time and manual_grounding_review="pending". Do not mistake PASS for a factual-quality score: structural checks require the expected paper to be cited but do not assess entailment. With only five fixtures, this is a smoke set, not a general benchmark.

Read every answer in the report. For each:
1. Locate its cited source and exact excerpt.
2. Check every factual claim against that excerpt.
3. Note invented details, irrelevant evidence and missing sentence-level citations.
4. Record a pass/fail and reason in docs/day-05-log.md.
5. Record the unsupported BART-score experiment separately.

First-call latency can include model loading. Later calls may be faster. Temperature zero reduces sampling variation but does not promise bit-for-bit reproducibility. Record the model name and local ID from ollama list.

Existing CI runs offline tests; the Day 4 workflow checks live retrieval. This update does not add model downloads to CI. Live generation remains a local evaluation.

## 8. Debugging checklist

- 503 cannot connect to Ollama: start the app/server and check RAG_OLLAMA_BASE_URL.
- Model missing: compare ollama list with scripts.check_config; pull the configured model.
- Search missing/down: rerun Day 4 verification and inspect docker compose logs --tail=100 opensearch.
- Generation timeout: close unneeded workloads, keep top_k=3, try a narrow question. You may increase RAG_REQUEST_TIMEOUT_SECONDS up to 600 in .env, then restart the API. This is an HTTPX operation timeout, not a hard total request deadline.
- Output limit reached: ask a narrower question. Do not accept a cut-off answer as complete.
- invalid_citations: inspect evidence and ask a focused question. Repeated failures may be a small-model limitation; log them. Do not weaken checks simply to make a test pass.
- Unsupported factual detail with valid citations: treat it as a quality failure. Add the case to your log; citation validation is not semantic verification.
- Stale 501 for a normal question: stop the old server, confirm the update was applied to the correct repo and restart. Health should show version 0.5.0.
- Tests show the old "not implemented" expectation: ensure the updated tests/test_api.py was copied.
- No matches while services are healthy: verify corpus content and query terms. Do not silently fall back to a general LLM answer.
- Network-free tests fail with a socket assertion: preserve the offline guard and inspect dependency overrides; do not disable it to hide accidental live calls.

## 9. Finish and push

Fill docs/day-05-log.md with actual results. A failed generation case is useful evidence; record it and debug before claiming acceptance.

```bash
git diff --check
git status --short

git add pyproject.toml uv.lock DAY_5_GUIDE.md
git add src/main.py src/routers/ping.py src/routers/ask.py
git add src/schemas/api/ask.py src/services/rag.py
git add src/services/ollama.py src/services/interfaces.py
git add scripts/ask.py scripts/verify_day5.py
git add fixtures/day5-evaluation.json
git add tests/test_api.py tests/test_rag.py docs/day-05-log.md

git diff --cached --stat
git commit -m "feat: connect BM25 retrieval to cited RAG answers"
git push
```

If your branch has no upstream, first confirm origin is your repository, then use:
```bash
git push -u origin "$(git branch --show-current)"
```

Do not stage .env or local reports containing private questions. The explicit staging commands above include only this update.

Core acceptance: Day 4 retrieval passes; lint and 76 tests pass; at least one live source-referenced answer is produced; the four structural cases pass; manual review and the unsupported-question result are recorded honestly; code is committed and pushed. Any remaining grounding failure stays documented as a baseline limitation.

Stretch only: five new paraphrased evaluation questions, comparison of warm/cold latency, or a second already-installed model. Do not add PDF parsing, embeddings, reranking or a UI today.

Interview explanation: "I built a BM25 RAG baseline with bounded evidence excerpts, an Ollama generation adapter and traceable source labels. I distinguished no-match results from service failures, checked citation IDs programmatically and manually reviewed grounding. My first evaluation set is deliberately small, so I report it as a smoke test rather than a quality benchmark."

Ollama API reference: https://docs.ollama.com/api/generate

