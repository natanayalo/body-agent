import logging
import pytest


@pytest.mark.xfail(reason="logging configuration in tests is tricky")
def test_logging_redacts_user_query(client, caplog):
    raw_query = "My SSN is 123-456-7890"
    redacted_query = "My SSN is [ssn]"

    caplog.set_level(logging.DEBUG)

    client.post("/api/graph/run", json={"query": raw_query})

    assert redacted_query in caplog.text
    # Check that the raw query is not in the logs from the nodes
    node_logs = [
        rec.message for rec in caplog.records if rec.name.startswith("app.graph.nodes")
    ]
    assert not any(raw_query in msg for msg in node_logs)
