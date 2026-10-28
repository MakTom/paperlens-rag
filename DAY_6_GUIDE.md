# Day 6 — establish a measured RAG baseline

## Goal and time budget

Day 5 connected retrieval to generation. Day 6 measures what that baseline gets right and wrong before adding full-text ingestion or embeddings. This follows the original roadmap's evaluation milestone.

Deliverables:
- 12 versioned questions: 8 supported and 4 unsupported.
- A fixed split: development has 6 supported + 2 unsupported; holdout has 2 supported + 2 unsupported.
- Recall@5, MRR@5, service errors and stage timings.
- Saved raw responses and retrieved evidence.
- A manual correctness, grounding and citation rubric.
- A baseline you can explain and compare with later versions.

Core work fits three hours: 20 minutes setup; 30 minutes learning/reading code; 30 minutes live runs; 45 minutes manual review; 35 minutes debugging; 20 minutes logging and Git. If you have four weekend hours, use the extra hour to inspect failures or repeat retrieval for reproducibility. Never mark a live run successful without running it.

There are no new Python dependencies, database migrations, Docker services or model changes. Existing Day 5 generation behavior is unchanged. API version becomes 0.6.0.

## 1. Apply over Day 5

Stop Uvicorn if running. Download PaperLens_Day6_Update.zip to Downloads.

```bash
cd "/Users/mayanktomar/Desktop/My Development/paperlense-rag"
git status --short

DAY6_EXTRACT_DIR="$(mktemp -d /tmp/paperlens-day6.XXXXXX)"
unzip "$HOME/Downloads/PaperLens_Day6_Update.zip" -d "$DAY6_EXTRACT_DIR"

rsync -avn "$DAY6_EXTRACT_DIR/paperlens-day6/" ./
DAY6_BACKUP_DIR="$(dirname "$PWD")/paperlens-day6-backup-$(date +%Y%m%d-%H%M%S)"
rsync -av --backup --backup-dir="$DAY6_BACKUP_DIR" \
  "$DAY6_EXTRACT_DIR/paperlens-day6/" ./

uv sync --locked --dev
```

The first rsync previews. The second backs up overwritten files outside your repository; it does not delete unrelated files. Existing .env, database, search index and prior code are preserved. Review any custom edits in the backups.

This is an incremental update requiring Days 1–5. Commit completed previous-day work separately if still uncommitted.

## 2. Validate the dataset without services

```bash
uv run --locked python -m scripts.evaluate --validate-only
uv run --locked ruff check src scripts tests
uv run --locked pytest -q
```

Expected label validation:
```text
PASS: 12 labels; 8 supported / 4 unsupported; 8 dev / 4 holdout; evidence verified.
```

Packaging validation: the merged Day 1–6 code passed **102 offline tests**, Ruff, dataset validation and the offline lock consistency check. Tests include mocked CLI execution; no live OpenSearch/Ollama results were measured here. The existing Starlette/HTTPX deprecation warning remains nonfatal.

The validator checks:
- Unique question IDs and required version-one counts.
- Relevant source IDs and verbatim supporting passages.
- Positive labels are permitted by each question's category filters.
- Fixture content still matches the frozen corpus fingerprint.
- Unsupported questions have an explicit reason and no false positive labels.

The labels refer to the five authored summaries from Day 3. A question may be answerable from the original paper or model memory but unsupported by this corpus. This distinction matters for evidence-only RAG.

Do not rewrite the fixture to make scores better. Keep the baseline labels and corpus fixed. Correcting a faulty label later requires a new version and a documented reason.

## 3. Verify existing services

```bash
docker compose up -d --wait postgres opensearch
uv run --locked python -m scripts.check_db
uv run --locked python -m scripts.verify_day4
ollama list
uv run --locked python -m scripts.check_config
uv run --locked python -m scripts.smoke_llm
```

Keep Ollama running locally on your Mac. If the configured model is missing, pull that exact model using the Day 5 instructions.

Unlike Day 5's API smoke script, today's runner calls the same RagService directly. Uvicorn does not need to run. This keeps retrieval/generation timing separate from HTTP API overhead. Keep the Day 5 API smoke checks for API-level verification.

Before and after evaluation, the runner reads the live search index and compares its five records to the frozen fixture. It also saves mapping/settings information. It does not seed, reindex or delete documents itself.

If you have already added extra papers, use a separate evaluation index populated with only the original fixture. Do not delete your working index to force the check to pass. This early baseline is intentionally limited to the original five records.

