"""Contract tests for the explicitly synthetic CCB XLS parser fixture."""
from pathlib import Path
import subprocess
import sys

import xlrd

from api_server import parse_xls_content
from tests.fixtures import CCB_XLS_SAMPLE_PATH


FIXTURE_DIR = Path(__file__).with_name("fixtures")
DOCUMENTATION_PATH = FIXTURE_DIR / "CCB_SAMPLE_SYNTHETIC.md"
GENERATOR_PATH = FIXTURE_DIR / "generate_ccb_sample.py"


def test_ccb_xls_fixture_is_documented_generated_and_explicitly_synthetic():
    """The public fixture must be invented and retain its provenance markers."""
    assert DOCUMENTATION_PATH.is_file()
    documentation = DOCUMENTATION_PATH.read_text(encoding="utf-8")
    assert "SYNTHETIC" in documentation
    assert "not a real bank statement" in documentation
    assert GENERATOR_PATH.is_file()
    completed = subprocess.run(
        [sys.executable, str(GENERATOR_PATH), "--check"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr

    workbook = xlrd.open_workbook(file_contents=CCB_XLS_SAMPLE_PATH.read_bytes())
    sheet = workbook.sheet_by_index(0)
    assert sheet.cell_value(0, 0) == "SYNTHETIC TEST FIXTURE — NOT A REAL BANK STATEMENT"
    assert sheet.cell_value(1, 0) == "All people, transaction scenarios, amounts, and dates are invented."
    assert "all people, organizations, amounts, and dates are invented" not in documentation.lower()
    assert "transactions, identities, and amounts are invented" in documentation.lower()
    assert "public parser/classification compatibility label" in documentation.lower()
    assert "not private data" in documentation.lower()

    transactions = parse_xls_content(CCB_XLS_SAMPLE_PATH.read_bytes())
    assert len(transactions) == 12
    assert transactions[0]["source"] == "ccb"
    assert transactions[0]["type"] == "transfer"
