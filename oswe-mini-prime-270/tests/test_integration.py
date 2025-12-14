import pytest
import asyncio
from fastapi.testclient import TestClient
from src.scheduler.app import app, store, call_external_calendar
from src.scheduler.model import AppointmentRequest
from datetime import datetime, timedelta
import uuid

client = TestClient(app)


def make_req(request_id=None, user_id="user1"):
    start = datetime.utcnow().isoformat()
    end = (datetime.utcnow() + timedelta(hours=1)).isoformat()
    return {
        "request_id": request_id or str(uuid.uuid4()),
        "user_id": user_id,
        "start_time": start,
        "end_time": end,
        "location": "Room 1",
    }


@pytest.fixture(autouse=True)
def reset_store():
    # reset store between tests
    store.__init__()


def test_idempotency(monkeypatch):
    reqid = "req-123"
    payload = make_req(reqid)

    # Monkeypatch calendar to succeed always
    async def mock_calendar(p, timeout=1.0):
        return {"status": "booked", "appointment_id": p.get("appointment_id")}

    monkeypatch.setattr("src.scheduler.app.call_external_calendar", mock_calendar)

    r1 = client.post("/appointments", json=payload)
    r2 = client.post("/appointments", json=payload)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["appointment_id"] == r2.json()["appointment_id"]
    assert len(store.list_outbox()) == 0  # outbox processed


def test_retry_and_backoff(monkeypatch):
    payload = make_req()
    calls = {"n": 0}

    async def flaky_calendar(p, timeout=1.0):
        calls["n"] += 1
        if calls["n"] < 3:
            raise Exception("Temporary failure")
        return {"status": "booked", "appointment_id": p.get("appointment_id")}

    monkeypatch.setattr("src.scheduler.app.call_external_calendar", flaky_calendar)

    r = client.post("/appointments", json=payload)
    assert r.status_code == 201
    assert calls["n"] == 3
    assert len(store.list_outbox()) == 0  # outbox processed after success


def test_timeout_and_compensation(monkeypatch):
    payload = make_req()

    async def timeout_calendar(p, timeout=1.0):
        raise Exception("Timeout")

    monkeypatch.setattr("src.scheduler.app.call_external_calendar", timeout_calendar)

    r = client.post("/appointments", json=payload)
    assert r.status_code == 201
    # Because calendar failed, outbox is left for replay
    assert len(store.list_outbox()) == 1


def test_outbox_replay(monkeypatch):
    # set up a store with an outbox
    payload = make_req()

    async def timeout_calendar(p, timeout=1.0):
        raise Exception("Timeout")

    monkeypatch.setattr("src.scheduler.app.call_external_calendar", timeout_calendar)
    r = client.post("/appointments", json=payload)
    assert r.status_code == 201
    assert len(store.list_outbox()) == 1

    # Now patch calendar to succeed and process outbox
    async def good_calendar(p, timeout=1.0):
        return {"status": "booked", "appointment_id": p.get("appointment_id")}

    monkeypatch.setattr("src.scheduler.app.call_external_calendar", good_calendar)
    r2 = client.post("/outbox/process")
    assert r2.status_code == 200
    assert len(store.list_outbox()) == 0


def test_happy_path(monkeypatch):
    payload = make_req()

    async def good_calendar(p, timeout=1.0):
        return {"status": "booked", "appointment_id": p.get("appointment_id")}

    monkeypatch.setattr("src.scheduler.app.call_external_calendar", good_calendar)
    r = client.post("/appointments", json=payload)
    assert r.status_code == 201
    assert len(store.list_outbox()) == 0

