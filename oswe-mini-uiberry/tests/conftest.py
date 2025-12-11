import pytest
import requests
import time
import json
import os
from threading import Thread

# ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))

from mocks import mock_provider

MOCK_URL = "http://127.0.0.1:5001"

@pytest.fixture(scope="session", autouse=True)
def mock_server():
    # start mock provider
    thread = mock_provider.start_mock_server(host='127.0.0.1', port=5001)
    # configure scenarios from test data
    data_path = os.path.join(PROJECT_ROOT, 'data', 'test_data.json')
    with open(data_path, 'r') as fh:
        cases = json.load(fh)
    scenarios = {
        "healthy": {"available": True},
        "transient": {"available": True, "book_transient_fail": 1},
        "slow_avail": {"available": True, "availability_delay": 3},
        "confirm_fail": {"available": True, "confirm_fail": True}
    }
    requests.post(f"{MOCK_URL}/configure", json={"scenarios": scenarios})
    # give server a moment
    time.sleep(0.5)
    yield
    # teardown
    try:
        requests.post(f"{MOCK_URL}/shutdown")
    except Exception:
        pass

@pytest.fixture(scope="session")
def results_collector():
    results_dir = os.path.join(PROJECT_ROOT, 'results')
    os.makedirs(results_dir, exist_ok=True)
    results = {"cases": [], "metrics": {"total": 0, "passed": 0, "retries": 0, "idempotent_hits": 0}}
    yield results
    # write aggregated results at session end
    out_path = os.path.join(results_dir, 'results_post.json')
    with open(out_path, 'w') as fh:
        json.dump(results, fh, indent=2)
