"""Render an existing report and optional human review; no service calls."""
import argparse
import json
from pathlib import Path

from src.evaluation.report import render_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--review", type=Path)
    args = parser.parse_args()
    try:
        report = json.loads(args.report.read_text())
        review = json.loads(args.review.read_text()) if args.review else None
        print(render_report(report, review))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
