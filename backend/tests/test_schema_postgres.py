"""Real PostgreSQL 16 integration contracts for the explicit schema boundary.

This suite only runs under the disposable private-socket cluster provided by
``/root/workspace/readme-acceptance/run-schema-postgres.sh``.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

import api_server
import database
import schema


DATABASE_URL_ENV = "SCHEMA_POSTGRES_TEST_DSN"
ROLE_NAME = "financial_business_schema_test"


def _database_url() -> str:
    value = os.getenv(DATABASE_URL_ENV)
    if not value:
        pytest.skip(f"{DATABASE_URL_ENV} is required for the disposable PostgreSQL gate")
    return value


@pytest.fixture
def database_url() -> str:
    return _database_url()


def _reset_public_schema(database_url: str) -> None:
    with psycopg.connect(database_url, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS public CASCADE")
            cursor.execute("CREATE SCHEMA public AUTHORIZATION postgres")


@pytest.fixture(autouse=True)
def isolated_public_schema(database_url: str):
    _reset_public_schema(database_url)
    try:
        yield
    finally:
        _reset_public_schema(database_url)
        with psycopg.connect(database_url, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP ROLE IF EXISTS {ROLE_NAME}")


def _relations(database_url: str) -> tuple[str, ...]:
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.relname
                FROM pg_class AS c
                JOIN pg_namespace AS n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relname IN ('transactions', 'import_jobs', 'import_job_runs')
                ORDER BY c.relname
                """
            )
            return tuple(row[0] for row in cursor.fetchall())


def _portable_catalog_fingerprint(database_url: str) -> tuple[tuple[str, int, str, str], ...]:
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.relname,
                       c.oid,
                       COALESCE(string_agg(a.attname || ':' || format_type(a.atttypid, a.atttypmod)
                           || ':' || a.attnotnull::text || ':' || COALESCE(pg_get_expr(d.adbin, d.adrelid), ''),
                           '|' ORDER BY a.attnum), ''),
                       COALESCE((
                           SELECT string_agg(pg_get_constraintdef(con.oid), '|' ORDER BY con.contype, con.conname)
                           FROM pg_constraint AS con
                           WHERE con.conrelid = c.oid
                       ), '')
                FROM pg_class AS c
                JOIN pg_namespace AS n ON n.oid = c.relnamespace
                LEFT JOIN pg_attribute AS a
                    ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
                LEFT JOIN pg_attrdef AS d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
                WHERE n.nspname = 'public'
                  AND c.relname IN ('transactions', 'import_jobs', 'import_job_runs')
                GROUP BY c.relname, c.oid
                ORDER BY c.relname
                """
            )
            return tuple((str(name), int(oid), str(columns), str(constraints)) for name, oid, columns, constraints in cursor.fetchall())


def _run_initializer(database_url: str) -> subprocess.CompletedProcess[str]:
    script = Path(__file__).parents[1] / "scripts" / "init_database.py"
    environment = dict(os.environ)
    environment["DATABASE_URL"] = database_url
    return subprocess.run(
        [sys.executable, str(script)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env=environment,
    )


def _canonical_transactions_sql(*, amount_type: str = "NUMERIC(14, 2)", review_default: str = "FALSE", primary_key: bool = True, type_check: str = "type IN ('expense', 'income', 'transfer')") -> str:
    identity = "id TEXT PRIMARY KEY" if primary_key else "id TEXT NOT NULL"
    return f"""
        CREATE TABLE public.transactions (
            {identity}, transaction_date DATE NOT NULL, amount {amount_type} NOT NULL,
            category TEXT NOT NULL, description TEXT NOT NULL, source TEXT NOT NULL,
            type TEXT NOT NULL CHECK ({type_check}),
            transaction_type TEXT, confidence DOUBLE PRECISION,
            requires_human_review BOOLEAN NOT NULL DEFAULT {review_default},
            raw_data JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """


def test_empty_schema_startup_fails_without_creating_any_app_table(database_url, monkeypatch):
    """Configured application startup fails closed; readiness never bootstraps schema."""
    monkeypatch.setenv("DATABASE_URL", database_url)

    with pytest.raises(schema.SchemaReadinessError, match="init_database.py"):
        with TestClient(api_server.app):
            pass

    assert _relations(database_url) == ()


def test_explicit_cli_initializes_exact_catalog_and_empty_app_serves_queries(database_url, monkeypatch):
    """Only the explicit CLI may create the three compatible public tables."""
    result = _run_initializer(database_url)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "Financial Assistant public schema is ready."
    schema.assert_database_ready(database_url)
    with psycopg.connect(database_url, row_factory=psycopg.rows.dict_row) as connection:
        with connection.cursor() as cursor:
            schema.validate_catalog_snapshot(schema._catalog_snapshot(cursor))

    monkeypatch.setenv("DATABASE_URL", database_url)
    with TestClient(api_server.app) as client:
        response = client.get("/api/agent/months")
    assert response.status_code == 200, response.text
    assert response.json() == {"success": True, "months": []}


def test_repeated_explicit_init_preserves_synthetic_stable_row_and_catalog(database_url):
    """A compatible repeat performs no replacement, rehashing, or data loss."""
    assert _run_initializer(database_url).returncode == 0
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.transactions (
                    id, transaction_date, amount, category, description, source, type,
                    requires_human_review, raw_data
                ) VALUES (
                    'stable-synthetic-transaction-id', '2026-04-11', -12.34, 'dining',
                    'synthetic retained row', 'synthetic', 'expense', true,
                    '{"stable_id": "stable-synthetic-transaction-id", "note": "preserve"}'::jsonb
                )
                """
            )
        connection.commit()

    before_catalog = _portable_catalog_fingerprint(database_url)
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, amount::text, raw_data::text FROM public.transactions")
            before_row = cursor.fetchone()

    result = _run_initializer(database_url)

    assert result.returncode == 0, result.stderr
    assert _portable_catalog_fingerprint(database_url) == before_catalog
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, amount::text, raw_data::text FROM public.transactions")
            assert cursor.fetchone() == before_row == (
                "stable-synthetic-transaction-id",
                "-12.34",
                '{"note": "preserve", "stable_id": "stable-synthetic-transaction-id"}',
            )


