import importlib.util
import sys
from pathlib import Path


RUNNER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_bill_classification_eval.py"

spec = importlib.util.spec_from_file_location("bill_eval_runner", RUNNER_PATH)
runner = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)


class TestBillClassificationEvalRunner:
    def test_runner_builds_summary_and_markdown(self):
        cases = runner.load_cases()
        assert cases, "Eval runner should load at least one case"

        results = runner.evaluate_cases(cases)
        report = runner.build_summary(results)
        markdown = runner.render_markdown(report)

        assert report["summary"]["total_cases"] == len(cases)
        assert set(report["bucket_summary"]) == {"easy", "edge", "review", "transfer"}
        assert report["report_paths"]["process_report_json"].endswith("process-report-v1.json")
        assert report["report_paths"]["process_report_markdown"].endswith("process-report-v1.md")
        assert "Bill Classification Eval Report" in markdown
        assert "Bucket Summary" in markdown
        assert "Failed Cases" in markdown

    def test_runner_builds_process_report_with_standard_post_process_hook(self):
        cases = runner.load_cases()
        report = runner.build_summary(runner.evaluate_cases(cases))
        process_report = runner.build_process_report(report)

        assert process_report["artifact_version"] == "process-report-v1"
        assert process_report["base_eval_report_generated_at"] == report["generated_at"]
        assert process_report["implementation_boundary"]["current_path"] == "runner standard post-process hook"
        assert len(process_report["rows"]) == report["summary"]["total_cases"]
