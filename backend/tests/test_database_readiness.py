"""Read-only FastAPI startup and DDL-free repository contracts."""

import inspect
import traceback
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

import api_server
import database
import schema


SYNTHETIC_DRIVER_TRACEBACK_MARKER = "SYNTHETIC_DRIVER_TRACEBACK_MARKER"


def test_lifespan_keeps_parse_only_startup_disconnected_without_database_url(monkeypatch):
    """No DATABASE_URL keeps the existing parse-only mode and opens no DB connection."""
    readiness = Mock()
    monkeypatch.setattr(api_server.database, "get_database_url", lambda: None)
    monkeypatch.setattr(api_server.schema, "assert_database_ready", readiness)

    with TestClient(api_server.app):
        pass

    readiness.assert_not_called()


def test_lifespan_validates_configured_database_before_serving(monkeypatch):
    """Configured startup validates only; it must delegate no schema initialization."""
    readiness = Mock()
    database_url = "postgresql://private-test-socket/example"
    monkeypatch.setattr(api_server.database, "get_database_url", lambda: database_url)
    monkeypatch.setattr(api_server.schema, "assert_database_ready", readiness)

    with TestClient(api_server.app):
        pass

    readiness.assert_called_once_with(database_url)


def test_lifespan_hides_database_url_when_schema_is_not_ready(monkeypatch):
    """Fail-closed startup gives an operator action without leaking the DSN."""
    database_url = "postgresql://user:secret@private.test/financial"
    monkeypatch.setattr(api_server.database, "get_database_url", lambda: database_url)
    monkeypatch.setattr(
        api_server.schema,
        "assert_database_ready",
        Mock(side_effect=schema.SchemaReadinessError("database schema is not ready; run `python backend/scripts/init_database.py`")),
    )

    with pytest.raises(schema.SchemaReadinessError) as error:
        with TestClient(api_server.app):
            pass

    assert "init_database.py" in str(error.value)
    assert database_url not in str(error.value)


def test_readiness_error_traceback_hides_synthetic_driver_marker(monkeypatch):
    """Startup's public error has no chained driver text for log formatting."""
    def fail_driver_lookup():
        raise RuntimeError(SYNTHETIC_DRIVER_TRACEBACK_MARKER)

    monkeypatch.setattr(schema, "_require_psycopg", fail_driver_lookup)

    with pytest.raises(schema.SchemaReadinessError) as error:
        schema.assert_database_ready("postgresql://safe-test-host/financial")

    assert SYNTHETIC_DRIVER_TRACEBACK_MARKER not in "".join(traceback.format_exception(error.value))


def test_initialization_error_traceback_hides_synthetic_driver_marker(monkeypatch):
    """Bootstrap's public error has no chained driver text for log formatting."""
    def fail_driver_lookup():
        raise RuntimeError(SYNTHETIC_DRIVER_TRACEBACK_MARKER)

    monkeypatch.setattr(schema, "_require_psycopg", fail_driver_lookup)

    with pytest.raises(schema.SchemaInitializationError) as error:
        schema.initialize_database("postgresql://safe-test-host/financial")

    assert SYNTHETIC_DRIVER_TRACEBACK_MARKER not in "".join(traceback.format_exception(error.value))


def test_business_repository_contains_no_schema_ddl():
    """Business reads and writes cannot recreate or alter the app schema."""
    source = inspect.getsource(database).upper()

    assert "CREATE TABLE" not in source
    assert "ALTER TABLE" not in source
    assert "DROP TABLE" not in source