def test_concurrent_explicit_initializers_serialize_under_database_lock(database_url, monkeypatch):
    """Separate connections cannot interleave the catalog check/create critical section."""
    original_snapshot = schema._catalog_snapshot
    reached_lock_protected_snapshot = 0
    peak_inside_snapshot = 0
    counter_lock = threading.Lock()

    def slow_snapshot(cursor):
        nonlocal reached_lock_protected_snapshot, peak_inside_snapshot
        with counter_lock:
            reached_lock_protected_snapshot += 1
            peak_inside_snapshot = max(peak_inside_snapshot, reached_lock_protected_snapshot)
        try:
            cursor.execute("SELECT pg_sleep(0.12)")
            return original_snapshot(cursor)
        finally:
            with counter_lock:
                reached_lock_protected_snapshot -= 1

    monkeypatch.setattr(schema, "_catalog_snapshot", slow_snapshot)
    barrier = threading.Barrier(2)

    def initialize_from_separate_connection():
        barrier.wait(timeout=10)
        schema.initialize_database(database_url)

    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(initialize_from_separate_connection) for _ in range(2)]
        for future in futures:
            assert future.result(timeout=30) is None
    elapsed = time.monotonic() - start

    assert peak_inside_snapshot == 1
    assert elapsed >= 0.40
    schema.assert_database_ready(database_url)


@pytest.mark.parametrize(
    ("case", "prepare"),
    [
        ("type", lambda cursor: cursor.execute(_canonical_transactions_sql(amount_type="DOUBLE PRECISION"))),
        ("default", lambda cursor: cursor.execute(_canonical_transactions_sql(review_default="TRUE"))),
        ("primary-key", lambda cursor: cursor.execute(_canonical_transactions_sql(primary_key=False))),
        ("check", lambda cursor: cursor.execute(_canonical_transactions_sql(type_check="type IN ('expense', 'income')"))),
        ("foreign-key", None),
    ],
    ids=["type", "default", "primary-key", "check", "foreign-key"],
)
def test_incompatible_existing_catalog_is_rejected_without_any_mutation(database_url, case, prepare):
    """Type/default/key/check/FK drift is never silently repaired or stamped compatible."""
    if case == "foreign-key":
        assert _run_initializer(database_url).returncode == 0
        with psycopg.connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute("ALTER TABLE public.import_job_runs DROP CONSTRAINT import_job_runs_job_id_fkey")
                cursor.execute(
                    """
                    ALTER TABLE public.import_job_runs
                    ADD CONSTRAINT import_job_runs_job_id_fkey
                    FOREIGN KEY (job_id) REFERENCES public.transactions(id) ON DELETE CASCADE
                    """
                )
            connection.commit()
    else:
        with psycopg.connect(database_url) as connection:
            with connection.cursor() as cursor:
                assert prepare is not None
                prepare(cursor)
            connection.commit()

    before = _portable_catalog_fingerprint(database_url)
    with pytest.raises(schema.SchemaInitializationError, match="initialization failed|incompatible schema contract"):
        schema.initialize_database(database_url)

    assert _portable_catalog_fingerprint(database_url) == before
    if case == "foreign-key":
        assert _relations(database_url) == ("import_job_runs", "import_jobs", "transactions")
    else:
        assert _relations(database_url) == ("transactions",)


def test_injected_partial_initializer_failure_rolls_back_all_new_ddl(database_url, monkeypatch):
    """A failure after the first CREATE leaves no partially-initialized public schema."""
    monkeypatch.setitem(schema.CREATE_TABLE_SQL, "import_jobs", "SELECT 1 / 0")

    with pytest.raises(schema.SchemaInitializationError, match="initialization failed"):
        schema.initialize_database(database_url)

    assert _relations(database_url) == ()


