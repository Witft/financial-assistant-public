"""Unit contracts for the explicit PostgreSQL schema boundary."""

from copy import deepcopy
import inspect
from pathlib import Path
import os
import re
import subprocess
import sys
import traceback

import pytest

import database
import schema


class _CatalogCursor:
    """Synthetic catalog cursor for duplicate-constraint snapshot boundaries."""

    def __init__(self, duplicate_kind: str):
        self.duplicate_kind = duplicate_kind
        self.table = ""
        self.statement = ""

    def execute(self, statement, parameters):
        self.statement = statement
        if parameters and isinstance(parameters[0], str) and parameters[0].startswith("public."):
            self.table = parameters[0].removeprefix("public.")

    def fetchone(self):
        if self.statement.startswith("SELECT to_regclass"):
            return {"relation": f"public.{self.table}"}
        if "SELECT c.relkind" in self.statement:
            return {"relkind": "r"}
        raise AssertionError(f"unexpected fetchone query: {self.statement}")

    def fetchall(self):
        contract = schema.CANONICAL_TABLES[self.table]
        if "FROM pg_attribute a LEFT JOIN pg_attrdef" in self.statement:
            return [
                {"name": name, **column}
                for name, column in contract["columns"].items()
            ]
        if "c.contype = 'p'" in self.statement:
            return [{"name": name} for name in contract["primary_key"]]
        if "c.contype = 'c'" in self.statement:
            rows = [
                {"definition": definition, "validated": value["validated"]}
                for definition, value in contract["checks"].items()
            ]
            return rows * 2 if self.duplicate_kind == "check" and self.table == "transactions" else rows
        if "c.contype = 'f'" in self.statement:
            rows = [
                {
                    "definition": definition,
                    "columns": value["columns"],
                    "schema_name": value["references"][0],
                    "table_name": value["references"][1],
                    "target_columns": value["references"][2],
                    "update_action": "a",
                    "delete_action": "c",
                    "match_type": "s",
                    "validated": value["validated"],
                    "deferrable": value["deferrable"],
                    "deferred": value["deferred"],
                }
                for definition, value in contract["foreign_keys"].items()
            ]
            return rows * 2 if self.duplicate_kind == "foreign-key" and self.table == "import_job_runs" else rows
        raise AssertionError(f"unexpected fetchall query: {self.statement}")


def test_canonical_schema_declares_all_existing_public_tables_and_contracts():
    """Bootstrap must own the exact public tables, columns, keys and checks."""
    tables = schema.CANONICAL_TABLES

    assert list(tables) == ["transactions", "import_jobs", "import_job_runs"]
    assert tables["transactions"]["columns"]["amount"] == {
        "type": "numeric(14,2)", "nullable": False, "default": None
    }
    assert tables["transactions"]["columns"]["raw_data"] == {
        "type": "jsonb", "nullable": False, "default": "'{}'::jsonb"
    }
    assert tables["transactions"]["primary_key"] == ("id",)
    assert tables["transactions"]["checks"] == {
        "CHECK ((type = ANY (ARRAY['expense'::text, 'income'::text, 'transfer'::text])))": {"validated": True}
    }
    assert tables["import_jobs"]["columns"]["source"] == {
        "type": "text", "nullable": False, "default": "'unknown'::text"
    }
    assert tables["import_jobs"]["checks"] == {
        "CHECK ((status = ANY (ARRAY['PENDING'::text, 'RUNNING'::text, 'SUCCEEDED'::text, 'FAILED'::text, 'REVIEW_REQUIRED'::text])))": {"validated": True}
    }
    assert tables["import_job_runs"]["foreign_keys"] == {
        "FOREIGN KEY (job_id) REFERENCES import_jobs(id) ON DELETE CASCADE": {
            "columns": ("job_id",), "references": ("public", "import_jobs", ("id",)),
            "on_update": "NO ACTION", "on_delete": "CASCADE", "match_type": "SIMPLE",
            "validated": True, "deferrable": False, "deferred": False,
        }
    }


def test_catalog_validation_accepts_exact_canonical_snapshot():
    """A compatible legacy schema is read-only accepted without mutation."""
    snapshot = schema.canonical_catalog_snapshot()

    schema.validate_catalog_snapshot(snapshot)


