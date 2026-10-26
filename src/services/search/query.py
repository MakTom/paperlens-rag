from src.schemas.api.search import SearchRequest


def build_query(request: SearchRequest) -> dict:
    query = {
        "bool": {
            "must": [{
                "multi_match": {
                    "query": request.query,
                    "fields": ["title^2", "abstract"],
                    "type": "best_fields",
                    "operator": "or",
                    "zero_terms_query": "none",
                },
            }],
        },
    }
    if request.categories:
        # OR within the selected categories; filters do not add relevance score.
        query["bool"]["filter"] = [{"terms": {"categories": request.categories}}]
    return {
        "size": request.top_k,
        "track_total_hits": True,
        "query": query,
        "sort": [{"_score": "desc"}, {"arxiv_id": "asc"}],
    }
