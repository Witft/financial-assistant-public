#!/usr/bin/env python3
"""Generate the first diagnosis-oriented process-report-v1 artifact.

This enrichment step reads the existing eval report (latest.json) and adds a small
process layer for the full bill-classification dataset.

Important stance:
- the current runner is fully green;
- therefore this is not a live-failure report;
- it is a process-oriented enrichment artifact that keeps Week 7/8/9 reasoning
  attached to real runner output.

The report now covers all eval cases, while preserving a special distinction for:
- diagnosis / failure samples
- control / guardrail samples
- ordinary coverage rows
"""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

with redirect_stdout(io.StringIO()):
    import api_server

ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = ROOT / "evals" / "bill-classification-v1"
REPORTS_DIR = EVAL_DIR / "reports"
LATEST_JSON_PATH = REPORTS_DIR / "latest.json"
OUTPUT_JSON_PATH = REPORTS_DIR / "process-report-v1.json"
OUTPUT_MD_PATH = REPORTS_DIR / "process-report-v1.md"

FAILURE_SAMPLE_IDS = [
    "synthetic-public-v1-004-platform-healthcare-override",
    "synthetic-public-v1-003-ambiguous-transfer-review",
    "synthetic-public-v1-020-unknown-fallback",
    "synthetic-public-v1-021-keyword-destination-priority",
]

CONTROL_SAMPLE_IDS = [
    "synthetic-public-v1-002-family-transfer",
    "synthetic-public-v1-007-investment-keyword",
    "synthetic-public-v1-006-dining-generic-keyword",
    "synthetic-public-v1-022-platform-misleading-control",
    "synthetic-public-v1-023-investment-destination-transfer-control",
]

# Public corpus IDs retain their synthetic provenance prefix. These report-only
# aliases preserve the established source-ID trace gate for synthetic
# counterparts of diagnostics/controls that previously used it.
TRACE_SOURCE_ID_ALIASES = {
    "synthetic-public-v1-002-family-transfer": "wechat-synthetic-family-control",
    "synthetic-public-v1-003-ambiguous-transfer-review": "wechat-synthetic-ambiguous-review",
    "synthetic-public-v1-023-investment-destination-transfer-control": "wechat-synthetic-investment-control",
}

SAMPLE_META: dict[str, dict[str, Any]] = {
    "synthetic-public-v1-004-platform-healthcare-override": {
        "sample_type": "failure",
        "first_failed_phase": "priority_gate",
        "failure_type": "A platform default must not outrank a stronger secondary scenario signal.",
        "next_action": "Record platform_default_hit / secondary_override_hit and keep the override ahead of the platform default.",
        "suppressed_rule_candidates": ["platform_default:dining"],
    },
    "synthetic-public-v1-003-ambiguous-transfer-review": {
        "sample_type": "failure",
        "first_failed_phase": "priority_gate",
        "failure_type": "An ambiguous transfer without family evidence must remain in the human-review path.",
        "next_action": "Record has_family_evidence / has_ambiguous_transfer_signal and keep the review gate before family_support.",
        "suppressed_rule_candidates": ["family_support_without_evidence"],
    },
    "synthetic-public-v1-020-unknown-fallback": {
        "sample_type": "failure",
        "first_failed_phase": "fallback_resolution",
        "failure_type": "A transaction with no rule match must remain other and require human review.",
        "next_action": "Record the NoRuleFallback outcome and keep the explicit human-review handoff.",
        "suppressed_rule_candidates": [],
    },
    "synthetic-public-v1-021-keyword-destination-priority": {
        "sample_type": "failure",
        "first_failed_phase": "keyword_resolution",
        "failure_type": "A surface consumption summary must not outrank an explicit investment destination.",
        "next_action": "Record summary_signal / destination_signal and keep the destination keyword ahead of the surface summary.",
        "suppressed_rule_candidates": ["surface_summary_over_destination"],
    },
    "synthetic-public-v1-002-family-transfer": {
        "sample_type": "control",
        "first_failed_phase": "—",
        "failure_type": "—",
        "next_action": "Keep explicit family evidence as a no-review family transfer guardrail.",
        "suppressed_rule_candidates": [],
    },
    "synthetic-public-v1-007-investment-keyword": {
        "sample_type": "control",
        "first_failed_phase": "—",
        "failure_type": "—",
        "next_action": "Keep the explicit investment keyword on the investment/transfer path.",
        "suppressed_rule_candidates": [],
    },
    "synthetic-public-v1-006-dining-generic-keyword": {
        "sample_type": "control",
        "first_failed_phase": "—",
        "failure_type": "—",
        "next_action": "Keep the generic dining keyword as an ordinary no-review guardrail.",
        "suppressed_rule_candidates": [],
    },
    "synthetic-public-v1-022-platform-misleading-control": {
        "sample_type": "control",
        "first_failed_phase": "—",
        "failure_type": "—",
        "next_action": "Keep ordinary synthetic platform retail on shopping rather than healthcare.",
        "suppressed_rule_candidates": [],
    },
    "synthetic-public-v1-023-investment-destination-transfer-control": {
        "sample_type": "control",
        "first_failed_phase": "—",
        "failure_type": "—",
        "next_action": "Keep an explicit synthetic investment destination on the investment/transfer path.",
        "suppressed_rule_candidates": [],
    },
}


