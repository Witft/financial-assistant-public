#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PostgreSQL persistence layer for the financial assistant backend.

The API remains backward-compatible when DATABASE_URL is not configured: parsing
still returns transactions, but persistence is skipped. When DATABASE_URL is set,
parsed transactions are upserted into PostgreSQL for future Agent-facing queries.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime
from typing import Any, Iterable


UPSERT_TRANSACTION_SQL = """
INSERT INTO public.transactions (
    id,
    transaction_date,
    amount,
    category,
    description,
    source,
    type,
    transaction_type,
    confidence,
    requires_human_review,
    raw_data
) VALUES (
    %(id)s,
    %(transaction_date)s,
    %(amount)s,
    %(category)s,
    %(description)s,
    %(source)s,
    %(type)s,
    %(transaction_type)s,
    %(confidence)s,
    %(requires_human_review)s,
    %(raw_data)s
)
ON CONFLICT (id) DO UPDATE SET
    transaction_date = EXCLUDED.transaction_date,
    amount = EXCLUDED.amount,
    category = EXCLUDED.category,
    description = EXCLUDED.description,
    source = EXCLUDED.source,
    type = EXCLUDED.type,
    transaction_type = EXCLUDED.transaction_type,
    confidence = EXCLUDED.confidence,
    requires_human_review = EXCLUDED.requires_human_review,
    raw_data = EXCLUDED.raw_data,
    updated_at = NOW();
"""

UPDATE_TRANSACTION_CATEGORY_SQL = """
UPDATE public.transactions
SET
    category = %(category)s,
    confidence = %(confidence)s,
    requires_human_review = FALSE,
    raw_data = jsonb_set(
        jsonb_set(COALESCE(raw_data, '{}'::jsonb), '{category}', to_jsonb(%(category)s::text), true),
        '{requires_human_review}',
        'false'::jsonb,
        true
    ),
    updated_at = NOW()
WHERE id = %(transaction_id)s;
"""

INSERT_IMPORT_JOB_SQL = """
INSERT INTO public.import_jobs (
    id,
    status,
    source,
    filename,
    started_at
) VALUES (
    %(id)s,
    %(status)s,
    %(source)s,
    %(filename)s,
    %(started_at)s
);
"""

UPDATE_IMPORT_JOB_STATUS_SQL = """
UPDATE public.import_jobs
SET
    status = %(status)s,
    updated_at = NOW(),
    started_at = COALESCE(started_at, %(started_at)s)
WHERE id = %(job_id)s;
"""

FINALIZE_IMPORT_JOB_SQL = """
UPDATE public.import_jobs
SET
    status = %(status)s,
    total_transactions = %(total_transactions)s,
    review_required_count = %(review_required_count)s,
    persisted_count = %(persisted_count)s,
    error_message = %(error_message)s,
    finished_at = NOW(),
    updated_at = NOW(),
    started_at = COALESCE(started_at, %(started_at)s)
WHERE id = %(job_id)s;
"""

INSERT_IMPORT_JOB_RUN_SQL = """
INSERT INTO public.import_job_runs (
    id,
    job_id,
    step,
    final_status,
    input_summary,
    model_version,
    output_summary,
    error_message,
    retry_count,
    started_at
) VALUES (
    %(id)s,
    %(job_id)s,
    %(step)s,
    %(final_status)s,
    %(input_summary)s,
    %(model_version)s,
    %(output_summary)s,
    %(error_message)s,
    %(retry_count)s,
    %(started_at)s
);
"""

FINALIZE_IMPORT_JOB_RUN_SQL = """
UPDATE public.import_job_runs
SET
    step = %(step)s,
    final_status = %(final_status)s,
    output_summary = %(output_summary)s,
    error_message = %(error_message)s,
    finished_at = NOW(),
    updated_at = NOW()
WHERE id = %(run_id)s;
"""


def get_database_url() -> str | None:
    """Return configured PostgreSQL DSN, if any."""
    value = os.getenv("DATABASE_URL")
    return value.strip() if value and value.strip() else None


def is_database_enabled() -> bool:
    """Whether persistence should be attempted."""
    return get_database_url() is not None


