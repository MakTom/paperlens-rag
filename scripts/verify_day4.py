"""Live checks against the existing DB and index; upserts but never deletes papers."""
from src.db.session import build_engine
from src.schemas.api.search import SearchRequest
from src.services.search.client import SearchClient
from src.services.search.indexer import index_papers


def verify(engine, search):
    first = index_papers(engine, search)
    second = index_papers(engine, search)
    if first["indexed"] < 5 or second["indexed"] != first["indexed"]:
        raise AssertionError("Expected stable source data containing the Day 3 fixture.")
    if first["index_total"] != second["index_total"]:
        raise AssertionError("Repeated indexing changed the document count.")
    cases = {
        "Attention Is All You Need": "1706.03762",
        "Dense Passage Retrieval": "2004.04906",
        "Retrieval Augmented Generation": "2005.11401",
    }
    for query, expected in cases.items():
        result = search.search(SearchRequest(query=query, top_k=5))
        if expected not in {hit.arxiv_id for hit in result.hits}:
            raise AssertionError(f"Known paper missing from top five: {expected}")
    filtered = search.search(SearchRequest(query="retrieval", categories=["cs.CL"]))
    if not filtered.hits or any("cs.CL" not in hit.categories for hit in filtered.hits):
        raise AssertionError("Category filter failed.")
    missing = search.search(SearchRequest(query="retrieval", categories=["no.such.category"]))
    if missing.total != 0 or missing.hits:
        raise AssertionError("Missing category should have zero matches.")
    unknown = search.search(SearchRequest(query="zzzxqvnonexistentfixturetoken"))
    if unknown.total != 0 or unknown.hits:
        raise AssertionError("Unmatched token should have zero matches.")
    print(
        f"PASS: stable index count={second['index_total']}; "
        "3 known-paper checks, category filters and no-match behavior verified."
    )


if __name__ == "__main__":
    engine = build_engine()
    try:
        with SearchClient() as search:
            verify(engine, search)
    finally:
        engine.dispose()