@dataclass
class RuleMatch:
    rule_name: str
    category: str
    confidence: float
    requires_review: bool


@dataclass
class ProcessRow:
    case_id: str
    sample_type: str
    bucket: str
    expected: str
    observed: str
    matched_rule: str
    first_failed_phase: str
    trace_fields: dict[str, Any]
    failure_type: str
    next_action: str


def load_latest_eval_report() -> dict[str, Any]:
    return json.loads(LATEST_JSON_PATH.read_text(encoding="utf-8"))


def format_expectation(category: str, requires_review: bool) -> str:
    return f"{category} / {'review' if requires_review else 'no review'}"


def collect_rule_matches(description: str, transaction_type: str) -> list[RuleMatch]:
    matches: list[RuleMatch] = []
    normalized_description = description.lower() if description else ""
    for rule in api_server._CLASSIFICATION_RULES:
        result = rule.match(normalized_description, transaction_type)
        if result is not None:
            matches.append(
                RuleMatch(
                    rule_name=rule.__class__.__name__,
                    category=result.category,
                    confidence=result.confidence,
                    requires_review=result.requires_review,
                )
            )
    return matches


def collect_platform_defaults(description: str) -> list[str]:
    hits: list[str] = []
    for default_cat, platforms in api_server.PlatformSecondaryOverrideRule._PLATFORM_DEFAULTS.items():
        matched_platforms = [platform for platform in platforms if platform in description]
        if matched_platforms:
            hits.append(f"{default_cat}:{'/'.join(matched_platforms)}")
    return hits


def collect_secondary_overrides(description: str) -> list[str]:
    hits: list[str] = []
    for override_cat, indicators in api_server.PlatformSecondaryOverrideRule._SECONDARY_OVERRIDES.items():
        matched_indicators = [indicator for indicator in indicators if indicator in description]
        if matched_indicators:
            hits.append(f"{override_cat}:{'/'.join(matched_indicators)}")
    return hits


def collect_family_evidence(description: str) -> list[str]:
    return [kw for kw in api_server.FamilyTransferRule._FAMILY_KEYWORDS if kw in description]


def collect_ambiguous_transfer_signals(description: str, transaction_type: str) -> list[str]:
    hits = [kw for kw in api_server.FamilyTransferRule._AMBIGUOUS_HINTS if kw in description]
    if transaction_type in {"转账", "微信转账", "红包"}:
        hits.append(f"transaction_type:{transaction_type}")
    return hits


def collect_summary_signals(description: str) -> list[str]:
    signals: list[str] = []
    if "摘要:" in description:
        summary_part = description.split("摘要:", 1)[1].split(" ", 1)[0].strip()
        if summary_part:
            signals.append(f"摘要:{summary_part}")
    for keyword in ("消费", "提现", "还款"):
        if keyword in description and keyword not in signals:
            signals.append(keyword)
    return signals


def collect_destination_signals(description: str) -> list[str]:
    keywords = tuple(api_server.CLASSIFICATION_RULES["investment"]["keywords"])
    return [keyword for keyword in keywords if keyword in description]