def generate_transaction_id(transaction: dict[str, Any]) -> str:
    """Generate a stable ID for duplicate-resistant upsert.

    Exported bills often do not expose a single trustworthy universal ID across
    Alipay and WeChat formats, so we hash the normalized business identity of a
    parsed transaction. This keeps repeated uploads idempotent.
    """
    identity = {
        "source": transaction.get("source", ""),
        "date": str(transaction.get("date", "")).split(" ")[0],
        "description": transaction.get("description", ""),
        "amount": float(transaction.get("amount", 0) or 0),
        "type": transaction.get("type", ""),
    }
    digest = hashlib.sha256(
        json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    return f"tx_{digest}"


def normalize_transaction_date(raw_date: Any) -> str:
    """Normalize parser date/time output to YYYY-MM-DD for database storage."""
    text = str(raw_date or "").strip()
    return text.split(" ")[0] if " " in text else text


def build_transaction_record(transaction: dict[str, Any]) -> dict[str, Any]:
    """Convert parser output into a PostgreSQL transaction row."""
    return {
        "id": transaction.get("id") or generate_transaction_id(transaction),
        "transaction_date": normalize_transaction_date(transaction.get("date")),
        "amount": float(transaction.get("amount", 0) or 0),
        "category": transaction.get("category") or "other",
        "description": transaction.get("description") or "",
        "source": transaction.get("source") or "unknown",
        "type": transaction.get("type") or "transfer",
        "transaction_type": transaction.get("transaction_type"),
        "confidence": transaction.get("confidence"),
        "requires_human_review": bool(transaction.get("requires_human_review", False)),
        "raw_data": dict(transaction),
    }


def _json_adapter(value: dict[str, Any]):
    """Adapt JSON for psycopg v3 when available."""
    try:
        from psycopg.types.json import Jsonb
    except ModuleNotFoundError as exc:  # pragma: no cover - only hit in misconfigured runtime
        raise RuntimeError("psycopg is required when DATABASE_URL is configured") from exc
    return Jsonb(value)


def _require_psycopg():
    try:
        import psycopg
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on runtime package state
        raise RuntimeError("psycopg is required when DATABASE_URL is configured") from exc
    return psycopg


def save_transactions(transactions: Iterable[dict[str, Any]]) -> int:
    """Upsert parsed transactions into PostgreSQL.

    Returns the number of records attempted. If DATABASE_URL is absent, this is a
    no-op so local parsing/tests remain lightweight.
    """
    database_url = get_database_url()
    records = [build_transaction_record(tx) for tx in transactions]

    if not database_url or not records:
        return 0

    psycopg = _require_psycopg()

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for record in records:
                db_record = dict(record)
                db_record["raw_data"] = _json_adapter(db_record["raw_data"])
                cur.execute(UPSERT_TRANSACTION_SQL, db_record)
        conn.commit()

    return len(records)


def create_import_job(*, filename: str, source: str = "unknown") -> str:
    """Create an import job in PENDING state and return its ID."""
    database_url = get_database_url()
    job_id = f"job_{uuid.uuid4().hex[:16]}"

    if not database_url:
        return job_id

    psycopg = _require_psycopg()

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                INSERT_IMPORT_JOB_SQL,
                {
                    "id": job_id,
                    "status": "PENDING",
                    "source": source or "unknown",
                    "filename": filename or "unknown",
                    "started_at": None,
                },
            )
        conn.commit()

    return job_id


def create_import_job_run(
    job_id: str,
    *,
    step: str,
    input_summary: dict[str, Any] | None = None,
    model_version: str | None = None,
    retry_count: int = 0,
) -> str:
    """Create the minimal execution record for an import job."""
    database_url = get_database_url()
    run_id = f"run_{uuid.uuid4().hex[:16]}"

    if not database_url:
        return run_id

    psycopg = _require_psycopg()

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                INSERT_IMPORT_JOB_RUN_SQL,
                {
                    "id": run_id,
                    "job_id": job_id,
                    "step": step,
                    "final_status": "RUNNING",
                    "input_summary": _json_adapter(input_summary or {}),
                    "model_version": model_version,
                    "output_summary": _json_adapter({}),
                    "error_message": None,
                    "retry_count": int(retry_count),
                    "started_at": datetime.utcnow(),
                },
            )
        conn.commit()

    return run_id


def finalize_import_job_run(
    run_id: str,
    *,
    step: str,
    final_status: str,
    output_summary: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    """Finalize the latest execution record for an import job."""
    database_url = get_database_url()
    if not database_url:
        return

    psycopg = _require_psycopg()

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                FINALIZE_IMPORT_JOB_RUN_SQL,
                {
                    "run_id": run_id,
                    "step": step,
                    "final_status": final_status,
                    "output_summary": _json_adapter(output_summary or {}),
                    "error_message": error_message,
                },
            )
            if cur.rowcount == 0:
                raise ValueError(f"未找到导入任务执行记录: {run_id}")
        conn.commit()


def update_import_job_status(job_id: str, status: str) -> None:
    """Update an import job to an in-flight state such as RUNNING."""
    database_url = get_database_url()
    if not database_url:
        return

    psycopg = _require_psycopg()

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                UPDATE_IMPORT_JOB_STATUS_SQL,
                {
                    "job_id": job_id,
                    "status": status,
                    "started_at": datetime.utcnow() if status == "RUNNING" else None,
                },
            )
            if cur.rowcount == 0:
                raise ValueError(f"未找到导入任务: {job_id}")
        conn.commit()