def test_catalog_snapshot_rejects_an_identical_duplicate_check_before_dict_insertion():
    """Two separately named but identical CHECK rows are still incompatible."""
    cursor = _CatalogCursor("check")

    with pytest.raises(schema.SchemaCompatibilityError, match="transactions.checks"):
        schema._catalog_snapshot(cursor)


def test_catalog_snapshot_rejects_an_identical_duplicate_foreign_key_before_dict_insertion():
    """Two separately named but identical FK rows are still incompatible."""
    cursor = _CatalogCursor("foreign-key")

    with pytest.raises(schema.SchemaCompatibilityError, match="import_job_runs.job_id"):
        schema._catalog_snapshot(cursor)


def test_catalog_validation_rejects_existing_incompatible_column_type():
    """An existing table with a changed business type must fail closed."""
    snapshot = deepcopy(schema.canonical_catalog_snapshot())
    snapshot["transactions"]["columns"]["amount"]["type"] = "double precision"

    with pytest.raises(schema.SchemaCompatibilityError, match="transactions.amount"):
        schema.validate_catalog_snapshot(snapshot)


def test_catalog_validation_rejects_missing_foreign_key():
    """An incomplete legacy schema cannot be stamped compatible."""
    snapshot = deepcopy(schema.canonical_catalog_snapshot())
    snapshot["import_job_runs"]["foreign_keys"] = {}

    with pytest.raises(schema.SchemaCompatibilityError, match="import_job_runs.job_id"):
        schema.validate_catalog_snapshot(snapshot)


def test_canonical_catalog_requires_validated_full_constraint_contract_and_ordinary_tables():
    """The checked contract includes exact checks, complete FK behavior, and relkind."""
    snapshot = schema.canonical_catalog_snapshot()

    assert snapshot["transactions"]["relation_kind"] == "r"
    assert snapshot["transactions"]["checks"] == {
        "CHECK ((type = ANY (ARRAY['expense'::text, 'income'::text, 'transfer'::text])))": {
            "validated": True,
        }
    }
    assert snapshot["import_job_runs"]["foreign_keys"] == {
        "FOREIGN KEY (job_id) REFERENCES import_jobs(id) ON DELETE CASCADE": {
            "columns": ("job_id",),
            "references": ("public", "import_jobs", ("id",)),
            "on_update": "NO ACTION",
            "on_delete": "CASCADE",
            "match_type": "SIMPLE",
            "validated": True,
            "deferrable": False,
            "deferred": False,
        }
    }


@pytest.mark.parametrize("relation_kind", ("v", "m", "f", "p"))
def test_catalog_validation_rejects_nonordinary_relation_kind(relation_kind):
    """A matching-looking view or partitioned relation is not an application table."""
    snapshot = schema.canonical_catalog_snapshot()
    snapshot["transactions"]["relation_kind"] = relation_kind

    with pytest.raises(schema.SchemaCompatibilityError, match="transactions.relation_kind"):
        schema.validate_catalog_snapshot(snapshot)


def test_runtime_sql_always_schema_qualifies_application_relations():
    """A role search_path must not redirect business reads or writes from public."""
    source = inspect.getsource(database)

    assert not re.search(
        r"(?im)^\s*(?:INSERT\s+INTO|UPDATE|FROM)\s+(?:transactions|import_jobs|import_job_runs)\b",
        source,
    )


def test_initialize_requires_explicit_database_url():
    """The explicit initializer cannot silently select any database."""
    with pytest.raises(schema.SchemaInitializationError, match="DATABASE_URL is required"):
        schema.initialize_database(None)


def test_readiness_requires_explicit_database_url():
    """Readiness has a separate configuration contract from parse-only startup."""
    with pytest.raises(schema.SchemaReadinessError, match="DATABASE_URL is required"):
        schema.assert_database_ready(None)


def test_initialization_cli_requires_database_url_without_echoing_connection_details():
    """The operator entrypoint is explicit and keeps absent-config diagnostics safe."""
    script = Path(__file__).parents[1] / "scripts" / "init_database.py"
    environment = dict(os.environ)
    environment.pop("DATABASE_URL", None)
    result = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, env=environment, check=False
    )

    assert result.returncode == 2
    assert "DATABASE_URL is required" in result.stderr
    assert "postgresql://" not in result.stderr.lower()
