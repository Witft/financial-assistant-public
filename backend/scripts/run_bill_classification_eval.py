#!/usr/bin/env python3
"""Run the bill-classification eval dataset and emit JSON/Markdown reports."""

from __future__ import annotations

import io
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from contextlib import redirect_stdout
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

with redirect_stdout(io.StringIO()):
    from api_server import classify_transaction

ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = ROOT / "evals" / "bill-classification-v1"
CASES_PATH = EVAL_DIR / "cases.jsonl"
REPORTS_DIR = EVAL_DIR / "reports"
LATEST_JSON_PATH = REPORTS_DIR / "latest.json"
LATEST_MD_PATH = REPORTS_DIR / "latest.md"
PROCESS_REPORT_JSON_PATH = REPORTS_DIR / "process-report-v1.json"
PROCESS_REPORT_MD_PATH = REPORTS_DIR / "process-report-v1.md"

PROCESS_REPORT_SCRIPT_PATH = SCRIPT_DIR / "generate_bill_process_report_v1.py"
process_report_spec = importlib.util.spec_from_file_location(
    "bill_process_report_v1_for_runner", PROCESS_REPORT_SCRIPT_PATH
)
assert process_report_spec is not None and process_report_spec.loader is not None
process_report_module = importlib.util.module_from_spec(process_report_spec)
sys.modules[process_report_spec.name] = process_report_module
process_report_spec.loader.exec_module(process_report_module)


@dataclass
class CaseResult:
    case_id: str
    bucket: str
    source: str
    raw_text: str
    raw_transaction_type: str
    normalized_type: str
    expected_category: str
    predicted_category: str
    category_match: bool
    expected_requires_human_review: bool
    predicted_requires_human_review: bool
    review_match: bool
    confidence: float
    amount: float
    occurred_at: str
    tags: list[str]
    gold_reason: str | None
    notes: str | None


def load_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for line in CASES_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        cases.append(json.loads(line))
    return cases


def evaluate_cases(cases: list[dict[str, Any]]) -> list[CaseResult]:
    results: list[CaseResult] = []
    for case in cases:
        predicted_category, confidence, predicted_requires_review = classify_transaction(
            case["raw_text"],
            case["raw_transaction_type"],
            skip_memory=True,
        )
        results.append(
            CaseResult(
                case_id=case["case_id"],
                bucket=case["bucket"],
                source=case["source"],
                raw_text=case["raw_text"],
                raw_transaction_type=case["raw_transaction_type"],
                normalized_type=case["normalized_type"],
                expected_category=case["expected_category"],
                predicted_category=predicted_category,
                category_match=predicted_category == case["expected_category"],
                expected_requires_human_review=case["expected_requires_human_review"],
                predicted_requires_human_review=predicted_requires_review,
                review_match=predicted_requires_review is case["expected_requires_human_review"],
                confidence=confidence,
                amount=case["amount"],
                occurred_at=case["occurred_at"],
                tags=case.get("tags", []),
                gold_reason=case.get("gold_reason"),
                notes=case.get("notes"),
            )
        )
    return results


def percentage(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator * 100, 2)