def collect_keyword_hits(description: str) -> list[str]:
    hits: list[str] = []
    normalized = description.lower()
    for category, rules in api_server.CLASSIFICATION_RULES.items():
        matched = [keyword for keyword in rules["keywords"] if keyword.lower() in normalized]
        if matched:
            hits.append(f"{category}:{'/'.join(matched[:3])}")
    return hits


def build_default_meta(result: dict[str, Any], matched_rule: str) -> dict[str, Any]:
    if result["expected_requires_human_review"]:
        return {
            "sample_type": "coverage",
            "first_failed_phase": "—",
            "failure_type": "—",
            "next_action": "作为 review coverage row，持续观察信息不足场景是否被稳定转入人工审核。",
            "suppressed_rule_candidates": [],
        }
    if result["bucket"] == "transfer":
        return {
            "sample_type": "coverage",
            "first_failed_phase": "—",
            "failure_type": "—",
            "next_action": "作为 transfer/investment coverage row，继续观察资金流转快路径是否稳定。",
            "suppressed_rule_candidates": [],
        }
    return {
        "sample_type": "coverage",
        "first_failed_phase": "—",
        "failure_type": "—",
        "next_action": f"作为常规 coverage row，确认 `{matched_rule}` 在当前样本上继续保持稳定命中。",
        "suppressed_rule_candidates": [],
    }


def build_trace_fields(case_id: str, raw_text: str, raw_transaction_type: str, matched_rule: str, meta: dict[str, Any]) -> dict[str, Any]:
    trace_fields: dict[str, Any] = {
        "winning_rule": matched_rule,
        "suppressed_rule_candidates": meta["suppressed_rule_candidates"],
    }

    platform_hits = collect_platform_defaults(raw_text)
    if platform_hits:
        trace_fields["platform_default_hit"] = platform_hits

    override_hits = collect_secondary_overrides(raw_text)
    if override_hits:
        trace_fields["secondary_override_hit"] = override_hits

    trace_source_id = TRACE_SOURCE_ID_ALIASES.get(case_id, case_id)

    family_hits = collect_family_evidence(raw_text)
    if family_hits or trace_source_id.startswith("wechat-"):
        trace_fields["has_family_evidence"] = bool(family_hits)
        trace_fields["family_evidence"] = family_hits

    ambiguous_hits = collect_ambiguous_transfer_signals(raw_text, raw_transaction_type)
    if ambiguous_hits or trace_source_id.startswith("wechat-"):
        trace_fields["has_ambiguous_transfer_signal"] = bool(ambiguous_hits)
        trace_fields["ambiguous_transfer_signal"] = ambiguous_hits

    summary_hits = collect_summary_signals(raw_text)
    if summary_hits:
        trace_fields["summary_signal"] = summary_hits

    destination_hits = collect_destination_signals(raw_text)
    if destination_hits:
        trace_fields["destination_signal"] = destination_hits

    keyword_hits = collect_keyword_hits(raw_text)
    if keyword_hits:
        trace_fields["keyword_hit_candidates"] = keyword_hits

    return trace_fields