## 4. Run retrieval evaluation first

```bash
uv run --locked python -m scripts.evaluate --retrieval-only
```

This runs only the eight development questions and never calls Ollama. It saves a unique run report, review worksheet and Markdown summary under reports/local/.

Run it a second time if you have time:
```bash
uv run --locked python -m scripts.evaluate --retrieval-only
```

Compare Recall@5, MRR@5 and ranked IDs in the two reports. With unchanged corpus/mapping/query logic, those should agree; timing can differ.

Metric example: relevant IDs are A and B; retrieved unique IDs are X, A, Y. Recall@5 is 1/2 = 0.5, and MRR@5 is 1/2 = 0.5. Duplicate paper IDs do not earn extra credit.

With five papers, Recall@5 is a weak diagnostic. It does not mean "the RAG system is accurate." MRR, the multi-source question, prompt evidence selection and manual answer review provide additional information.

## 5. Run the full development baseline

```bash
uv run --locked python -m scripts.evaluate \
  --hardware-note "Mayank Mac; 24 GiB RAM; record current background workload in day log"
```

This performs retrieval once per question, then generates using that same result. It uses retrieval top_k=5 for the metric, while the existing RAG service includes at most three evidence excerpts.

The run can take several minutes, especially on the first model request. It prints paths like:
```text
reports/local/day6-<timestamp>-<id>.json
reports/local/day6-<timestamp>-<id>.review.json
reports/local/day6-<timestamp>-<id>.md
```

Reports include:
- Question ID, query, filters, ranked hits and exact generated response.
- Retrieval, generation and total client-side timing for each case.
- Service error types, kept separate from model abstention.
- Dataset, corpus, prompt and relevant code fingerprints.
- OpenSearch index mapping/settings and server version.
- Configured model name and local model digest.
- Python, platform, architecture, hardware note and Git state.
- Whether the corpus was stable across preflight and postflight checks.

The runner records existing generation options, not a new experiment configuration. A nonzero exit means service/preflight/postflight/report failure. Low quality is still a valid baseline result; the runner does not invent a quality threshold or treat every status=answered as success.

A passing exit code means the run completed consistently, not that its answers were correct.

## 6. Review answer quality manually

Open docs/evaluation-rubric.md and the full RAG report. For each development case, compare the answer against the exact cited excerpt and expected points in eval/questions.v1.json.

Edit only the generated .review.json worksheet:
- Enter your name in reviewer.
- Enter correctness, groundedness and citation_support as 0, 1 or 2 where applicable.
- Use appropriate_abstention for unsupported questions and actual declines.
- Keep null for unreviewed or not-applicable values, with notes explaining N/A.
- Preserve run_id and report_sha256.

Do not review a retrieval-only run as if answers were generated.

After editing, replace the example run stem below with the actual one printed by your full run:
```bash
DAY6_RUN="reports/local/day6-REPLACE-WITH-YOUR-ACTUAL-RUN-ID"

uv run --locked python -m scripts.summarize_evaluation \
  "$DAY6_RUN.json" --review "$DAY6_RUN.review.json"
```

This prints a summary with review coverage and separate supported/unsupported results. It rejects mismatched report/worksheet pairs. It does not modify the original report.

A valid citation ID proves only that a referenced source was supplied. Read the excerpt to determine whether it supports the claim. An unsupported answer with a syntactically valid [S1] remains a failure.

## 7. Preserve your measured baseline

Raw runs are saved under reports/local/, ignored by Git. Once you have reviewed a full run, preserve that exact report and worksheet under a new versioned baseline directory. Review the contents first: these fixture runs should contain only public paper summaries and your environment metadata.

```bash
mkdir -p reports/baselines
DAY6_BASELINE_DIR="reports/baselines/day06-$(date +%Y%m%d-%H%M%S)"
mkdir "$DAY6_BASELINE_DIR"

cp "$DAY6_RUN.json" "$DAY6_BASELINE_DIR/run.json"
cp "$DAY6_RUN.review.json" "$DAY6_BASELINE_DIR/review.json"

uv run --locked python -m scripts.summarize_evaluation \
  "$DAY6_BASELINE_DIR/run.json" \
  --review "$DAY6_BASELINE_DIR/review.json" \
  > "$DAY6_BASELINE_DIR/summary.md"
```

Inspect the generated summary and command exit status before staging. Never freeze a report with corpus_stable=false or unresolved service errors as a clean baseline. Keep failed runs locally for debugging.

