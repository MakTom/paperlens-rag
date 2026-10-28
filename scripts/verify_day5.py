"""Live API smoke evaluation. Structural checks do not measure factual grounding."""
import json
from datetime import datetime, timezone
from time import perf_counter

import httpx

from src.config import PROJECT_ROOT
from src.schemas.api.ask import AskResponse


def check_case(case, response):
    if "expected_status" in case:
        return response.status == case["expected_status"] and not response.sources and not response.evidence
    evidence = {e.citation_id: e for e in response.evidence}
    expected = case["expected_arxiv_id"]
    return (
        response.status == "answered" and bool(response.cited_ids)
        and all(i in evidence for i in response.cited_ids)
        and any(evidence[i].arxiv_id == expected for i in response.cited_ids)
        and response.sources == [evidence[i].source_url for i in response.cited_ids]
    )


def main():
    cases = json.loads((PROJECT_ROOT / "fixtures/day5-evaluation.json").read_text())
    rows = []
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=650, trust_env=False) as client:
        for case in cases:
            start = perf_counter()
            row = dict(case, passed=False, manual_grounding_review="pending")
            try:
                raw = client.post("/api/v1/ask", json={"query": case["query"], "top_k": 3})
                raw.raise_for_status()
                response = AskResponse.model_validate(raw.json())
                row.update(response=response.model_dump(), passed=check_case(case, response))
            except (httpx.HTTPError, ValueError) as exc:
                row["error_type"] = type(exc).__name__
            row["elapsed_seconds"] = round(perf_counter() - start, 3)
            rows.append(row)
            print(f"{'PASS' if row['passed'] else 'FAIL'}: {case['id']}")
    folder = PROJECT_ROOT / "reports/local"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = folder / f"day5-{stamp}.json"
    path.write_text(json.dumps({"cases": rows, "note": "Manual factual-grounding review required."}, indent=2))
    print(f"Report: {path}")
    print("Read each answer against its exact evidence excerpts; citation validity is not factual correctness.")
    return 0 if all(row["passed"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
