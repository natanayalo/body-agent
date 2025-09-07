import logging
import os
import pytest
import tempfile
from app.main import app
from app.graph.build import build_graph


def configure_test_logging():
    """Configure logging for test environment"""
    # Use tempfile for tests
    log_path = tempfile.gettempdir()
    log_file = os.path.join(log_path, "test.log")

    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        filename=log_file,
        filemode="w",
    )


@pytest.fixture(autouse=True)
def setup_app():
    """Setup app state before each test"""
    # Build and compile graph
    app.state.graph = build_graph().compile()