def build_summary(results: list[CaseResult]) -> dict[str, Any]:
    total = len(results)
    category_hits = sum(1 for r in results if r.category_match)
    review_hits = sum(1 for r in results if r.review_match)
    full_hits = sum(1 for r in results if r.category_match and r.review_match)
    failures = [r for r in results if not (r.category_match and r.review_match)]

    bucket_groups: dict[str, list[CaseResult]] = defaultdict(list)
    for result in results:
        bucket_groups[result.bucket].append(result)

    bucket_summary: dict[str, Any] = {}
    for bucket, items in sorted(bucket_groups.items()):
        bucket_summary[bucket] = {
            "count": len(items),
            "category_accuracy": percentage(sum(1 for r in items if r.category_match), len(items)),
            "review_accuracy": percentage(sum(1 for r in items if r.review_match), len(items)),
            "full_match_rate": percentage(
                sum(1 for r in items if r.category_match and r.review_match), len(items)
            ),
        }

    confusion = Counter()
    for result in failures:
        confusion[f"{result.expected_category} -> {result.predicted_category}"] += 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(CASES_PATH.relative_to(ROOT)),
        "report_paths": {
            "json": str(LATEST_JSON_PATH.relative_to(ROOT)),
            "markdown": str(LATEST_MD_PATH.relative_to(ROOT)),
            "process_report_json": str(PROCESS_REPORT_JSON_PATH.relative_to(ROOT)),
            "process_report_markdown": str(PROCESS_REPORT_MD_PATH.relative_to(ROOT)),
        },
        "summary": {
            "total_cases": total,
            "category_accuracy": percentage(category_hits, total),
            "review_accuracy": percentage(review_hits, total),
            "full_match_rate": percentage(full_hits, total),
            "failure_count": len(failures),
        },
        "bucket_summary": bucket_summary,
        "failure_breakdown": dict(confusion.most_common()),
        "failures": [asdict(r) for r in failures],
        "results": [asdict(r) for r in results],
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines: list[str] = []
    lines.append("# Bill Classification Eval Report")
    lines.append("")
    lines.append(f"- Generated at: `{report['generated_at']}`")
    lines.append(f"- Dataset: `{report['dataset_path']}`")
    lines.append(f"- Total cases: **{summary['total_cases']}**")
    lines.append(f"- Category accuracy: **{summary['category_accuracy']}%**")
    lines.append(f"- Review accuracy: **{summary['review_accuracy']}%**")
    lines.append(f"- Full match rate: **{summary['full_match_rate']}%**")
    lines.append(f"- Failure count: **{summary['failure_count']}**")
    lines.append("")

    lines.append("## Bucket Summary")
    lines.append("")
    lines.append("| Bucket | Count | Category Accuracy | Review Accuracy | Full Match Rate |")
    lines.append("|---|---:|---:|---:|---:|")
    for bucket, bucket_summary in report["bucket_summary"].items():
        lines.append(
            f"| {bucket} | {bucket_summary['count']} | {bucket_summary['category_accuracy']}% | "
            f"{bucket_summary['review_accuracy']}% | {bucket_summary['full_match_rate']}% |"
        )
    lines.append("")

    lines.append("## Failure Breakdown")
    lines.append("")
    if report["failure_breakdown"]:
        for key, count in report["failure_breakdown"].items():
            lines.append(f"- `{key}` × {count}")
    else:
        lines.append("- No failures 🎉")
    lines.append("")

    lines.append("## Failed Cases")
    lines.append("")
    if report["failures"]:
        for failure in report["failures"]:
            lines.append(f"### {failure['case_id']} ({failure['bucket']})")
            lines.append(f"- raw_text: `{failure['raw_text']}`")
            lines.append(f"- raw_transaction_type: `{failure['raw_transaction_type']}`")
            lines.append(f"- expected_category: `{failure['expected_category']}`")
            lines.append(f"- predicted_category: `{failure['predicted_category']}`")
            lines.append(
                f"- expected_requires_human_review: `{failure['expected_requires_human_review']}` / "
                f"predicted: `{failure['predicted_requires_human_review']}`"
            )
            lines.append(f"- confidence: `{failure['confidence']}`")
            if failure.get("gold_reason"):
                lines.append(f"- gold_reason: {failure['gold_reason']}")
            if failure.get("tags"):
                lines.append(f"- tags: `{', '.join(failure['tags'])}`")
            lines.append("")
    else:
        lines.append("All cases fully matched expected category + review behavior.")
        lines.append("")

    return "\n".join(lines)


def write_eval_outputs(report: dict[str, Any]) -> str:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown = render_markdown(report)
    LATEST_MD_PATH.write_text(markdown + "\n", encoding="utf-8")
    return markdown


def build_process_report(report: dict[str, Any]) -> dict[str, Any]:
    process_report = process_report_module.build_process_report(report)
    process_report["base_eval_report_generated_at"] = report["generated_at"]
    process_report["implementation_boundary"]["current_path"] = "runner standard post-process hook"
    return process_report


def write_process_report_outputs(report: dict[str, Any]) -> str:
    process_report = build_process_report(report)
    process_report_module.write_outputs(process_report)
    return process_report_module.render_markdown(process_report)


def main() -> None:
    cases = load_cases()
    results = evaluate_cases(cases)
    report = build_summary(results)

    markdown = write_eval_outputs(report)
    write_process_report_outputs(report)

    print(markdown)
    print("")
    print(f"JSON report written to: {LATEST_JSON_PATH}")
    print(f"Markdown report written to: {LATEST_MD_PATH}")
    print(f"Process report JSON written to: {PROCESS_REPORT_JSON_PATH}")
    print(f"Process report Markdown written to: {PROCESS_REPORT_MD_PATH}")


if __name__ == "__main__":
    main()
