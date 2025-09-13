import logging
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from app.config.logging import configure_logging, _resolve_log_dir


@pytest.fixture(autouse=True)
def reset_logging_and_env():
    # Ensure a clean logging state for each test
    logging.shutdown()
    # Re-initialize logging system to default state
    logging.setLoggerClass(logging.Logger)
    logging.root = logging.RootLogger(logging.WARNING)
    logging.Logger.root = logging.root
    logging.Logger.manager = logging.Manager(logging.Logger.root)

    # Clear environment variables that might affect logging
    if "APP_LOG_DIR" in os.environ:
        del os.environ["APP_LOG_DIR"]
    if "APP_DATA_DIR" in os.environ:
        del os.environ["APP_DATA_DIR"]
    if "LOG_LEVEL" in os.environ:
        del os.environ["LOG_LEVEL"]


def test_resolve_log_dir_explicit_env_var(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("APP_LOG_DIR", tmpdir)
        log_dir = _resolve_log_dir()
        assert log_dir == Path(tmpdir)


def test_resolve_log_dir_app_data_dir_env_var(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("APP_DATA_DIR", tmpdir)
        log_dir = _resolve_log_dir()
        assert log_dir == Path(tmpdir) / "logs"


def test_resolve_log_dir_fallback_to_tmp(monkeypatch):
    # Ensure no relevant env vars are set
    if "APP_LOG_DIR" in os.environ:
        del os.environ["APP_LOG_DIR"]
    if "APP_DATA_DIR" in os.environ:
        del os.environ["APP_DATA_DIR"]

    log_dir = _resolve_log_dir()
    assert log_dir == Path(tempfile.gettempdir()) / "body-agent"


def test_configure_logging_creates_directory(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("APP_LOG_DIR", tmpdir)
        returned_path = configure_logging()
        assert returned_path == Path(tmpdir) / "api.log"
        assert Path(tmpdir).is_dir()


def test_configure_logging_permission_error_fallback(monkeypatch):
    # Mock Path.mkdir to raise PermissionError for the first call, then succeed
    mock_mkdir = MagicMock(side_effect=[PermissionError, None])
    with patch("pathlib.Path.mkdir", new=mock_mkdir):
        # Ensure no explicit APP_LOG_DIR is set to trigger fallback
        if "APP_LOG_DIR" in os.environ:
            del os.environ["APP_LOG_DIR"]
        if "APP_DATA_DIR" in os.environ:
            del os.environ["APP_DATA_DIR"]

        returned_path = configure_logging()
        # Should fall back to /tmp
        assert returned_path.parent == Path(tempfile.gettempdir()) / "body-agent"
        assert returned_path.name == "api.log"
        # Ensure mkdir was called twice (once for original, once for fallback)
        assert mock_mkdir.call_count == 2


def test_configure_logging_root_logger_level():
    configure_logging()
    root_logger = logging.getLogger()
    assert root_logger.level == logging.INFO


def test_configure_logging_handlers_present():
    configure_logging()
    root_logger = logging.getLogger()
    # Should have a file handler and a stream handler
    assert len(root_logger.handlers) == 2
    assert any(
        isinstance(h, logging.handlers.RotatingFileHandler)
        for h in root_logger.handlers
    )
    assert any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers)


def test_configure_logging_log_level_from_env_var(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    configure_logging()
    root_logger = logging.getLogger()
    assert root_logger.level == logging.DEBUG


def test_configure_logging_clears_existing_handlers():
    # Add a dummy handler before configuring
    dummy_handler = logging.StreamHandler()
    root_logger = logging.getLogger()
    root_logger.addHandler(dummy_handler)

    # Ensure the dummy handler is initially present
    assert dummy_handler in root_logger.handlers

    configure_logging()

    # After configuration, dummy handler should be removed
    assert dummy_handler not in root_logger.handlers

    # We expect 2 handlers (file and stream) from configure_logging
    # Filter out any handlers that pytest's caplog might have added
    # (caplog adds handlers to the root logger, which are not cleared by logging.shutdown())
    configured_handlers = [
        h
        for h in root_logger.handlers
        if isinstance(h, (logging.handlers.RotatingFileHandler, logging.StreamHandler))
    ]

    assert len(configured_handlers) == 2
    assert any(
        isinstance(h, logging.handlers.RotatingFileHandler) for h in configured_handlers
    )
    assert any(isinstance(h, logging.StreamHandler) for h in configured_handlers)


def test_pii_scrubbing_in_logs(client, caplog):
    # This test seems to be an integration test, not a unit test for logging configuration.
    # It relies on the FastAPI client and actual logging behavior with PII.
    # It should be moved to integration tests if possible.
    pii_query = "My email is test@example.com and my phone is 123-456-7890."

    with caplog.at_level(logging.DEBUG):
        response = client.post(
            "/api/graph/run", json={"user_id": "test-user", "query": pii_query}
        )
        assert response.status_code == 200

        # Check that raw PII is NOT in logs
        for record in caplog.records:
            assert pii_query not in record.message
            assert "test@example.com" not in record.message
            assert "123-456-7890" not in record.message
