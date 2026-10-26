# Day 4 — Keyword retrieval
Status: code prepared; local service checks and push pending.

Record actual results:
- Date / time spent:
- PostgreSQL and OpenSearch healthy:
- Source paper count:
- First index result:
- Second index result:
- Known-paper search result:
- Live verification:
- Search API 200 / invalid input 422 / service-down 503:
- Restart persistence:
- Offline tests and lint:
- GitHub workflows:
- Blockers / decisions:

Decisions:
- PostgreSQL remains canonical storage.
- OpenSearch holds a derived copy of each paper record.
- BM25 searches title (boosted) and abstract; no embeddings or LLM call yet.
- Fixture abstracts remain labeled authored_summary.
- The arXiv ID is also the OpenSearch document ID.
- Reindexing updates existing IDs and adds new ones; it does not remove stale records.
