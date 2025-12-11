from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException, status
from .model import AppointmentRequest
from .store import InMemoryStore
from typing import Optional
import uuid
import httpx
import asyncio
from pydantic import ValidationError


app = FastAPI(title="Appointment Scheduler v2")

store = InMemoryStore()

# Circuit breaker / timeout simulation
import os

async def call_external_calendar(payload: dict, timeout: float = 1.0) -> dict:
    try:
        calendar_url = os.getenv("CALENDAR_URL", "http://127.0.0.1:8001/calendar/book")
        async with httpx.AsyncClient(timeout=timeout) as client:
            from fastapi.encoders import jsonable_encoder
            json_payload = jsonable_encoder(payload)
            r = await client.post(calendar_url, json=json_payload)
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Calendar call failed: {e}")


@app.post("/appointments", status_code=201)
async def create_appointment(request: AppointmentRequest, idempotency_key: Optional[str] = Header(None)):
    request_id = idempotency_key or request.request_id
    if not request_id:
        raise HTTPException(status_code=400, detail="idempotency key required")

    try:
        appointment = store.create_appointment(request_id, request.model_dump(exclude={"request_id"}))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Attempt to notify calendar with retries and exponential backoff
    max_retries = 3
    base_delay = 0.1
    for attempt in range(1, max_retries + 1):
        try:
            cal_resp = await call_external_calendar(appointment.model_dump())
            # mark outbox processed
            outbox = store.list_outbox()
            for ev in outbox:
                store.mark_outbox_processed(ev.event_id)
            return appointment
        except Exception as e:
            if attempt == max_retries:
                # Compensation: mark as failed for now; leave outbox for retry
                return appointment
            await asyncio.sleep(base_delay * (2 ** (attempt - 1)))


@app.get("/appointments/{appointment_id}")
def get_appointment(appointment_id: str):
    appointment = store.get_appointment(appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Not found")
    return appointment


@app.get("/outbox")
def list_outbox():
    return store.list_outbox()


@app.post("/outbox/process")
def process_outbox():
    # For simplicity, mark all outbox as processed to simulate replay
    for ev in store.list_outbox():
        store.mark_outbox_processed(ev.event_id)
    return {"processed": True}
