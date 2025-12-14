# Appointment Scheduler v2 — Greenfield Replacement

Overview:
- Minimal greenfield microservice replacement for a legacy routing/appointment scheduling module.
- Demonstrates key features: idempotency, outbox (transactional outbox), retries/backoff, timeout handling, and replay.

How to run:
1) Create a Python venv and install requirements:
```bash
python -m venv .venv
. .venv/bin/activate  # On Windows: ./.venv/Scripts/activate
pip install -r requirements.txt
```

2) Run tests:
```bash
# Linux/macOS
./run_tests.sh
# Windows PowerShell
bash ./run_tests.sh
```

3) Run services for manual exploration:
```bash
# Run mock calendar on port 8001
uvicorn mocks.calendar_mock:app --port 8001 &
# Run scheduler on port 8000
uvicorn src.scheduler.app:app --port 8000
```

Structure:
- `src/scheduler` - service code and in-memory store
- `mocks` - mock calendar to simulate delays/failures
- `tests` - pytest integration tests
- `data` - example test data
- `logs`, `results` - artifacts after running tests

Notes:
- The service uses an in-memory store for demonstration; for production, replace with persistent DB.
- Idempotency and outbox patterns are demonstrated.