def finalize_import_job(
    job_id: str,
    *,
    status: str,
    total_transactions: int,
    review_required_count: int,
    persisted_count: int,
    error_message: str | None = None,
) -> None:
    """Finalize an import job into SUCCEEDED / REVIEW_REQUIRED / FAILED."""
    database_url = get_database_url()
    if not database_url:
        return

    psycopg = _require_psycopg()

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                FINALIZE_IMPORT_JOB_SQL,
                {
                    "job_id": job_id,
                    "status": status,
                    "total_transactions": int(total_transactions),
                    "review_required_count": int(review_required_count),
                    "persisted_count": int(persisted_count),
                    "error_message": error_message,
                    "started_at": datetime.utcnow(),
                },
            )
            if cur.rowcount == 0:
                raise ValueError(f"未找到导入任务: {job_id}")
        conn.commit()


def complete_import_job_if_review_finished(job_id: str) -> bool:
    """Mark a REVIEW_REQUIRED import job as SUCCEEDED when no pending-review rows remain."""
    database_url = get_database_url()
    if not database_url:
        return False

    psycopg = _require_psycopg()

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM public.transactions
                WHERE COALESCE(raw_data->>'import_job_id', '') = %s
                  AND requires_human_review = TRUE;
                """,
                (job_id,),
            )
            pending_count = int(cur.fetchone()[0])
            if pending_count > 0:
                return False

            cur.execute(
                """
                UPDATE public.import_jobs
                SET
                    status = 'SUCCEEDED',
                    review_required_count = 0,
                    finished_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s;
                """,
                (job_id,),
            )
        conn.commit()

    return True


def update_transaction_category(transaction_id: str, category: str, confidence: float = 1.0) -> None:
    """Persist a human-reviewed category correction back into PostgreSQL."""
    database_url = get_database_url()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    psycopg = _require_psycopg()

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                UPDATE_TRANSACTION_CATEGORY_SQL,
                {
                    "transaction_id": transaction_id,
                    "category": category,
                    "confidence": confidence,
                },
            )
            if cur.rowcount == 0:
                raise ValueError(f"未找到交易: {transaction_id}")
        conn.commit()


def _month_range(month: str) -> tuple[str, str]:
    """Return [start, next_month) date strings for a YYYY-MM month."""
    try:
        start = datetime.strptime(month, "%Y-%m")
    except ValueError as exc:
        raise ValueError("月份格式错误，请使用 YYYY-MM，例如 2026-04") from exc

    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def get_monthly_summary(month: str) -> dict[str, Any]:
    """Query a structured monthly financial summary from PostgreSQL."""
    database_url = get_database_url()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    start_date, end_date = _month_range(month)
    psycopg = _require_psycopg()

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) AS income,
                    COALESCE(SUM(CASE WHEN type = 'expense' THEN -amount ELSE 0 END), 0) AS expense,
                    COALESCE(SUM(CASE WHEN type = 'transfer' THEN amount ELSE 0 END), 0) AS transfer,
                    COUNT(*) AS transaction_count
                FROM public.transactions
                WHERE transaction_date >= %s AND transaction_date < %s;
                """,
                (start_date, end_date),
            )
            income, expense, transfer, transaction_count = cur.fetchone()

            cur.execute(
                """
                SELECT
                    category,
                    COALESCE(SUM(-amount), 0) AS amount,
                    COUNT(*) AS transaction_count
                FROM public.transactions
                WHERE transaction_date >= %s
                  AND transaction_date < %s
                  AND type = 'expense'
                GROUP BY category
                ORDER BY amount DESC;
                """,
                (start_date, end_date),
            )
            category_expenses = [
                {
                    "category": row[0],
                    "amount": float(row[1]),
                    "transaction_count": int(row[2]),
                }
                for row in cur.fetchall()
            ]

    income_value = float(income)
    expense_value = float(expense)
    transfer_value = float(transfer)
    return {
        "month": month,
        "summary": {
            "income": income_value,
            "expense": expense_value,
            "transfer": transfer_value,
            "balance": income_value - expense_value,
            "transaction_count": int(transaction_count),
        },
        "category_expenses": category_expenses,
    }