def test_restricted_business_role_has_no_ddl_and_can_start_and_query_prepared_schema(database_url, monkeypatch):
    """Runtime role uses read-only startup and real business SELECTs without CREATE privilege."""
    assert _run_initializer(database_url).returncode == 0
    with psycopg.connect(database_url, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.transactions (
                    id, transaction_date, amount, category, description, source, type, raw_data
                ) VALUES (
                    'restricted-role-query-row', '2026-04-15', -1.00, 'other', 'role query',
                    'synthetic', 'expense', '{}'::jsonb
                )
                """
            )
            cursor.execute(f"CREATE ROLE {ROLE_NAME} LOGIN")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {ROLE_NAME}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO {ROLE_NAME}")
            cursor.execute(f"REVOKE CREATE ON SCHEMA public FROM {ROLE_NAME}")

    role_dsn = psycopg.conninfo.make_conninfo(database_url, user=ROLE_NAME)
    schema.assert_database_ready(role_dsn)
    with psycopg.connect(role_dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT has_schema_privilege(current_user, 'public', 'CREATE')")
            assert cursor.fetchone() == (False,)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cursor.execute("CREATE TABLE public.role_must_not_create (id integer)")

    monkeypatch.setenv("DATABASE_URL", role_dsn)
    assert database.get_available_months() == ["2026-04"]
    with TestClient(api_server.app) as client:
        response = client.get("/api/agent/months")
    assert response.status_code == 200, response.text
    assert response.json() == {"success": True, "months": ["2026-04"]}


def test_business_queries_ignore_search_path_shadow_tables(database_url, monkeypatch):
    """Readiness of public cannot be bypassed by a tenant shadow relation at runtime."""
    assert _run_initializer(database_url).returncode == 0
    with psycopg.connect(database_url, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO public.transactions
                    (id, transaction_date, amount, category, description, source, type, raw_data)
                   VALUES ('public-row', '2026-04-15', -1, 'other', 'public', 'synthetic', 'expense', '{}'::jsonb)"""
            )
            cursor.execute("CREATE SCHEMA tenant")
            cursor.execute("CREATE TABLE tenant.transactions (transaction_date date)")

    shadow_dsn = database_url + "&options=-csearch_path%3Dtenant%2Cpublic"
    monkeypatch.setenv("DATABASE_URL", shadow_dsn)

    assert database.get_available_months() == ["2026-04"]


def test_readiness_rejects_extra_check_constraint(database_url):
    """Every additional CHECK changes write semantics and must fail closed."""
    assert _run_initializer(database_url).returncode == 0
    with psycopg.connect(database_url, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE public.transactions ADD CONSTRAINT transactions_amount_check CHECK (amount < 0)")

    with pytest.raises(schema.SchemaReadinessError, match="init_database.py"):
        schema.assert_database_ready(database_url)


def test_readiness_rejects_not_valid_canonical_check(database_url):
    """A canonical-looking but unvalidated CHECK is incompatible."""
    assert _run_initializer(database_url).returncode == 0
    with psycopg.connect(database_url, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE public.transactions DROP CONSTRAINT transactions_type_check")
            cursor.execute(
                """ALTER TABLE public.transactions ADD CONSTRAINT transactions_type_check
                   CHECK (type IN ('expense', 'income', 'transfer')) NOT VALID"""
            )

    with pytest.raises(schema.SchemaReadinessError, match="init_database.py"):
        schema.assert_database_ready(database_url)


def test_readiness_rejects_nonordinary_relation_before_column_contract(database_url):
    """Relation kind is an explicit boundary, rather than incidental column drift."""
    with psycopg.connect(database_url, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("CREATE VIEW public.transactions AS SELECT NULL::text AS id")

    with pytest.raises(schema.SchemaReadinessError, match="init_database.py") as error:
        schema.assert_database_ready(database_url)
    assert "relation_kind" not in str(error.value)  # public diagnostic remains sanitized

    with psycopg.connect(database_url, row_factory=psycopg.rows.dict_row) as connection:
        with connection.cursor() as cursor:
            with pytest.raises(schema.SchemaCompatibilityError, match="transactions.relation_kind"):
                schema._validate_table("transactions", schema._catalog_snapshot(cursor)["transactions"])


def test_readiness_rejects_foreign_key_with_changed_update_contract(database_url):
    """FK update/match/deferral semantics are part of the exact compatibility contract."""
    assert _run_initializer(database_url).returncode == 0
    with psycopg.connect(database_url, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE public.import_job_runs DROP CONSTRAINT import_job_runs_job_id_fkey")
            cursor.execute(
                """ALTER TABLE public.import_job_runs
                   ADD CONSTRAINT import_job_runs_job_id_fkey
                   FOREIGN KEY (job_id) REFERENCES public.import_jobs(id)
                   ON UPDATE CASCADE ON DELETE CASCADE"""
            )

    with pytest.raises(schema.SchemaReadinessError, match="init_database.py"):
        schema.assert_database_ready(database_url)
