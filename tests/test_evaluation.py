import json
from copy import deepcopy

import httpx
import pytest

from src.config import PROJECT_ROOT
from src.evaluation.dataset import canonical_corpus, fingerprint, load_dataset
from src.evaluation.metrics import retrieval_metrics, summarize
from src.evaluation.report import render_report, review_template, save_run, validate_review
from src.evaluation.runner import evaluate
from src.evaluation.snapshot import snapshot_index
from src.schemas.api.search import SearchHit, SearchResponse
from src.services.ollama import ModelServiceError
from src.services.search.client import SearchServiceError
from src.services.search.settings import SearchSettings


def test_frozen_labels_and_splits():
    dataset = load_dataset()
    dev = [c for c in dataset.cases if c.split == "dev"]
    holdout = [c for c in dataset.cases if c.split == "holdout"]
    assert len(dev) == 8 and sum(c.supported for c in dev) == 6
    assert len(holdout) == 4 and sum(c.supported for c in holdout) == 2


def test_corpus_hash_is_order_independent():
    papers = json.loads((PROJECT_ROOT / "fixtures/papers.seed.json").read_text())
    assert fingerprint(canonical_corpus(papers)) == fingerprint(canonical_corpus(list(reversed(papers))))


@pytest.mark.parametrize("mutation", ["corpus", "passage", "category", "duplicate"])
def test_invalid_labels_fail_before_services(tmp_path, mutation):
    payload = json.loads((PROJECT_ROOT / "eval/questions.v1.json").read_text())
    if mutation == "corpus":
        payload["corpus_sha256"] = "invalid"
    elif mutation == "passage":
        payload["cases"][0]["evidence"][0]["passage"] = "Invented supporting evidence"
    elif mutation == "category":
        payload["cases"][0]["categories"] = ["no.such.category"]
    else:
        payload["cases"][1]["id"] = payload["cases"][0]["id"]
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        load_dataset(path)


def test_rank_metrics_deduplicate_papers():
    metrics = retrieval_metrics(["x", "x", "a", "a"], ["a", "b"])
    assert metrics == {"recall_at_5": 0.5, "mrr_at_5": 0.5}


def test_metrics_cutoff_and_missing():
    assert retrieval_metrics(["x"] * 2, ["a"])["recall_at_5"] == 0
    assert retrieval_metrics(list("abcdef"), ["f"])["mrr_at_5"] == 0
    assert retrieval_metrics([], []) == {"recall_at_5": None, "mrr_at_5": None}


class FakeSearch:
    def __init__(self, empty=False, fail=False):
        self.empty, self.fail = empty, fail
        self.calls = []

    def search(self, request):
        self.calls.append(request)
        if self.fail:
            raise SearchServiceError("down")
        hits = [] if self.empty else [SearchHit(
            arxiv_id="2004.04906", title="Dense Passage Retrieval",
            abstract="DPR uses two encoders.", source_url="https://arxiv.org/abs/2004.04906",
            categories=["cs.CL"], text_kind="authored_summary", score=1,
        )]
        return SearchResponse(query=request.query, total=len(hits), took_ms=1, hits=hits)


class FakeGenerator:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def generate(self, prompt, *, system=None):
        self.calls.append((prompt, system))
        if self.fail:
            raise ModelServiceError("down")
        return "DPR uses two encoders. [S1]"


def run_one(**kwargs):
    case = load_dataset().cases[0]
    search, model = FakeSearch(), FakeGenerator()
    rows, summary = evaluate([case], search, model, **kwargs)
    return rows, summary, search, model


def test_runner_calls_retrieval_once_and_never_supplies_gold_labels():
    rows, summary, search, model = run_one()
    assert len(search.calls) == 1 and search.calls[0].top_k == 5
    assert len(model.calls) == 1
    prompt = json.loads(model.calls[0][0])
    assert set(prompt) == {"question", "evidence"}
    assert "expected_answer_points" not in model.calls[0][0]
    assert rows[0]["response"]["status"] == "answered"
    assert summary["recall_at_5"] == 1
    assert summary["manual_quality_scores"] is None


def test_retrieval_only_never_calls_model_and_keeps_null_generation_time():
    rows, summary, search, model = run_one(retrieval_only=True)
    assert not model.calls
    assert "response" not in rows[0]
    assert rows[0]["timings_ms"]["generation"] is None
    assert summary["latency"]["generation"]["n"] == 0


def test_no_evidence_skips_model():
    rows, _ = evaluate([load_dataset().cases[0]], FakeSearch(empty=True), FakeGenerator())
    assert rows[0]["response"]["status"] == "no_evidence"
    assert rows[0]["timings_ms"]["generation"] is None


def test_search_failure_counts_zero_and_is_not_abstention():
    rows, summary = evaluate([load_dataset().cases[0]], FakeSearch(fail=True), FakeGenerator())
    assert rows[0]["error"] == "SearchServiceError"
    assert not rows[0]["retrieval_completed"]
    assert summary["recall_at_5"] == 0 and summary["errors"] == 1
    assert summary["supported_statuses"] == {"error": 1}