def get_transactions(
    *,
    month: str,
    category: str | None = None,
    source: str | None = None,
    transaction_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Query transaction details for Agent drill-down questions."""
    database_url = get_database_url()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    start_date, end_date = _month_range(month)
    safe_limit = max(1, min(int(limit), 500))
    where_clauses = ["transaction_date >= %s", "transaction_date < %s"]
    params: list[Any] = [start_date, end_date]

    if category:
        where_clauses.append("category = %s")
        params.append(category)
    if source:
        where_clauses.append("source = %s")
        params.append(source)
    if transaction_type:
        where_clauses.append("type = %s")
        params.append(transaction_type)

    params.append(safe_limit)
    psycopg = _require_psycopg()

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    id,
                    transaction_date,
                    amount,
                    category,
                    description,
                    source,
                    type,
                    transaction_type,
                    confidence,
                    requires_human_review,
                    COALESCE(raw_data->>'import_job_id', NULL) AS import_job_id
                FROM public.transactions
                WHERE {' AND '.join(where_clauses)}
                ORDER BY transaction_date DESC, updated_at DESC
                LIMIT %s;
                """,
                tuple(params),
            )
            rows = cur.fetchall()

    return [
        {
            "id": row[0],
            "date": row[1].isoformat() if hasattr(row[1], "isoformat") else str(row[1]),
            "amount": float(row[2]),
            "category": row[3],
            "description": row[4],
            "source": row[5],
            "type": row[6],
            "transaction_type": row[7],
            "confidence": float(row[8]) if row[8] is not None else None,
            "requires_human_review": bool(row[9]),
            "import_job_id": row[10],
        }
        for row in rows
    ]


def _serialize_optional_datetime(value: Any) -> str | None:
    """Serialize PostgreSQL timestamp-like values to ISO strings."""
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _map_import_job_run_row(row: tuple[Any, ...]) -> dict[str, Any]:
    """Map an import_job_runs row to an API-friendly dict."""
    return {
        "id": row[0],
        "job_id": row[1],
        "step": row[2],
        "final_status": row[3],
        "input_summary": row[4] or {},
        "model_version": row[5],
        "output_summary": row[6] or {},
        "error_message": row[7],
        "retry_count": int(row[8]),
        "started_at": _serialize_optional_datetime(row[9]),
        "finished_at": _serialize_optional_datetime(row[10]),
        "updated_at": _serialize_optional_datetime(row[11]),
    }


def get_latest_import_job_run(job_id: str) -> dict[str, Any] | None:
    """Return the most recent execution record for an import job."""
    database_url = get_database_url()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    psycopg = _require_psycopg()

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    job_id,
                    step,
                    final_status,
                    input_summary,
                    model_version,
                    output_summary,
                    error_message,
                    retry_count,
                    started_at,
                    finished_at,
                    updated_at
                FROM public.import_job_runs
                WHERE job_id = %s
                ORDER BY started_at DESC, updated_at DESC
                LIMIT 1;
                """,
                (job_id,),
            )
            row = cur.fetchone()

    return _map_import_job_run_row(row) if row else None


def _map_import_job_row(row: tuple[Any, ...]) -> dict[str, Any]:
    """Map an import_jobs row to an API-friendly dict."""
    return {
        "id": row[0],
        "status": row[1],
        "source": row[2],
        "filename": row[3],
        "total_transactions": int(row[4]),
        "review_required_count": int(row[5]),
        "persisted_count": int(row[6]),
        "error_message": row[7],
        "created_at": _serialize_optional_datetime(row[8]),
        "started_at": _serialize_optional_datetime(row[9]),
        "finished_at": _serialize_optional_datetime(row[10]),
        "updated_at": _serialize_optional_datetime(row[11]),
    }



def get_latest_import_job() -> dict[str, Any] | None:
    """Return the most recently created import job, if any."""
    database_url = get_database_url()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    psycopg = _require_psycopg()

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    status,
                    source,
                    filename,
                    total_transactions,
                    review_required_count,
                    persisted_count,
                    error_message,
                    created_at,
                    started_at,
                    finished_at,
                    updated_at
                FROM public.import_jobs
                ORDER BY created_at DESC
                LIMIT 1;
                """
            )
            row = cur.fetchone()

    if not row:
        return None

    job = _map_import_job_row(row)
    job["latest_run"] = get_latest_import_job_run(job["id"])
    return job



def get_import_job(job_id: str) -> dict[str, Any] | None:
    """Return a specific import job by ID, if it exists."""
    database_url = get_database_url()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    psycopg = _require_psycopg()

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    status,
                    source,
                    filename,
                    total_transactions,
                    review_required_count,
                    persisted_count,
                    error_message,
                    created_at,
                    started_at,
                    finished_at,
                    updated_at
                FROM public.import_jobs
                WHERE id = %s
                LIMIT 1;
                """,
                (job_id,),
            )
            row = cur.fetchone()

    if not row:
        return None

    job = _map_import_job_row(row)
    job["latest_run"] = get_latest_import_job_run(job_id)
    return job



def get_available_months() -> list[str]:
    """返回数据库中所有存在交易记录的月份（YYYY-MM 格式），升序排列。"""
    database_url = get_database_url()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    psycopg = _require_psycopg()

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT TO_CHAR(transaction_date, 'YYYY-MM') AS month
                FROM public.transactions
                ORDER BY month ASC;
                """
            )
            return [row[0] for row in cur.fetchall()]
