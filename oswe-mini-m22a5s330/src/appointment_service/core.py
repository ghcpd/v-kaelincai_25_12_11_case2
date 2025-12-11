"""
Simple in-memory AppointmentService prototype demonstrating idempotency, retry with backoff,
circuit-breaker, transactional outbox (simulated), and saga compensation.
"""
from __future__ import annotations

import time
import uuid
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, Callable, List


@dataclass
class Appointment:
    appointment_id: str
    user_id: str
    start_ts: str
    duration_minutes: int
    state: str = "created"
    metadata: Dict[str, Any] = field(default_factory=dict)
    version: int = 1


class IdempotencyStore:
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        return self._store.get(key)

    def set(self, key: str, value: Dict[str, Any]):
        self._store[key] = value


class Outbox:
    def __init__(self):
        self._items: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def add(self, item: Dict[str, Any]):
        with self._lock:
            self._items.append(item)

    def pop_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            items = list(self._items)
            self._items.clear()
            return items


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3):
        self._failures = 0
        self._open = False
        self._threshold = failure_threshold

    def record_success(self):
        self._failures = max(0, self._failures - 1)
        if self._failures < self._threshold:
            self._open = False

    def record_failure(self):
        self._failures += 1
        if self._failures >= self._threshold:
            self._open = True

    def is_open(self) -> bool:
        return self._open


class AppointmentService:
    def __init__(self, calendar_client_factory: Callable[[], Any]):
        self._appointments: Dict[str, Appointment] = {}
        self._idempotency = IdempotencyStore()
        self._outbox = Outbox()
        self._cb = CircuitBreaker()
        self._calendar_client_factory = calendar_client_factory

    def create_appointment(self, idempotency_key: str, user_id: str, start_ts: str, duration_minutes: int, metadata: Optional[Dict[str, Any]] = None) -> Appointment:
        # Idempotency check
        existing = self._idempotency.get(idempotency_key)
        if existing is not None:
            print(f"[INFO] idempotency hit for {idempotency_key}")
            return existing["appointment"]

        if duration_minutes < 1 or duration_minutes > 1440:
            raise ValueError("duration_minutes out of range")

        # validation: start_ts not validated thoroughly here (assume ISO string)

        app = Appointment(appointment_id=str(uuid.uuid4()), user_id=user_id, start_ts=start_ts, duration_minutes=duration_minutes, metadata=metadata or {})
        self._appointments[app.appointment_id] = app

        # Save idempotency entry before side-effects
        self._idempotency.set(idempotency_key, {"appointment": app})

        # Append outbox event to request provider booking
        self._outbox.add({"type": "book_slot", "appointment_id": app.appointment_id})

        # Dispatch outbox synchronously for prototype
        self._dispatch_outbox()

        return app

    def _dispatch_outbox(self):
        items = self._outbox.pop_all()
        client = self._calendar_client_factory()
        for item in items:
            if item["type"] == "book_slot":
                app_id = item["appointment_id"]
                app = self._appointments.get(app_id)
                if not app:
                    continue
                # Check circuit-breaker
                if self._cb.is_open():
                    app.state = "failed"
                    continue
                # Retry with backoff
                for attempt in range(5):
                    try:
                        resp = client.book(app_id, app.start_ts, app.duration_minutes)
                        if resp.get("status") == "ok":
                            app.state = "confirmed"
                            self._cb.record_success()
                            break
                        else:
                            raise RuntimeError("provider error")
                    except Exception as e:
                        self._cb.record_failure()
                        if attempt == 4:
                            app.state = "failed"
                        else:
                            backoff = 0.05 * (2 ** attempt)
                            time.sleep(backoff)

    def get_appointment(self, appointment_id: str) -> Optional[Appointment]:
        return self._appointments.get(appointment_id)

    # Simulate compensation endpoint triggered by provider webhook
    def provider_conflict(self, appointment_id: str):
        app = self._appointments.get(appointment_id)
        if not app:
            return
        # Compensation: mark cancelled and emit audit event
        app.state = "cancelled"
        self._outbox.add({"type": "audit", "appointment_id": appointment_id})

    def reconcile(self):
        # For prototype: return list of inconsistencies
        inconsistencies = []
        for aid, app in self._appointments.items():
            if app.state == "confirmed":
                # check provider record (omitted)
                pass
            if app.state == "failed":
                inconsistencies.append(aid)
        return inconsistencies
