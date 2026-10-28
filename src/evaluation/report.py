"""Immutable machine report plus an explicitly unscored human-review worksheet."""
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from src.evaluation.dataset import fingerprint


class ReviewRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    correctness: int | None = Field(default=None, ge=0, le=2, strict=True)
    groundedness: int | None = Field(default=None, ge=0, le=2, strict=True)
    citation_support: int | None = Field(default=None, ge=0, le=2, strict=True)
    appropriate_abstention: bool | None = Field(default=None, strict=True)
    notes: str = ""


def review_template(report):
    return {"run_id": report["run_id"], "report_sha256": fingerprint(report),
            "reviewer": "", "rows": [ReviewRow(id=r["id"]).model_dump() for r in report["rows"]]}


def validate_review(report, review):
    if review.get("run_id") != report["run_id"] or review.get("report_sha256") != fingerprint(report):
        raise ValueError("Review does not belong to this exact run report")
    parsed = [ReviewRow.model_validate(r) for r in review["rows"]]
    ids = [r.id for r in parsed]
    if len(ids) != len(set(ids)) or set(ids) != {r["id"] for r in report["rows"]}:
        raise ValueError("Review IDs must match the report exactly once")
    if any(any(v is not None for k, v in r.model_dump().items() if k not in ("id", "notes")) for r in parsed):
        if not review.get("reviewer", "").strip():
            raise ValueError("Name the reviewer before adding scores")
    return parsed


def render_report(report, review=None):
    summary = report["summary"]
    lines = ["# PaperLens baseline evaluation", "", f"Run: {report['run_id']}",
             f"Split: {report['metadata']['split']}",
             f"Mode: {report['metadata']['mode']}",
             f"Corpus stable across pre/post checks: {report.get('corpus_stable')}",
             "Do not freeze a run with corpus_stable=false or service errors.", "",
             f"Supported cases: {summary['supported_cases']}; unsupported: {summary['unsupported_cases']}",
             f"Recall@5: {summary['recall_at_5']}; MRR@5: {summary['mrr_at_5']}",
             f"Service errors: {summary['errors']}", "",
             "Retrieval metrics are paper-level; unsupported cases are excluded. Retrieval failures count as zero.",
             "Five-document Recall@5 is a weak benchmark. These are descriptive baseline results, not production claims.",
             "", "## Response statuses", "", f"Supported: {summary['supported_statuses']}",
             f"Unsupported: {summary['unsupported_statuses']}", "", "## Latency", ""]
    for stage, values in summary["latency"].items():
        lines.append(f"- {stage}: n={values['n']}, median_ms={values['median_ms']}, max_ms={values['max_ms']}")
    lines += ["", "Generation is null when not invoked. Timings include attempted calls, including failures.",
              "This run does not control cache/model warm state; do not label it a cold/warm benchmark.",
              "", "## Human review", ""]
    if review is None:
        lines.append("Pending. No automated factual-quality score is assigned.")
    else:
        parsed = validate_review(report, review)
        lookup = {r.id: r for r in parsed}
        for supported in (True, False):
            group = [lookup[r["id"]] for r in report["rows"] if r["supported"] == supported]
            lines.append(f"### {'Supported' if supported else 'Unsupported'} ({len(group)} cases)")
            lines.append("")
            for field in ("correctness", "groundedness", "citation_support"):
                scores = [getattr(r, field) for r in group if getattr(r, field) is not None]
                average = sum(scores) / len(scores) if scores else None
                lines.append(f"- {field}: reviewed={len(scores)}/{len(group)}, mean_0_to_2={average}")
            votes = [r.appropriate_abstention for r in group if r.appropriate_abstention is not None]
            lines.append(f"- appropriate_abstention: true={sum(votes)}, reviewed={len(votes)}/{len(group)}")
            lines.append("")
        lines += ["Null fields are unreviewed or not applicable, never assumed correct.",
                  "See the worksheet notes for reasons and N/A explanations."]
    return "\n".join(lines) + "\n"


def save_run(report, directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    stem = directory / report["run_id"]
    outputs = {".json": json.dumps(report, indent=2),
               ".review.json": json.dumps(review_template(report), indent=2),
               ".md": render_report(report)}
    for suffix, text in outputs.items():
        with Path(str(stem) + suffix).open("x") as handle:
            handle.write(text + "\n")
    return stem