def test_model_failure_retains_retrieval_metrics():
    rows, summary = evaluate([load_dataset().cases[0]], FakeSearch(), FakeGenerator(fail=True))
    assert rows[0]["error"] == "ModelServiceError"
    assert rows[0]["retrieval_completed"]
    assert summary["recall_at_5"] == 1


def test_unsupported_excluded_from_retrieval_denominator():
    cases = [load_dataset().cases[0], load_dataset().cases[6]]
    _, summary = evaluate(cases, FakeSearch(), FakeGenerator())
    assert summary["supported_cases"] == 1 and summary["unsupported_cases"] == 1
    assert summary["recall_at_5"] == 1
    assert summary["unsupported_statuses"] == {"answered": 1}


def sample_report():
    rows, summary, _, _ = run_one()
    return {"run_id": "synthetic-test-only", "metadata": {"split": "dev", "mode": "rag"},
            "corpus_stable": True, "rows": rows, "summary": summary}


def test_review_starts_unscored_and_tracks_coverage():
    report = sample_report()
    review = review_template(report)
    assert review["rows"][0]["correctness"] is None
    assert "reviewed=0/1" in render_report(report, review)
    assert "Pending" in render_report(report)


def test_review_is_bound_to_exact_report():
    report = sample_report()
    review = review_template(report)
    report["rows"][0]["query"] = "Different question"
    with pytest.raises(ValueError, match="exact run"):
        validate_review(report, review)


@pytest.mark.parametrize("problem", ["duplicate", "out_of_range", "reviewer_missing"])
def test_review_rejects_invalid_scoring(problem):
    report = sample_report()
    review = review_template(report)
    if problem == "duplicate":
        review["rows"].append(deepcopy(review["rows"][0]))
    elif problem == "out_of_range":
        review["rows"][0]["correctness"] = 3
    else:
        review["rows"][0]["correctness"] = 2
    with pytest.raises(ValueError):
        validate_review(report, review)


def test_manual_scores_remain_separate_from_automatic_metrics():
    report = sample_report()
    review = review_template(report)
    review["reviewer"] = "Test reviewer"
    review["rows"][0].update(correctness=0, groundedness=0, citation_support=0, notes="Unsupported claim")
    assert "mean_0_to_2=0.0" in render_report(report, review)
    assert report["summary"]["manual_quality_scores"] is None


def test_existing_run_cannot_be_overwritten(tmp_path):
    report = sample_report()
    save_run(report, tmp_path)
    with pytest.raises(FileExistsError):
        save_run(report, tmp_path)


@pytest.mark.parametrize("drift", [False, True])
def test_live_snapshot_detects_changed_index(monkeypatch, drift):
    papers = json.loads((PROJECT_ROOT / "fixtures/papers.seed.json").read_text())
    if drift:
        papers[0]["abstract"] += " Changed."
    def handler(request):
        if request.url.path.endswith("/_search"):
            return httpx.Response(200, json={"timed_out": False, "_shards": {"failed": 0},
                "hits": {"total": {"value": 5, "relation": "eq"}, "hits": [{"_source": p} for p in papers]}})
        return httpx.Response(200, json={})
    original = httpx.Client
    monkeypatch.setattr("src.evaluation.snapshot.httpx.Client",
                        lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(handler)))
    expected = load_dataset().corpus_sha256
    if drift:
        with pytest.raises(ValueError, match="differs"):
            snapshot_index(SearchSettings(_env_file=None), expected)
    else:
        assert snapshot_index(SearchSettings(_env_file=None), expected)["corpus_sha256"] == expected


def test_failure_not_dropped_from_aggregate_denominator():
    rows, _, _, _ = run_one()
    failed = deepcopy(rows[0])
    failed.update(error="SearchServiceError", metrics={"recall_at_5": 0, "mrr_at_5": 0})
    failed.pop("response")
    assert summarize(rows + [failed])["recall_at_5"] == 0.5


def test_cli_retrieval_run_writes_eight_dev_cases_without_model(monkeypatch, tmp_path):
    from contextlib import nullcontext
    from scripts import evaluate as cli

    model = FakeGenerator(fail=True)
    monkeypatch.setattr("sys.argv", ["evaluate", "--retrieval-only"])
    monkeypatch.setattr(cli, "snapshot_index", lambda *args: {"corpus_sha256": "test"})
    monkeypatch.setattr(cli, "SearchClient", lambda *args: nullcontext(FakeSearch()))
    monkeypatch.setattr(cli, "OllamaClient", lambda *args: model)
    monkeypatch.setattr(cli, "git_state", lambda: {"commit": "test", "dirty": False})
    monkeypatch.setattr(cli, "save_run", lambda report, directory: save_run(report, tmp_path))
    assert cli.main() == 0
    report_path = next(p for p in tmp_path.glob("*.json") if not p.name.endswith(".review.json"))
    report = json.loads(report_path.read_text())
    assert len(report["rows"]) == 8
    assert all(row["id"].startswith("dev-") for row in report["rows"])
    assert not model.calls
    assert report["metadata"]["model"] is None


def test_cli_holdout_requires_explicit_unlock(monkeypatch):
    from scripts import evaluate as cli

    monkeypatch.setattr("sys.argv", ["evaluate", "--split", "holdout"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2
