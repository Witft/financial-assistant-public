"""Explicit, fail-closed PostgreSQL schema bootstrap and readiness checks.

Business repository functions must never import or call the initialization entrypoint.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

PUBLIC_SCHEMA = "public"
ADVISORY_LOCK_NAME = "financial_assistant_schema_boundary_v1"


class SchemaInitializationError(RuntimeError):
    """Raised when explicit schema setup cannot safely complete."""


class SchemaCompatibilityError(SchemaInitializationError):
    """Raised when an existing object differs from the current public contract."""


class SchemaReadinessError(RuntimeError):
    """Raised when configured application startup cannot read a prepared schema."""


CANONICAL_TABLES: dict[str, dict[str, Any]] = {
    "transactions": {
        "relation_kind": "r",
        "columns": {
            "id": {"type": "text", "nullable": False, "default": None},
            "transaction_date": {"type": "date", "nullable": False, "default": None},
            "amount": {"type": "numeric(14,2)", "nullable": False, "default": None},
            "category": {"type": "text", "nullable": False, "default": None},
            "description": {"type": "text", "nullable": False, "default": None},
            "source": {"type": "text", "nullable": False, "default": None},
            "type": {"type": "text", "nullable": False, "default": None},
            "transaction_type": {"type": "text", "nullable": True, "default": None},
            "confidence": {"type": "double precision", "nullable": True, "default": None},
            "requires_human_review": {"type": "boolean", "nullable": False, "default": "false"},
            "raw_data": {"type": "jsonb", "nullable": False, "default": "'{}'::jsonb"},
            "created_at": {"type": "timestamp with time zone", "nullable": False, "default": "now()"},
            "updated_at": {"type": "timestamp with time zone", "nullable": False, "default": "now()"},
        },
        "primary_key": ("id",),
        "checks": {
            "CHECK ((type = ANY (ARRAY['expense'::text, 'income'::text, 'transfer'::text])))": {"validated": True},
        },
        "foreign_keys": {},
    },
    "import_jobs": {
        "relation_kind": "r",
        "columns": {
            "id": {"type": "text", "nullable": False, "default": None},
            "status": {"type": "text", "nullable": False, "default": None},
            "source": {"type": "text", "nullable": False, "default": "'unknown'::text"},
            "filename": {"type": "text", "nullable": False, "default": None},
            "total_transactions": {"type": "integer", "nullable": False, "default": "0"},
            "review_required_count": {"type": "integer", "nullable": False, "default": "0"},
            "persisted_count": {"type": "integer", "nullable": False, "default": "0"},
            "error_message": {"type": "text", "nullable": True, "default": None},
            "created_at": {"type": "timestamp with time zone", "nullable": False, "default": "now()"},
            "started_at": {"type": "timestamp with time zone", "nullable": True, "default": None},
            "finished_at": {"type": "timestamp with time zone", "nullable": True, "default": None},
            "updated_at": {"type": "timestamp with time zone", "nullable": False, "default": "now()"},
        },
        "primary_key": ("id",),
        "checks": {
            "CHECK ((status = ANY (ARRAY['PENDING'::text, 'RUNNING'::text, 'SUCCEEDED'::text, 'FAILED'::text, 'REVIEW_REQUIRED'::text])))": {"validated": True},
        },
        "foreign_keys": {},
    },
    "import_job_runs": {
        "relation_kind": "r",
        "columns": {
            "id": {"type": "text", "nullable": False, "default": None},
            "job_id": {"type": "text", "nullable": False, "default": None},
            "step": {"type": "text", "nullable": False, "default": None},
            "final_status": {"type": "text", "nullable": False, "default": None},
            "input_summary": {"type": "jsonb", "nullable": False, "default": "'{}'::jsonb"},
            "model_version": {"type": "text", "nullable": True, "default": None},
            "output_summary": {"type": "jsonb", "nullable": False, "default": "'{}'::jsonb"},
            "error_message": {"type": "text", "nullable": True, "default": None},
            "retry_count": {"type": "integer", "nullable": False, "default": "0"},
            "started_at": {"type": "timestamp with time zone", "nullable": True, "default": None},
            "finished_at": {"type": "timestamp with time zone", "nullable": True, "default": None},
            "updated_at": {"type": "timestamp with time zone", "nullable": False, "default": "now()"},
        },
        "primary_key": ("id",),
        "checks": {
            "CHECK ((final_status = ANY (ARRAY['PENDING'::text, 'RUNNING'::text, 'SUCCEEDED'::text, 'FAILED'::text, 'REVIEW_REQUIRED'::text])))": {"validated": True},
        },
        "foreign_keys": {
            "FOREIGN KEY (job_id) REFERENCES import_jobs(id) ON DELETE CASCADE": {
                "columns": ("job_id",),
                "references": ("public", "import_jobs", ("id",)),
                "on_update": "NO ACTION",
                "on_delete": "CASCADE",
                "match_type": "SIMPLE",
                "validated": True,
                "deferrable": False,
                "deferred": False,
            },
        },
    },
}

CREATE_TABLE_SQL = {
    "transactions": """
