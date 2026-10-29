"""Run frozen development evaluation using the same RagService as FastAPI."""
import argparse
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from uuid import uuid4

import httpx

from src.config import PROJECT_ROOT, Settings
from src.evaluation.dataset import fingerprint, load_dataset
from src.evaluation.report import save_run
from src.evaluation.runner import evaluate
from src.evaluation.snapshot import snapshot_index
from src.schemas.api.search import SearchRequest
from src.services.ollama import OllamaClient
from src.services.rag import MAX_EXCERPT_CHARS, MAX_SOURCES, SYSTEM_PROMPT
from src.services.search.client import SearchClient
from src.services.search.query import build_query
from src.services.search.settings import SearchSettings


def git_state():
    def command(*args):
        result = subprocess.run(["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=5)
        return result.stdout.strip() if result.returncode == 0 else None
    try:
        status = command("status", "--porcelain")
        return {"commit": command("rev-parse", "HEAD"), "dirty": bool(status) if status is not None else None}
    except (OSError, subprocess.TimeoutExpired):
        return {"commit": None, "dirty": None}


def model_identity(settings):
    with httpx.Client(timeout=10, trust_env=False) as client:
        response = client.get(str(settings.ollama_base_url).rstrip("/") + "/api/tags")
        response.raise_for_status()
        models = response.json()["models"]
    wanted = settings.ollama_model
    names = {wanted, wanted + ":latest"} if ":" not in wanted else {wanted}
    for model in models:
        if model.get("name") in names or model.get("model") in names:
            if not model.get("digest"):
                raise ValueError("Configured model has no digest")
            return {"name": wanted, "digest": model["digest"]}
    raise ValueError("Configured model is not installed; check ollama list")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retrieval-only", action="store_true")
    parser.add_argument("--split", choices=["dev", "holdout"], default="dev")
    parser.add_argument("--allow-holdout", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--hardware-note", default="not supplied")
    args = parser.parse_args()
    if args.split == "holdout" and not args.allow_holdout:
        parser.error("Holdout is reserved. Freeze settings before using --allow-holdout.")
    try:
        dataset = load_dataset()
        cases = [c for c in dataset.cases if c.split == args.split]
        if args.validate_only:
            print("PASS: 12 labels; 8 supported / 4 unsupported; 8 dev / 4 holdout; evidence verified.")
            return 0
        settings, search_settings = Settings(), SearchSettings()
        before = snapshot_index(search_settings, dataset.corpus_sha256)
        identity = None if args.retrieval_only else model_identity(settings)
        code_files = ["uv.lock", "src/services/rag.py", "src/services/ollama.py",
                      "src/services/search/query.py", "src/services/search/client.py",
                      "src/services/search/index_definition.py", "src/schemas/api/ask.py",
                      "src/evaluation/dataset.py", "src/evaluation/metrics.py", "src/evaluation/runner.py",
                      "src/evaluation/snapshot.py", "src/evaluation/report.py", "scripts/evaluate.py"]
        metadata = {
            "split": args.split, "mode": "retrieval_only" if args.retrieval_only else "rag",
            "dataset_version": dataset.dataset_version, "dataset_sha256": fingerprint(dataset.model_dump()),
            "corpus_version": dataset.corpus_version, "index_snapshot": before,
            "prompt_sha256": fingerprint(SYSTEM_PROMPT), "prompt_version": "day7-v2",
            "model": identity, "generation_options": {"temperature": 0, "num_predict": 256, "num_ctx": 8192},
            "model_timeout_seconds": settings.request_timeout_seconds,
            "search_timeout_seconds": search_settings.timeout_seconds,
            "query_template": build_query(SearchRequest(query="<query>", top_k=5)),
            "retrieval_top_k": 5, "max_context_records": MAX_SOURCES, "excerpt_chars": MAX_EXCERPT_CHARS,
            "python": sys.version, "platform": platform.platform(), "machine": platform.machine(),
            "hardware_note": args.hardware_note, "git": git_state(),
            "code_sha256": {name: fingerprint((PROJECT_ROOT / name).read_text()) for name in code_files},
            "warm_state": "uncontrolled; first request may load model", "cache": "no application answer cache",
        }
        print(f"Running {len(cases)} {args.split} cases in {metadata['mode']} mode...", flush=True)
        with SearchClient(search_settings) as search:
            rows, summary = evaluate(cases, search, OllamaClient(settings), retrieval_only=args.retrieval_only)
        snapshot_error = None
        try:
            stable = before == snapshot_index(search_settings, dataset.corpus_sha256)
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            stable, snapshot_error = False, type(exc).__name__
        now = datetime.now(timezone.utc)
        report = {"run_id": f"day6-{now.strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}",
                  "created_at": now.isoformat(), "metadata": metadata, "corpus_stable": stable,
                  "postflight_error": snapshot_error, "rows": rows, "summary": summary}
        stem = save_run(report, PROJECT_ROOT / "reports/local")
        print(json.dumps(summary, indent=2))
        print(f"Report: {stem}.json\nReview worksheet: {stem}.review.json\nSummary: {stem}.md")
        print("Manual factual review is pending. No quality threshold is asserted.")
        if not stable:
            print("FAIL: index changed or postflight failed; do not freeze this as a baseline.")
        return 0 if stable and not summary["errors"] else 1
    except (httpx.HTTPError, ValueError, KeyError, TypeError, OSError) as exc:
        print(f"FAIL ({type(exc).__name__}): evaluation preflight or report handling failed.")
        if isinstance(exc, ValueError):
            print(str(exc))
        print("Check fixture labels, Day 4 index, configured model and local services.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
