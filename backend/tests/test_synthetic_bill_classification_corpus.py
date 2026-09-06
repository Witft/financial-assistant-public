"""Regression checks for the independently authored public eval corpus."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = ROOT / "evals" / "bill-classification-v1"
GENERATOR_PATH = EVAL_DIR / "generate_synthetic_cases.py"
CASES_PATH = EVAL_DIR / "cases.jsonl"
TEMPLATE_PATH = EVAL_DIR / "cases.template.jsonl"


def load_generator():
    spec = importlib.util.spec_from_file_location("synthetic_bill_classification_cases", GENERATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_cases(serialized: str) -> list[dict]:
    return [json.loads(line) for line in serialized.splitlines() if line.strip()]


def test_synthetic_generator_reproduces_committed_cases_and_template():
    generator = load_generator()

    generated = generator.render_cases()

    assert generated == CASES_PATH.read_text(encoding="utf-8")
    assert generated == TEMPLATE_PATH.read_text(encoding="utf-8")


def test_synthetic_corpus_has_explicit_provenance_and_distinguishable_ids():
    generator = load_generator()
    cases = parse_cases(generator.render_cases())

    assert cases
    assert {case["source"] for case in cases} == {generator.SYNTHETIC_SOURCE}
    assert all(case["case_id"].startswith(generator.CASE_ID_PREFIX) for case in cases)
    assert all("synthetic" in case["tags"] for case in cases)
    assert all("public" in case["tags"] for case in cases)
    assert all(case["notes"] == generator.PROVENANCE_NOTE for case in cases)
