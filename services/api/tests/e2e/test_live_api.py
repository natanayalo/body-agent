import pytest
import requests
import time
import logging

logging.basicConfig(level=logging.INFO)


@pytest.fixture(scope="session")
def api_base_url():
    # In a real scenario, this would be dynamically determined or configured
    return "http://localhost:8000"


@pytest.fixture(scope="session", autouse=True)
def wait_for_api(api_base_url):
    url = f"{api_base_url}/healthz"
    retries = 20
    for i in range(retries):
        try:
            response = requests.get(url, timeout=1)
            if response.status_code == 200 and response.json().get("ok"):
                logging.info(f"API is ready after {i+1} retries.")
                return
        except requests.exceptions.ConnectionError:
            pass
        logging.warning(f"Waiting for API to be ready... Attempt {i+1}/{retries}")
        time.sleep(2)
    pytest.fail("API did not become ready within the timeout.")


def test_healthz_endpoint(api_base_url):
    response = requests.get(f"{api_base_url}/healthz", timeout=15)
    assert response.status_code == 200
    assert response.json().get("ok") is True


def test_graph_run_basic_query(api_base_url):
    payload = {"user_id": "test-user-real", "query": "I have a fever of 38.8C"}
    response = requests.post(f"{api_base_url}/api/graph/run", json=payload, timeout=15)
    assert response.status_code == 200
    data = response.json()
    assert "state" in data
    assert data["state"]["user_id"] == "test-user-real"
    assert data["state"]["user_query"] == "I have a fever of 38.8C"


def test_graph_run_pii_scrubbing(api_base_url):
    payload = {
        "user_id": "test-user-pii",
        "query": "My phone number is 123-456-7890 and email is test@example.com",
    }
    response = requests.post(f"{api_base_url}/api/graph/run", json=payload, timeout=15)
    assert response.status_code == 200
    data = response.json()
    assert "state" in data
    assert "[phone]" in data["state"]["user_query_redacted"]
    assert "[email]" in data["state"]["user_query_redacted"]
    assert "123-456-7890" not in data["state"]["user_query_redacted"]
    assert "test@example.com" not in data["state"]["user_query_redacted"]


def test_add_med_endpoint(api_base_url):
    payload = {"user_id": "test-user-med", "name": "Ibuprofen 200mg"}
    response = requests.post(
        f"{api_base_url}/api/memory/add_med", json=payload, timeout=15
    )
    assert response.status_code == 200
    assert response.json().get("ok") is True


def test_e2e_medication_interaction_flow(api_base_url):
    user_id = "test-user-med-interaction"
    # 1. Add first medication
    add_med_payload_1 = {"user_id": user_id, "name": "Ibuprofen 200mg"}
    response_1 = requests.post(
        f"{api_base_url}/api/memory/add_med", json=add_med_payload_1, timeout=15
    )
    assert response_1.status_code == 200
    assert response_1.json().get("ok") is True

    # 2. Add second medication
    add_med_payload_2 = {"user_id": user_id, "name": "Warfarin 5mg"}
    response_2 = requests.post(
        f"{api_base_url}/api/memory/add_med", json=add_med_payload_2, timeout=15
    )
    assert response_2.status_code == 200
    assert response_2.json().get("ok") is True

    # 3. Query about a health issue that might trigger an interaction alert
    query_payload = {
        "user_id": user_id,
        "query": "What are the interactions between Ibuprofen and Warfarin?",
    }
    response_3 = requests.post(
        f"{api_base_url}/api/graph/run", json=query_payload, timeout=15
    )
    assert response_3.status_code == 200
    data = response_3.json()

    # 4. Verify that an interaction alert is present
    alerts = data["state"].get("alerts", [])
    assert any("Warfarin — interactions" in a for a in alerts) or any(
        "Ibuprofen — warnings" in a for a in alerts
    ), f"Expected interaction alert, but got: {alerts}"

    # 5. Verify citations are present and normalized
    citations = data["state"].get("citations", [])
    assert len(citations) > 0
    assert all(c.startswith("http") or c.startswith("file") for c in citations)
    # Check for deduplication and normalization (e.g., no utm_ params, consistent slashes)
    # This is a basic check, more robust checks would involve parsing URLs
    assert len(set(citations)) == len(citations), "Citations should be deduplicated"
