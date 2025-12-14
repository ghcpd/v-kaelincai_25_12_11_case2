from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class AppointmentRequest(BaseModel):
    request_id: str = Field(..., description="Unique request id for idempotency")
    user_id: str
    start_time: datetime
    end_time: datetime
    location: str
    details: Optional[str] = None


class Appointment(BaseModel):
    appointment_id: str
    request_id: str
    user_id: str
    start_time: datetime
    end_time: datetime
    location: str
    status: str


class OutboxEvent(BaseModel):
    event_id: str
    payload: dict
    processed: bool = False
