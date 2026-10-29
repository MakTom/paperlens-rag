# Week 1 known limitations

- Five curated authored summaries, not full paper text. Labels are relative to this corpus.
- BM25 keyword retrieval only; no embeddings, reranking or semantic search.
- Five-document Recall@5 is a weak benchmark. MRR and evidence/answer review matter.
- At most three summary excerpts are supplied to generation; character caps are not token-aware budgeting.
- Citation validation checks labels, not factual support or complete sentence-level citation coverage.
- Prompt instructions and JSON formatting are not a prompt-injection security boundary.
- Small models may fail abstention, citation formatting or factual grounding. No quality improvement is claimed without measurement.
- Source updates require reindexing; upserts do not synchronize deletions.
- No application cache, streaming, authentication, distributed ingestion or multi-user guarantees.
- Liveness health does not establish backend readiness.
- Model warm state and hardware load are uncontrolled in the current evaluation.
- HTTPX timeouts are not a hard end-to-end API deadline. The verification runner has separate subprocess time limits.
- New response validation rejects malformed backend payloads as service errors. A service may be unavailable even while its process runs.
- The search response contract currently assumes no pagination/collapse and exact total hits.
- Evaluation pre/post checks are not an atomic snapshot. Do not mutate index/settings/model during a run.
- GitHub Actions checks offline behavior and containerized DB/search. Local generation and manual review are separate.
- Local Compose services are intended for localhost development, not public deployment.
- The Starlette/HTTPX deprecation warning is still present and nonfatal.

## Verified defect fixed on Day 7

Input: an OpenSearch JSON object with "_shards": null.

Before: SearchClient raised AttributeError; the expected SearchServiceError handler did not run.
After: SearchClient raises SearchServiceError; search and ask API routes return HTTP 503.
Regression tests use the real adapter with mocked HTTP and verify that generation is not called.

This is a reproduced reliability defect, not a defect selected from unavailable live Day 6 scores.

