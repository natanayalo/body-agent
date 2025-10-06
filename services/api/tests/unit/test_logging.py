import logging
from io import StringIO
import os
import tempfile
from pathlib import Path

import pytest

from app.config.logging import (
    configure_logging,
    _resolve_log_dir,
    set_request_id,
    clear_request_id,
    RequestIdFilter,
)


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
    """
    Tests that configure_logging falls back to a temporary directory if it
    encounters a PermissionError when trying to create the primary log directory.
    """
    # 1. Define a primary log directory path that we will simulate as non-writable.
    primary_log_dir_path = "/non_writable_dir/logs"

    # 2. Mock _resolve_log_dir to return this non-writable path.
    monkeypatch.setattr(
        "app.config.logging._resolve_log_dir", lambda: Path(primary_log_dir_path)
    )

    # 3. Mock Path.mkdir to simulate PermissionError for the primary path.
    #    We need to keep a reference to the original mkdir to call it for the fallback path.
    original_mkdir = Path.mkdir
    mkdir_calls = []

    def mkdir_spy(path_instance, parents=False, exist_ok=False):
        mkdir_calls.append(path_instance)
        if path_instance == Path(primary_log_dir_path):
            raise PermissionError("Simulated permission denied")
        else:
            # For the fallback path, we call the original mkdir to actually create it,
            # so that the RotatingFileHandler can be instantiated without error.
            return original_mkdir(path_instance, parents=parents, exist_ok=exist_ok)

    monkeypatch.setattr(Path, "mkdir", mkdir_spy)

    # 4. Call the function to be tested.
    returned_path = configure_logging()

    # 5. Assertions
    fallback_dir = Path(tempfile.gettempdir()) / "body-agent"

    # Check that the returned log file path is in the fallback directory.
    assert returned_path.parent == fallback_dir
    assert returned_path.name == "api.log"

    # Check that mkdir was called twice: once for the primary dir, once for the fallback.
    assert len(mkdir_calls) == 2
    assert mkdir_calls[0] == Path(primary_log_dir_path)
    assert mkdir_calls[1] == fallback_dir


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


def test_request_id_in_logs():
    # Build a dedicated logger with our filter and formatter

    buf = StringIO()
    handler = logging.StreamHandler(buf)
    fmt = logging.Formatter(
        "%(asctime)s | [%(levelname)s] [%(name)s] rid=%(request_id)s %(message)s"
    )
    handler.setFormatter(fmt)
    handler.addFilter(RequestIdFilter())

    logger = logging.getLogger("test.requestid")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    try:
        set_request_id("abc-123")
        logger.info("hello")
        clear_request_id()
        logger.info("world")
    finally:
        logger.removeHandler(handler)

    output = buf.getvalue()
    assert "rid=abc-123" in output and "hello" in output
    assert "rid=-" in output and "world" in output


def test_request_id_filter_direct():
    f = RequestIdFilter()
    # Default (cleared) should set '-'
    clear_request_id()
    rec = logging.LogRecord("x", logging.INFO, __file__, 0, "msg", (), None)
    assert f.filter(rec) is True
    assert getattr(rec, "request_id", "") == "-"

    # After setting, filter should copy the value
    set_request_id("rid-xyz")
    rec2 = logging.LogRecord("x", logging.INFO, __file__, 0, "msg2", (), None)
    assert f.filter(rec2) is True
    assert getattr(rec2, "request_id", "") == "rid-xyz"