def build_process_report(eval_report: dict[str, Any]) -> dict[str, Any]:
    results = eval_report["results"]
    rows: list[ProcessRow] = []

    for result in results:
        matches = collect_rule_matches(result["raw_text"], result["raw_transaction_type"])
        matched_rule = matches[0].rule_name if matches else "NoRuleFallback"
        meta = SAMPLE_META.get(result["case_id"], build_default_meta(result, matched_rule))
        trace_fields = build_trace_fields(
            case_id=result["case_id"],
            raw_text=result["raw_text"],
            raw_transaction_type=result["raw_transaction_type"],
            matched_rule=matched_rule,
            meta=meta,
        )

        rows.append(
            ProcessRow(
                case_id=result["case_id"],
                sample_type=meta["sample_type"],
                bucket=result["bucket"],
                expected=format_expectation(
                    result["expected_category"], result["expected_requires_human_review"]
                ),
                observed=format_expectation(
                    result["predicted_category"], result["predicted_requires_human_review"]
                ),
                matched_rule=matched_rule,
                first_failed_phase=meta["first_failed_phase"],
                trace_fields=trace_fields,
                failure_type=meta["failure_type"],
                next_action=meta["next_action"],
            )
        )

    sample_type_counts: dict[str, int] = {}
    for row in rows:
        sample_type_counts[row.sample_type] = sample_type_counts.get(row.sample_type, 0) + 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_eval_report": str(LATEST_JSON_PATH.relative_to(ROOT)),
        "artifact_version": "process-report-v1",
        "mode": "diagnosis-oriented",
        "selection": {
            "failure_sample_ids": FAILURE_SAMPLE_IDS,
            "control_sample_ids": CONTROL_SAMPLE_IDS,
            "total_eval_cases": len(results),
            "count": len(rows),
            "sample_type_counts": sample_type_counts,
        },
        "implementation_boundary": {
            "current_path": "runner post-process first",
            "goal": "Keep classifier output stable while testing whether process fields are worth internalizing.",
            "fields_that_feel_runtime_truth": ["matched_rule"],
            "fields_that_stay_eval_or_report_layer_for_now": [
                "first_failed_phase",
                "failure_type",
                "next_action",
                "suppressed_rule_candidates",
            ],
        },
        "rows": [asdict(row) for row in rows],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Bill Classification Process Report v1")
    lines.append("")
    lines.append(f"- Generated at: `{report['generated_at']}`")
    lines.append(f"- Base eval report: `{report['base_eval_report']}`")
    lines.append(f"- Mode: `{report['mode']}`")
    lines.append(f"- Selection count: **{report['selection']['count']}** / total eval cases `{report['selection']['total_eval_cases']}`")
    lines.append(f"- Sample type counts: `{json.dumps(report['selection']['sample_type_counts'], ensure_ascii=False)}`")
    lines.append(f"- Implementation path: `{report['implementation_boundary']['current_path']}`")
    lines.append("")
    lines.append(
        "> 说明：当前 eval runner 是全绿的，所以这不是“现网失败列表”，而是把 Week 7/8/9 的过程归因判断挂到真实 runner 输出上的第一版全量 process-report enrichment。"
    )
    lines.append("")
    lines.append("## Rows")
    lines.append("")
    lines.append("| case_id | sample_type | expected | observed | matched_rule | first_failed_phase |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for row in report["rows"]:
        lines.append(
            f"| `{row['case_id']}` | `{row['sample_type']}` | `{row['expected']}` | `{row['observed']}` | "
            f"`{row['matched_rule']}` | `{row['first_failed_phase']}` |"
        )
    lines.append("")
    lines.append("## Detailed Trace Fields")
    lines.append("")
    for row in report["rows"]:
        lines.append(f"### {row['case_id']} ({row['sample_type']})")
        lines.append(f"- bucket: `{row['bucket']}`")
        lines.append(f"- matched_rule: `{row['matched_rule']}`")
        lines.append(f"- failure_type: {row['failure_type']}")
        lines.append(f"- next_action: {row['next_action']}")
        lines.append("- trace_fields:")
        lines.append("```json")
        lines.append(json.dumps(row["trace_fields"], ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")
    lines.append("## Post-process vs in-classifier boundary")
    lines.append("")
    lines.append("- `matched_rule` 已经接近运行时真相，后续若需要更强可观测性，可以考虑让分类主流程直接产出。")
    lines.append("- `first_failed_phase` / `failure_type` / `next_action` 仍属于 eval/report 解释层，不应在 Week 9 就侵入 `classify_transaction()`。")
    lines.append("- `suppressed_rule_candidates` 当前仍依赖诊断视角和人工命名，适合先留在后处理层。")
    lines.append("")
    return "\n".join(lines)


def write_outputs(report: dict[str, Any]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUTPUT_MD_PATH.write_text(render_markdown(report) + "\n", encoding="utf-8")


def main() -> None:
    eval_report = load_latest_eval_report()
    report = build_process_report(eval_report)
    write_outputs(report)
    print(render_markdown(report))
    print("")
    print(f"JSON report written to: {OUTPUT_JSON_PATH}")
    print(f"Markdown report written to: {OUTPUT_MD_PATH}")


if __name__ == "__main__":
    main()
