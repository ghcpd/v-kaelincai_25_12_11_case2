from __future__ import annotations

from typing import Dict, Optional
from .model import Appointment, OutboxEvent
import uuid


class InMemoryStore:
    """Simple in-memory store to simulate DB + outbox."""

    def __init__(self):
        self._appointments: Dict[str, Appointment] = {}
        self._outbox: Dict[str, OutboxEvent] = {}
        self._idempotency: Dict[str, str] = {}  # request_id -> appointment_id

    def create_appointment(self, request_id: str, appointment_data: dict) -> Appointment:
        # Idempotency handling: if a request with same request_id exists, return it
        if request_id in self._idempotency:
            appointment_id = self._idempotency[request_id]
            return self._appointments[appointment_id]

        appointment_id = str(uuid.uuid4())
        appointment = Appointment(appointment_id=appointment_id, request_id=request_id, status="created", **appointment_data)
        self._appointments[appointment_id] = appointment
        self._idempotency[request_id] = appointment_id

        # add to outbox
        event_id = str(uuid.uuid4())
        outbox = OutboxEvent(event_id=event_id, payload=appointment.model_dump())
        self._outbox[event_id] = outbox
        return appointment

    def get_appointment(self, appointment_id: str) -> Optional[Appointment]:
        return self._appointments.get(appointment_id)

    def list_outbox(self):
        return [o for o in self._outbox.values() if not o.processed]

    def mark_outbox_processed(self, event_id: str):
        if event_id in self._outbox:
            self._outbox[event_id].processed = True
