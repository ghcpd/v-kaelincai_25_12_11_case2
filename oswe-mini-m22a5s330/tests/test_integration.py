import time
import json
import os
import pytest

from appointment_service.core import AppointmentService
from mocks.calendar_mock import CalendarMock, Behavior


@pytest.fixture
def results_dir(tmp_path):
    # Use the project's results/ folder so test artifacts are aggregated
    import os
    d = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'results'))
    os.makedirs(d, exist_ok=True)
    return d


def test_healthy_path(results_dir):
    svc = AppointmentService(lambda: CalendarMock(Behavior(mode="ok")))
    app = svc.create_appointment("key-healthy", "user-1", "2025-12-12T10:00:00Z", 30)
    assert app.state == "confirmed"


def test_idempotency(results_dir):
    mock = CalendarMock(Behavior(mode="ok"))
    svc = AppointmentService(lambda: mock)
    a1 = svc.create_appointment("key-idemp", "user-2", "2025-12-12T11:00:00Z", 45)
    a2 = svc.create_appointment("key-idemp", "user-2", "2025-12-12T11:00:00Z", 45)
    assert a1.appointment_id == a2.appointment_id
    assert mock.calls() == 1


def test_retry_backoff(results_dir):
    # Calendar fails twice then ok
    mock_factory = lambda: CalendarMock(Behavior(mode="fail_n_then_ok", fail_n=2))
    svc = AppointmentService(mock_factory)
    app = svc.create_appointment("key-transient", "user-3", "2025-12-12T12:00:00Z", 30)
    assert app.state == "confirmed"


def test_timeout_and_circuit_breaker(results_dir):
    # Calendar always timeouts
    svc = AppointmentService(lambda: CalendarMock(Behavior(mode="timeout")))
    app = svc.create_appointment("key-timeout", "user-4", "2025-12-12T13:00:00Z", 60)
    # Because of retries the service marks it failed
    assert app.state == "failed"
    # Now short-circuit further attempts
    app2 = svc.create_appointment("key-timeout-2", "user-4", "2025-12-12T14:00:00Z", 60)
    assert app2.state == "failed"


def test_compensation_and_reconciliation(results_dir):
    mock = CalendarMock(Behavior(mode="ok"))
    svc = AppointmentService(lambda: mock)
    app = svc.create_appointment("key-conflict", "user-5", "2025-12-12T14:00:00Z", 20)
    assert app.state == "confirmed"

    # Provider later sends a conflict webhook
    svc.provider_conflict(app.appointment_id)
    assert svc.get_appointment(app.appointment_id).state == "cancelled"

    # Reconcile should show no failed items for this id
    inconsistencies = svc.reconcile()
    assert app.appointment_id not in inconsistencies

    # Save a results summary
    summary = {
        "appointment_id": app.appointment_id,
        "final_state": svc.get_appointment(app.appointment_id).state,
    }
    with open(os.path.join(results_dir, "results_post.json"), "w") as f:
        json.dump(summary, f)
