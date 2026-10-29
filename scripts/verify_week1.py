"""Run ordered Week 1 checks, stop on the first failure and save stage status."""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from src.config import PROJECT_ROOT

# Existing live verification may upsert fixture search documents; it never deletes them.
RETRIEVAL_STAGES = [
    ("configuration", ["scripts.check_config"], 30),
    ("database", ["scripts.check_db"], 60),
    ("retrieval", ["scripts.verify_day4"], 180),
    ("development_retrieval_evaluation", ["scripts.evaluate", "--retrieval-only"], 300),
]
GENERATION_STAGES = [
    ("api_contract", ["scripts.check_api"], 30),
    ("ollama_generation", ["scripts.smoke_llm"], 650),
    ("api_rag_smoke", ["scripts.verify_day5"], 2700),
]


def run_stages(stages, execute=subprocess.run):
    rows = []
    stopped = False
    for name, arguments, timeout in stages:
        row = {"stage": name, "status": "not_run", "elapsed_seconds": None}
        if not stopped:
            print(f"CHECK: {name}", flush=True)
            start = perf_counter()
            try:
                result = execute([sys.executable, "-m", *arguments], cwd=PROJECT_ROOT,
                                 timeout=timeout, check=False)
                row["returncode"] = result.returncode
                row["status"] = "passed" if result.returncode == 0 else "failed"
            except subprocess.TimeoutExpired:
                row["status"] = "timed_out"
            except OSError:
                row["status"] = "could_not_start"
            row["elapsed_seconds"] = round(perf_counter() - start, 3)
            stopped = row["status"] != "passed"
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-generation", action="store_true")
    args = parser.parse_args()
    stages = RETRIEVAL_STAGES + ([] if args.skip_generation else GENERATION_STAGES)
    rows = run_stages(stages)
    ok = all(row["status"] == "passed" for row in rows)
    report = {
        "scope": "retrieval_only" if args.skip_generation else "live_week1_smoke",
        "checks_passed": ok, "human_quality_review": "required_separately",
        "ci_status": "not_checked", "stages": rows,
    }
    folder = PROJECT_ROOT / "reports/local"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = folder / f"week1-{stamp}-{uuid4().hex[:8]}.json"
    with path.open("x") as handle:
        json.dump(report, handle, indent=2)
    print(f"Report: {path}")
    print("PASS: selected checks completed." if ok else "FAIL: fix the first failed stage, then rerun.")
    print("This does not approve a release: review Day 6 answers and confirm GitHub Actions separately.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
