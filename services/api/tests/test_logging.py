import logging
from app.config.logging import configure_logging


def test_configure_logging():
    """Test that logging is configured correctly."""
    # Configure logging
    configure_logging()

    # Check that the root logger is configured
    root_logger = logging.getLogger()
    assert root_logger.level == logging.WARNING

    # Check that the app logger is configured
    app_logger = logging.getLogger("app")
    assert app_logger.level == logging.INFO
    assert len(app_logger.handlers) == 2
