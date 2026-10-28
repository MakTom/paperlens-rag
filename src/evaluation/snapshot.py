"""Read-only check of the exact five-record live index against the frozen fixture."""
import httpx

from src.evaluation.dataset import canonical_corpus, fingerprint


def snapshot_index(settings, expected_hash):
    with httpx.Client(base_url=str(settings.base_url).rstrip("/") + "/",
                      timeout=20, trust_env=False) as client:
        response = client.post(f"{settings.index}/_search", json={
            "size": 6, "track_total_hits": True, "query": {"match_all": {}},
        }, params={"allow_partial_search_results": "false"})
        response.raise_for_status()
        data = response.json()
        if data.get("timed_out") or data.get("_shards", {}).get("failed", 0):
            raise ValueError("Index snapshot incomplete")
        if data["hits"]["total"]["relation"] != "eq" or data["hits"]["total"]["value"] != 5:
            raise ValueError("Baseline requires exactly the five Day 3 records; use a separate index")
        records = canonical_corpus([h["_source"] for h in data["hits"]["hits"]])
        if len(records) != 5 or fingerprint(records) != expected_hash:
            raise ValueError("Live index differs from the frozen fixture; reindex the correct corpus")
        mapping = client.get(f"{settings.index}/_mapping")
        mapping.raise_for_status()
        index_settings = client.get(f"{settings.index}/_settings")
        index_settings.raise_for_status()
        version = client.get("")
        version.raise_for_status()
    return {"corpus_sha256": fingerprint(records), "index": settings.index,
            "mapping": mapping.json(), "index_settings": index_settings.json(),
            "opensearch_version": version.json().get("version", {}).get("number")}
