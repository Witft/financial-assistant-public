import json
from pathlib import Path

import pytest

from api_server import classify_transaction


EVAL_CASES_PATH = Path(__file__).resolve().parents[2] / "evals" / "bill-classification-v1" / "cases.jsonl"


REQUIRED_FIELDS = {
    "case_id",
    "source",
    "raw_text",
    "raw_transaction_type",
    "normalized_type",
    "amount",
    "occurred_at",
    "expected_category",
    "expected_requires_human_review",
    "bucket",
}

VALID_BUCKETS = {"easy", "edge", "review", "transfer"}


def load_eval_cases() -> list[dict]:
    cases: list[dict] = []
    for line in EVAL_CASES_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        cases.append(json.loads(line))
    return cases


CASES = load_eval_cases()


class TestBillClassificationEvalDataset:
    def test_eval_dataset_exists(self):
        assert EVAL_CASES_PATH.exists(), f"Missing eval dataset: {EVAL_CASES_PATH}"

    def test_eval_dataset_has_unique_case_ids(self):
        case_ids = [case["case_id"] for case in CASES]
        assert case_ids, "Eval dataset is empty"
        assert len(case_ids) == len(set(case_ids)), "Duplicate case_id found in eval dataset"

    def test_eval_dataset_uses_expected_schema(self):
        for case in CASES:
            missing_fields = REQUIRED_FIELDS - case.keys()
            assert not missing_fields, f"case_id={case.get('case_id')} missing fields: {sorted(missing_fields)}"
            assert case["normalized_type"] in {"expense", "income", "transfer"}, (
                f"case_id={case['case_id']} has invalid normalized_type={case['normalized_type']!r}"
            )
            assert case["bucket"] in VALID_BUCKETS, (
                f"case_id={case['case_id']} has invalid bucket={case['bucket']!r}"
            )


@pytest.mark.parametrize("case", CASES, ids=[case["case_id"] for case in CASES])
def test_bill_classification_eval_cases(case):
    predicted_category, confidence, requires_review = classify_transaction(
        case["raw_text"],
        case["raw_transaction_type"],
        skip_memory=True,
    )

    assert predicted_category == case["expected_category"], (
        f"case_id={case['case_id']} raw_text={case['raw_text']!r} raw_transaction_type={case['raw_transaction_type']!r}: "
        f"expected category {case['expected_category']!r}, got {predicted_category!r}"
    )
    assert requires_review is case["expected_requires_human_review"], (
        f"case_id={case['case_id']} raw_text={case['raw_text']!r} raw_transaction_type={case['raw_transaction_type']!r}: "
        f"expected requires_human_review={case['expected_requires_human_review']}, got {requires_review}"
    )
    assert 0.0 <= confidence <= 1.0, (
        f"case_id={case['case_id']} produced invalid confidence={confidence}"
    )
