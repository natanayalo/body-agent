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
    response = requests.get(f"{api_base_url}/healthz", timeout=60)
    assert response.status_code == 200
    assert response.json().get("ok") is True


def test_graph_run_basic_query(api_base_url):
    payload = {"user_id": "test-user-real", "query": "I have a fever of 38.8C"}
    response = requests.post(f"{api_base_url}/api/graph/run", json=payload, timeout=60)
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
    response = requests.post(f"{api_base_url}/api/graph/run", json=payload, timeout=60)
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
        f"{api_base_url}/api/memory/add_med", json=payload, timeout=60
    )
    assert response.status_code == 200
    assert response.json().get("ok") is True