CREATE TABLE public.transactions (
    id TEXT PRIMARY KEY, transaction_date DATE NOT NULL, amount NUMERIC(14, 2) NOT NULL,
    category TEXT NOT NULL, description TEXT NOT NULL, source TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('expense', 'income', 'transfer')),
    transaction_type TEXT, confidence DOUBLE PRECISION,
    requires_human_review BOOLEAN NOT NULL DEFAULT FALSE,
    raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)""",
    "import_jobs": """
CREATE TABLE public.import_jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'REVIEW_REQUIRED')),
    source TEXT NOT NULL DEFAULT 'unknown', filename TEXT NOT NULL,
    total_transactions INTEGER NOT NULL DEFAULT 0, review_required_count INTEGER NOT NULL DEFAULT 0,
    persisted_count INTEGER NOT NULL DEFAULT 0, error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)""",
    "import_job_runs": """
CREATE TABLE public.import_job_runs (
    id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES public.import_jobs(id) ON DELETE CASCADE,
    step TEXT NOT NULL,
    final_status TEXT NOT NULL CHECK (final_status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'REVIEW_REQUIRED')),
    input_summary JSONB NOT NULL DEFAULT '{}'::jsonb, model_version TEXT,
    output_summary JSONB NOT NULL DEFAULT '{}'::jsonb, error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0, started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)""",
}


def canonical_catalog_snapshot() -> dict[str, dict[str, Any]]:
    """Return a fresh exact catalog shape for unit and integration contract tests."""
    return deepcopy(CANONICAL_TABLES)


def _validate_table(table: str, actual: dict[str, Any]) -> None:
    expected = CANONICAL_TABLES[table]
    if actual.get("relation_kind") != expected["relation_kind"]:
        raise SchemaCompatibilityError(f"incompatible schema contract: {table}.relation_kind")
    for column, contract in expected["columns"].items():
        if actual.get("columns", {}).get(column) != contract:
            raise SchemaCompatibilityError(f"incompatible schema contract: {table}.{column}")
    if set(actual.get("columns", {})) != set(expected["columns"]):
        raise SchemaCompatibilityError(f"incompatible schema contract: {table}.columns")
    if tuple(actual.get("primary_key", ())) != expected["primary_key"]:
        raise SchemaCompatibilityError(f"incompatible schema contract: {table}.primary_key")
    if set(actual.get("checks", {})) != set(expected["checks"]):
        raise SchemaCompatibilityError(f"incompatible schema contract: {table}.checks")
    if actual.get("checks", {}) != expected["checks"]:
        raise SchemaCompatibilityError(f"incompatible schema contract: {table}.checks")
    if set(actual.get("foreign_keys", {})) != set(expected["foreign_keys"]):
        expected_fks = expected["foreign_keys"]
        if len(expected_fks) == 1:
            column = next(iter(expected_fks.values()))["columns"][0]
            raise SchemaCompatibilityError(f"incompatible schema contract: {table}.{column}")
        raise SchemaCompatibilityError(f"incompatible schema contract: {table}.foreign_keys")
    if actual.get("foreign_keys", {}) != expected["foreign_keys"]:
        raise SchemaCompatibilityError(f"incompatible schema contract: {table}.foreign_keys")


def validate_catalog_snapshot(snapshot: dict[str, dict[str, Any]]) -> None:
    """Fail closed unless every current application object matches exactly."""
    if set(snapshot) != set(CANONICAL_TABLES):
        raise SchemaCompatibilityError("incompatible schema contract: required public tables")
    for table in CANONICAL_TABLES:
        _validate_table(table, snapshot[table])


def _require_psycopg():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ModuleNotFoundError as exc:  # pragma: no cover - environment failure
        raise SchemaInitializationError("PostgreSQL driver is unavailable") from None
    return psycopg, dict_row


def _catalog_snapshot(cursor) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for table in CANONICAL_TABLES:
        cursor.execute("SELECT to_regclass(%s) AS relation", (f"public.{table}",))
        if cursor.fetchone()["relation"] is None:
            continue
        cursor.execute(
            "SELECT c.relkind FROM pg_class AS c WHERE c.oid = to_regclass(%s)",
            (f"public.{table}",),
        )
        relation_kind = cursor.fetchone()["relkind"]
        cursor.execute(
            """SELECT a.attname AS name, format_type(a.atttypid, a.atttypmod) AS type,
                      NOT a.attnotnull AS nullable, pg_get_expr(d.adbin, d.adrelid) AS default
                 FROM pg_attribute a LEFT JOIN pg_attrdef d
                   ON d.adrelid = a.attrelid AND d.adnum = a.attnum
                WHERE a.attrelid = %s::regclass AND a.attnum > 0 AND NOT a.attisdropped
                ORDER BY a.attnum""",
            (f"public.{table}",),
        )
        columns = {row["name"]: {"type": row["type"], "nullable": row["nullable"], "default": row["default"]} for row in cursor.fetchall()}
        cursor.execute(
            """SELECT a.attname AS name FROM pg_constraint c
                 JOIN unnest(c.conkey) WITH ORDINALITY AS keys(attnum, ordinal) ON TRUE
                 JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = keys.attnum
                WHERE c.conrelid = %s::regclass AND c.contype = 'p' ORDER BY keys.ordinal""",
            (f"public.{table}",),
        )
        primary_key = tuple(row["name"] for row in cursor.fetchall())
        cursor.execute(
            """SELECT pg_get_constraintdef(c.oid) AS definition, c.convalidated AS validated
                 FROM pg_constraint AS c
                WHERE c.conrelid = %s::regclass AND c.contype = 'c'""",
            (f"public.{table}",),
        )
        checks: dict[str, dict[str, bool]] = {}
        for row in cursor.fetchall():
            definition = row["definition"]
            if definition in checks:
                raise SchemaCompatibilityError(f"incompatible schema contract: {table}.checks")
            checks[definition] = {"validated": bool(row["validated"])}
        cursor.execute(
            """SELECT pg_get_constraintdef(c.oid) AS definition,
                      array_agg(source.attname ORDER BY source_keys.ordinality) AS columns,
                      ns.nspname AS schema_name, rel.relname AS table_name,
                      array_agg(target.attname ORDER BY target_keys.ordinality) AS target_columns,
                      c.confupdtype AS update_action, c.confdeltype AS delete_action,
                      c.confmatchtype AS match_type, c.convalidated AS validated,
                      c.condeferrable AS deferrable, c.condeferred AS deferred
                 FROM pg_constraint AS c
                 JOIN unnest(c.conkey) WITH ORDINALITY AS source_keys(attnum, ordinality) ON TRUE
                 JOIN pg_attribute AS source ON source.attrelid = c.conrelid AND source.attnum = source_keys.attnum
                 JOIN unnest(c.confkey) WITH ORDINALITY AS target_keys(attnum, ordinality)
                   ON target_keys.ordinality = source_keys.ordinality
                 JOIN pg_attribute AS target ON target.attrelid = c.confrelid AND target.attnum = target_keys.attnum
                 JOIN pg_class AS rel ON rel.oid = c.confrelid
                 JOIN pg_namespace AS ns ON ns.oid = rel.relnamespace
                WHERE c.conrelid = %s::regclass AND c.contype = 'f'
                GROUP BY c.oid, ns.nspname, rel.relname""",
            (f"public.{table}",),
        )
        action_names = {"c": "CASCADE", "a": "NO ACTION", "r": "RESTRICT", "n": "SET NULL", "d": "SET DEFAULT"}
        match_names = {"s": "SIMPLE", "f": "FULL", "p": "PARTIAL"}
        foreign_keys: dict[str, dict[str, Any]] = {}
        for row in cursor.fetchall():
            definition = row["definition"]
            if definition in foreign_keys:
                expected_fks = CANONICAL_TABLES[table]["foreign_keys"]
                if len(expected_fks) == 1:
                    column = next(iter(expected_fks.values()))["columns"][0]
                    raise SchemaCompatibilityError(f"incompatible schema contract: {table}.{column}")
                raise SchemaCompatibilityError(f"incompatible schema contract: {table}.foreign_keys")
            foreign_keys[definition] = {
                "columns": tuple(row["columns"]),
                "references": (row["schema_name"], row["table_name"], tuple(row["target_columns"])),
                "on_update": action_names[row["update_action"]],
                "on_delete": action_names[row["delete_action"]],
                "match_type": match_names[row["match_type"]],
                "validated": bool(row["validated"]),
                "deferrable": bool(row["deferrable"]),
                "deferred": bool(row["deferred"]),
            }
        snapshot[table] = {"relation_kind": relation_kind, "columns": columns, "primary_key": primary_key, "checks": checks, "foreign_keys": foreign_keys}
    return snapshot


def _require_url(database_url: str | None, error_type: type[Exception]) -> str:
    if not database_url or not database_url.strip():
        raise error_type("DATABASE_URL is required")
    return database_url.strip()


def initialize_database(database_url: str | None) -> None:
    """Create only missing compatible tables in one advisory-locked transaction."""
    database_url = _require_url(database_url, SchemaInitializationError)
    try:
        psycopg, dict_row = _require_psycopg()
        with psycopg.connect(database_url, row_factory=dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (ADVISORY_LOCK_NAME,))
                existing = _catalog_snapshot(cursor)
                for table, actual in existing.items():
                    _validate_table(table, actual)
                for table in CANONICAL_TABLES:
                    if table not in existing:
                        cursor.execute(CREATE_TABLE_SQL[table])
                validate_catalog_snapshot(_catalog_snapshot(cursor))
            conn.commit()
    except SchemaInitializationError:
        raise
    except Exception as exc:
        raise SchemaInitializationError("database initialization failed; inspect local PostgreSQL logs") from None


def assert_database_ready(database_url: str | None) -> None:
    """Read-only schema validation for configured application startup."""
    database_url = _require_url(database_url, SchemaReadinessError)
    try:
        psycopg, dict_row = _require_psycopg()
        with psycopg.connect(database_url, row_factory=dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute("BEGIN TRANSACTION READ ONLY")
                validate_catalog_snapshot(_catalog_snapshot(cursor))
                conn.rollback()
    except Exception as exc:
        if isinstance(exc, SchemaReadinessError):
            raise
        raise SchemaReadinessError(
            "database schema is not ready; run `python backend/scripts/init_database.py`"
        ) from None
