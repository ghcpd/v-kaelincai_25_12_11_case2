# Structured Logging Schema

All logs must include these fields:
- `timestamp` (ISO 8601)
- `level` (INFO/WARN/ERROR)
- `service` (appointments.scheduler)
- `request_id` (unique id associated with the request)
- `user_id` (masked unless authorized)
- `message` (textual description)
- `component` (e.g., storage, calendar, outbox)

Sensitive fields (like `details`) must be masked before logging.

Example JSON log:
{
  "timestamp": "2025-12-11T12:34:56.789Z",
  "level": "INFO",
  "service": "appointments.scheduler",
  "request_id": "req-abc",
  "user_id": "u1",
  "component": "outbox",
  "message": "enqueued outbox event",
}
