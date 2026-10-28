"""Paper-level metrics; unsupported cases have no retrieval relevance score."""
from statistics import mean, median


def retrieval_metrics(retrieved_ids, relevant_ids, k=5):
    if k < 1:
        raise ValueError("k must be positive")
    relevant = set(relevant_ids)
    if not relevant:
        return {"recall_at_5": None, "mrr_at_5": None}
    ranked = list(dict.fromkeys(retrieved_ids))[:k]
    recall = len(relevant.intersection(ranked)) / len(relevant)
    rr = next((1 / rank for rank, identifier in enumerate(ranked, 1) if identifier in relevant), 0.0)
    return {"recall_at_5": recall, "mrr_at_5": rr}


def summarize(rows):
    supported = [r for r in rows if r["supported"]]
    unsupported = [r for r in rows if not r["supported"]]
    def metric(key):
        # A retrieval service failure counts as zero, never drops out of the denominator.
        return mean((r["metrics"][key] or 0.0) for r in supported) if supported else None
    def statuses(group):
        result = {}
        for row in group:
            status = row.get("response", {}).get("status", "error" if row["error"] else "not_run")
            result[status] = result.get(status, 0) + 1
        return result
    latency = {}
    for stage in ("retrieval", "generation", "total"):
        values = [r["timings_ms"][stage] for r in rows if r["timings_ms"][stage] is not None]
        latency[stage] = {"n": len(values), "median_ms": median(values) if values else None,
                          "max_ms": max(values) if values else None}
    return {
        "cases": len(rows), "supported_cases": len(supported), "unsupported_cases": len(unsupported),
        "recall_at_5": metric("recall_at_5"), "mrr_at_5": metric("mrr_at_5"),
        "errors": sum(r["error"] is not None for r in rows),
        "supported_statuses": statuses(supported), "unsupported_statuses": statuses(unsupported),
        "latency": latency,
        "manual_quality_scores": None,
    }
