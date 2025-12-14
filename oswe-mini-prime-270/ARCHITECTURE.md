# Greenfield Replacement — Architecture and Design

## High-level goals
- Build a microservice-based appointment scheduler that is:
  - Idempotent on request retries
  - Robust to external service failures via retries and backoff
  - Uses an outbox pattern to ensure eventual consistency
  - Supports replay/compensation flows
  - Provides structured logging and observability

## Components
- Scheduler API (FastAPI): public endpoints to create/list appointments, process outbox.
- In-memory Store (DB): holds appointments, idempotency table, and outbox events.
- Mock Calendar Service: simulates external calendar provider with failure/delay patterns.

## Data Flow
1. Client sends a `POST /appointments` with a `request_id` header.
2. Scheduler validates idempotency; creates an appointment in store and inserts outbox event.
3. Scheduler attempts to call Calendar (external) via `call_external_calendar` with retries and backoff. On success, it marks outbox entries as processed.
4. Failures leave outbox for background replay (or manual `/outbox/process`).

## Failure modes & Strategies
- Failure to reach calendar: use retries with exponential backoff, and leave outbox for replay.
- Replaying outbox attempts to call calendar and marks processed on success.
- Idempotency: maintain mapping `request_id` -> `appointment_id` to return same resource when retried.

## Interfaces
- `POST /appointments` : AppointmentRequest, returns created appointment.
- `GET /appointments/{id}` : retrieve appointment status.
- `GET /outbox` : list unprocessed outbox events.
- `POST /outbox/process` : attempt to process outbox events.

