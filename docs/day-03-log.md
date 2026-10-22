# Day 3 — PostgreSQL persistence
Status: code prepared; local PostgreSQL checks and GitHub push pending.

Record actual results:
- Date / time spent:
- Docker healthy:
- Migration revision:
- First seed result:
- Second seed result:
- Count after restart:
- Live verification:
- Lint / offline tests:
- GitHub Actions:
- Blockers / decisions:

Decisions:
- PostgreSQL is the canonical store; a search index will be derived from it on Day 4.
- Seed text is labeled authored_summary; it is not a verbatim source abstract.
- arXiv ID is unique at database level.
- Repeated seed inserts missing IDs only; future ingestion will handle updates.
- Database credentials are for localhost development only.
- Existing API liveness and /ask behavior are unchanged.
