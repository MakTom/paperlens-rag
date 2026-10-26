"""Versioned mapping: analyzed text for ranking, keywords for exact filters."""

SCHEMA_VERSION = "paperlens-bm25-v1"
INDEX_BODY = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "_meta": {"schema_version": SCHEMA_VERSION},
        "dynamic": "strict",
        "properties": {
            "arxiv_id": {"type": "keyword"},
            "title": {"type": "text", "analyzer": "english"},
            "abstract": {"type": "text", "analyzer": "english"},
            "source_url": {"type": "keyword", "index": False},
            "categories": {"type": "keyword"},
            "text_kind": {"type": "keyword"},
        },
    },
}