Record results in docs/day-06-log.md. No live baseline scores are included in this ZIP because your Mac services have not been run here.

## 8. Keep holdout reserved

The default is dev. Merely running label-validation tests does not execute holdout queries. Do not inspect holdout outputs to choose prompts or model settings.

Later, after freezing the settings for a final evaluation, the explicit command is:
```bash
uv run --locked python -m scripts.evaluate --split holdout --allow-holdout
```

You do not need this command to finish Day 6. Record that the holdout was consumed when you eventually run it. Once its results influence tuning, it is no longer an untouched holdout.

## 9. Code reading order

| File | What it teaches |
|---|---|
| eval/questions.v1.json | Hand-written gold labels, evidence and split discipline |
| src/evaluation/dataset.py | Data validation and content fingerprints |
| src/evaluation/metrics.py | Paper-level ranking metrics and honest denominators |
| src/evaluation/runner.py | Timing wrappers around existing retrieval/generation |
| src/evaluation/snapshot.py | Read-only corpus verification |
| src/evaluation/report.py | Unscored worksheets, review validation and summaries |
| scripts/evaluate.py | CLI orchestration and reproducibility metadata |
| scripts/summarize_evaluation.py | Re-rendering an existing run without service calls |
| tests/test_evaluation.py | Known metric answers, failure handling and no-label-leakage tests |

The API's generation behavior and citations are unchanged today. This is deliberate: measure the existing baseline before choosing a fix. Day 7 uses the largest observed development-set defect to select work.

The corpus pre/post checks detect many accidental changes but are not a transactional snapshot across the run. Do not ingest or change settings while evaluating. Model tags/digests and fingerprints aid reproducibility; they do not guarantee identical generated text.

## 10. Troubleshooting

- Fixture hash mismatch: compare fixtures/papers.seed.json with the original Day 3 fixture. Preserve intentional corpus changes separately; do not silently relabel baseline results.
- Live index count/content mismatch: inspect the selected RAG_SEARCH_INDEX and source records. Reindexing upserts does not delete stale documents. Use a separate clean evaluation index when needed.
- Model preflight failure: start Ollama, check RAG_OLLAMA_MODEL and ollama list. Retrieval-only mode does not require Ollama.
- Service errors in rows: resolve availability/timeouts before drawing quality conclusions. Model failure preserves retrieval metrics; retrieval failure counts zero.
- invalid_citations: keep it in the baseline report as a model/output-format problem. Do not remove the case from averages.
- MRR improves but answers do not: inspect the three evidence excerpts and generated claims; retrieval ranking and generation quality are separate.
- Review hash mismatch: use the worksheet generated for that exact untouched report.
- Unsupported question answered: record whether claims were unsupported. Do not reward model memory for answering beyond evidence.
- Old health version: restart Uvicorn after applying the update, if you are also using the API.
- Slow runs: model loading and other Docker workloads affect latency; avoid calling these measurements a cold/warm benchmark.
- Existing Starlette/HTTPX warning: nonfatal; the code does not change that dependency pairing today.

## 11. Commit and push

```bash
git diff --check
git status --short

git add pyproject.toml uv.lock DAY_6_GUIDE.md
git add src/main.py src/routers/ping.py tests/test_api.py
git add src/evaluation eval/questions.v1.json
git add scripts/evaluate.py scripts/summarize_evaluation.py
git add tests/test_evaluation.py docs/evaluation-rubric.md docs/day-06-log.md

# Only after you created and reviewed this baseline directory:
git add "$DAY6_BASELINE_DIR"

git diff --cached --stat
git commit -m "feat: add retrieval and answer evaluation baseline"
git push
```

If your branch has no upstream, confirm origin is your own repository and use git push -u origin with your current branch as on previous days. No remote changes have been made by this package.

Acceptance: label validation, lint and offline tests pass; development retrieval run completes; full development report is reviewed; unsupported cases are reported separately; baseline is frozen without inventing scores; four holdout cases remain unused; commit is pushed.

Stretch only: repeat retrieval to check deterministic ranks, inspect the multi-source failure path or document warm-state observations. Do not introduce embeddings or change prompts before saving the baseline.

Interview explanation: "I separated retrieval metrics from answer quality, versioned a small labeled corpus and question set, reserved a holdout, and saved model/prompt/index fingerprints. I measured failures as well as successes and manually checked claim support because citation IDs alone do not establish grounding."

