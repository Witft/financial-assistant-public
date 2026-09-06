import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_bill_process_report_v1.py"

spec = importlib.util.spec_from_file_location("bill_process_report_v1", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class TestBillProcessReportV1:
    def test_build_process_report_covers_all_eval_cases_in_runner_order(self):
        eval_report = module.load_latest_eval_report()
        report = module.build_process_report(eval_report)

        assert report["artifact_version"] == "process-report-v1"
        assert report["selection"]["count"] == len(eval_report["results"])
        assert report["selection"]["total_eval_cases"] == len(eval_report["results"])

        rows = report["rows"]
        row_case_ids = [row["case_id"] for row in rows]
        eval_case_ids = [row["case_id"] for row in eval_report["results"]]
        assert row_case_ids == eval_case_ids

    def test_report_preserves_failure_and_control_sample_distinction(self):
        eval_report = module.load_latest_eval_report()
        report = module.build_process_report(eval_report)
        rows_by_id = {row["case_id"]: row for row in report["rows"]}

        assert rows_by_id["synthetic-public-v1-004-platform-healthcare-override"]["sample_type"] == "failure"
        assert rows_by_id["synthetic-public-v1-003-ambiguous-transfer-review"]["sample_type"] == "failure"
        assert rows_by_id["synthetic-public-v1-020-unknown-fallback"]["sample_type"] == "failure"

        assert rows_by_id["synthetic-public-v1-002-family-transfer"]["sample_type"] == "control"
        assert rows_by_id["synthetic-public-v1-007-investment-keyword"]["sample_type"] == "control"
        assert rows_by_id["synthetic-public-v1-006-dining-generic-keyword"]["sample_type"] == "control"

    def test_representative_rows_have_expected_rules_and_trace_fields(self):
        eval_report = module.load_latest_eval_report()
        report = module.build_process_report(eval_report)
        rows_by_id = {row["case_id"]: row for row in report["rows"]}

        platform_override = rows_by_id["synthetic-public-v1-004-platform-healthcare-override"]
        assert platform_override["matched_rule"] == "PlatformSecondaryOverrideRule"
        assert platform_override["trace_fields"]["winning_rule"] == "PlatformSecondaryOverrideRule"
        assert "platform_default_hit" in platform_override["trace_fields"]
        assert "secondary_override_hit" in platform_override["trace_fields"]

        ambiguous_transfer = rows_by_id["synthetic-public-v1-003-ambiguous-transfer-review"]
        assert ambiguous_transfer["matched_rule"] == "FamilyTransferRule"
        assert ambiguous_transfer["trace_fields"]["has_family_evidence"] is False
        assert ambiguous_transfer["trace_fields"]["has_ambiguous_transfer_signal"] is True

        unknown_fallback = rows_by_id["synthetic-public-v1-020-unknown-fallback"]
        assert unknown_fallback["matched_rule"] == "NoRuleFallback"
        assert unknown_fallback["expected"] == "other / review"
        assert unknown_fallback["observed"] == "other / review"

    def test_ordinary_coverage_rows_get_default_meta(self):
        eval_report = module.load_latest_eval_report()
        report = module.build_process_report(eval_report)
        rows_by_id = {row["case_id"]: row for row in report["rows"]}

        easy_row = rows_by_id["synthetic-public-v1-008-digital-keyword"]
        assert easy_row["sample_type"] == "coverage"
        assert easy_row["first_failed_phase"] == "—"
        assert "coverage row" in easy_row["next_action"]

        review_row = rows_by_id["synthetic-public-v1-017-dining-type-fallback"]
        assert review_row["sample_type"] == "coverage"
        assert review_row["next_action"].startswith("作为 review coverage row")

        transfer_row = rows_by_id["synthetic-public-v1-001-transfer-keyword"]
        assert transfer_row["sample_type"] == "coverage"
        assert transfer_row["next_action"].startswith("作为 transfer/investment coverage row")

    def test_synthetic_diagnostics_preserve_keyword_destination_and_control_contracts(self):
        eval_report = module.load_latest_eval_report()
        report = module.build_process_report(eval_report)
        rows_by_id = {row["case_id"]: row for row in report["rows"]}

        keyword_destination = rows_by_id["synthetic-public-v1-021-keyword-destination-priority"]
        assert keyword_destination["sample_type"] == "failure"
        assert keyword_destination["matched_rule"] == "KeywordMatchRule"
        assert "summary_signal" in keyword_destination["trace_fields"]
        assert "destination_signal" in keyword_destination["trace_fields"]

        platform_control = rows_by_id["synthetic-public-v1-022-platform-misleading-control"]
        assert platform_control["sample_type"] == "control"
        assert platform_control["expected"] == "shopping / no review"
        assert platform_control["matched_rule"] == "KeywordMatchRule"
        assert "platform_default_hit" in platform_control["trace_fields"]

        investment_control = rows_by_id["synthetic-public-v1-023-investment-destination-transfer-control"]
        assert investment_control["sample_type"] == "control"
        assert investment_control["expected"] == "investment / no review"
        assert investment_control["matched_rule"] == "KeywordMatchRule"
        assert investment_control["trace_fields"]["has_family_evidence"] is False
        assert investment_control["trace_fields"]["family_evidence"] == []
        assert investment_control["trace_fields"]["has_ambiguous_transfer_signal"] is False
        assert investment_control["trace_fields"]["ambiguous_transfer_signal"] == []

    def test_trace_field_gate_remains_source_id_prefix_based(self):
        meta = module.build_default_meta(
            {"expected_requires_human_review": False, "bucket": "easy"},
            "KeywordMatchRule",
        )

        gated_trace = module.build_trace_fields(
            "wechat-synthetic-control",
            "synthetic neutral text",
            "商户消费",
            "KeywordMatchRule",
            meta,
        )
        assert gated_trace["has_family_evidence"] is False
        assert gated_trace["family_evidence"] == []
        assert gated_trace["has_ambiguous_transfer_signal"] is False
        assert gated_trace["ambiguous_transfer_signal"] == []

        ungated_trace = module.build_trace_fields(
            "synthetic-public-v1-ungated-control",
            "synthetic neutral text",
            "商户消费",
            "KeywordMatchRule",
            meta,
        )
        assert "has_family_evidence" not in ungated_trace
        assert "has_ambiguous_transfer_signal" not in ungated_trace
