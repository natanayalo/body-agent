import logging
import os
from unittest.mock import patch

from app.config.logging import configure_logging
from app.config import settings


def test_logging_configures_root_logger():
    # Ensure that the root logger is configured as expected
    # Reset logging to ensure a clean state for this test
    logging.shutdown()
    logging.setLoggerClass(logging.Logger)
    logging.root = logging.RootLogger(logging.WARNING)
    logging.Logger.root = logging.root
    logging.Logger.manager = logging.Manager(logging.Logger.root)

    configure_logging()
    root_logger = logging.getLogger()
    assert root_logger.level == logging.WARNING
    assert len(root_logger.handlers) == 1
    assert isinstance(root_logger.handlers[0], logging.StreamHandler)


def test_logging_configures_app_logger():
    # Ensure that the 'app' logger is configured as expected
    logging.shutdown()
    logging.setLoggerClass(logging.Logger)
    logging.root = logging.RootLogger(logging.WARNING)
    logging.Logger.root = logging.root
    logging.Logger.manager = logging.Manager(logging.Logger.root)

    configure_logging()
    app_logger = logging.getLogger("app")
    assert app_logger.level == logging.INFO  # Default level if LOG_LEVEL not set
    assert app_logger.handlers is not None and len(app_logger.handlers) == 2
    assert isinstance(app_logger.handlers[0], logging.StreamHandler)
    assert app_logger.propagate is False


def test_logging_configures_risk_ml_logger():
    # Ensure that the 'app.graph.nodes.risk_ml' logger is configured as expected
    logging.shutdown()
    logging.setLoggerClass(logging.Logger)
    logging.root = logging.RootLogger(logging.WARNING)
    logging.Logger.root = logging.root
    logging.Logger.manager = logging.Manager(logging.Logger.root)

    configure_logging()
    risk_ml_logger = logging.getLogger("app.graph.nodes.risk_ml")
    assert risk_ml_logger.level == logging.INFO  # Default level if LOG_LEVEL not set
    assert risk_ml_logger.handlers is not None and len(risk_ml_logger.handlers) == 2
    assert isinstance(risk_ml_logger.handlers[0], logging.StreamHandler)
    assert risk_ml_logger.propagate is False


def test_logging_configures_health_logger():
    # Ensure that the 'app.graph.nodes.health' logger is configured as expected
    logging.shutdown()
    logging.setLoggerClass(logging.Logger)
    logging.root = logging.RootLogger(logging.WARNING)
    logging.Logger.root = logging.root
    logging.Logger.manager = logging.Manager(logging.Logger.root)

    configure_logging()
    health_logger = logging.getLogger("app.graph.nodes.health")
    assert health_logger.level == logging.INFO
    assert health_logger.handlers is not None and len(health_logger.handlers) == 2
    assert isinstance(health_logger.handlers[0], logging.StreamHandler)
    assert health_logger.propagate is False


@patch("logging.config.dictConfig")
@patch("os.makedirs")
@patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"})
def test_configure_logging_log_level_env_var(mock_makedirs, mock_dictConfig):
    configure_logging()
    mock_dictConfig.assert_called_once()
    config = mock_dictConfig.call_args[0][0]
    assert config["loggers"]["app"]["level"] == "DEBUG"
    assert config["loggers"]["app.graph.nodes.risk_ml"]["level"] == "DEBUG"


@patch("logging.config.dictConfig")
@patch("os.makedirs")
def test_configure_logging_file_handler_config(mock_makedirs, mock_dictConfig):
    configure_logging()
    mock_dictConfig.assert_called_once()
    config = mock_dictConfig.call_args[0][0]
    file_handler = config["handlers"]["file"]
    assert file_handler["class"] == "logging.handlers.RotatingFileHandler"
    assert file_handler["filename"] == settings.log_file
    assert file_handler["maxBytes"] == 10485760
    assert file_handler["backupCount"] == 5


@patch("logging.config.dictConfig")
@patch("os.makedirs")
def test_configure_logging_creates_log_directory(mock_makedirs, mock_dictConfig):
    configure_logging()
    mock_makedirs.assert_called_once_with(
        os.path.dirname(settings.log_file), exist_ok=True
    )
