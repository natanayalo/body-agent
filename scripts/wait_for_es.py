import requests
import time
import os

ES_HOST = os.getenv("ES_HOST", "http://elasticsearch:9200")


def wait_for_elasticsearch():
    url = f"{ES_HOST}/_cluster/health"
    print(f"Waiting for Elasticsearch at {url}...")
    while True:
        try:
            response = requests.get(url, timeout=1)
            if response.status_code == 200 and response.json().get("status") in [
                "green",
                "yellow",
            ]:
                print("Elasticsearch is healthy!")
                break
        except requests.exceptions.ConnectionError:
            pass
        print("Waiting for Elasticsearch...")
        time.sleep(5)


if __name__ == "__main__":
    wait_for_elasticsearch()
