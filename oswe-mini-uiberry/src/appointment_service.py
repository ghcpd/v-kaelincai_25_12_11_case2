import requests
import time
import threading
import uuid
import json
from datetime import datetime
from requests.exceptions import RequestException, Timeout
from typing import Optional
from .logger_config import get_logger

logger = get_logger("appointment_service")

# Simple in-memory idempotency + booking store for prototype
_idempotency_store = {}
_booking_store = {}
_store_lock = threading.Lock()

class CircuitOpen(Exception):
    pass

class CircuitBreaker:
    def __init__(self, fail_threshold=3, reset_timeout=10):
        self.fail_threshold = fail_threshold
        self.reset_timeout = reset_timeout
        self.fail_count = 0
        self.opened_at = None
        self._lock = threading.Lock()

    def before_call(self):
        with self._lock:
            if self.opened_at:
                if time.time() - self.opened_at > self.reset_timeout:
                    # half-open
                    self.opened_at = None
                    self.fail_count = 0
                else:
                    raise CircuitOpen("circuit open")

    def on_success(self):
        with self._lock:
            self.fail_count = 0
            self.opened_at = None

    def on_failure(self):
        with self._lock:
            self.fail_count += 1
            if self.fail_count >= self.fail_threshold:
                self.opened_at = time.time()


class AppointmentService:
    def __init__(self, base_url: str, timeout: float = 2.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.circuit = CircuitBreaker(fail_threshold=3, reset_timeout=8)

    def _persist_idempotency(self, key: str, result: dict):
        with _store_lock:
            _idempotency_store[key] = result

    def _get_idempotent(self, key: str) -> Optional[dict]:
        with _store_lock:
            return _idempotency_store.get(key)

    def _record_booking(self, booking_id: str, payload: dict):
        with _store_lock:
            _booking_store[booking_id] = payload

    def _call_with_retry(self, method, url, headers=None, json_body=None,
                         retries=3, backoff_base=0.2, timeout=None):
        attempts = 0
        timeout = timeout or self.timeout
        last_exc = None
        while attempts <= retries:
            attempts += 1
            try:
                self.circuit.before_call()
                resp = self.session.request(method, url, headers=headers, json=json_body, timeout=timeout)
                if resp.status_code >= 500:
                    raise RequestException(f"server error {resp.status_code}")
                self.circuit.on_success()
                return resp
            except (RequestException, Timeout) as ex:
                last_exc = ex
                self.circuit.on_failure()
                jitter = (0.5 * backoff_base) * attempts
                logger.debug(f"retry {attempts} after exception: {ex}", extra={"request_id": headers.get("X-Request-ID") if headers else None})
                time.sleep(backoff_base * attempts + jitter)
        raise last_exc

    def book_appointment(self, payload: dict, idempotency_key: Optional[str] = None) -> dict:
        """
        Orchestrates appointment booking with idempotency, retries, timeout and compensation.
        Returns a dict with booking_id and status.
        """
        request_id = str(uuid.uuid4())
        headers = {
            "X-Request-ID": request_id,
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        logger.info("start booking", extra={"request_id": request_id, "idempotency_key": idempotency_key})

        # Check idempotency first
        if idempotency_key:
            prior = self._get_idempotent(idempotency_key)
            if prior:
                logger.info("idempotent hit - returning prior result", extra={"request_id": request_id, "idempotency_key": idempotency_key, "appointment_id": prior.get("booking_id")})
                return prior

        # 1) Check availability
        avail_url = f"{self.base_url}/availability"
        try:
            resp = self._call_with_retry("POST", avail_url, headers=headers, json_body=payload, retries=2, timeout=1.5)
        except Exception as ex:
            logger.error(f"availability check failed: {ex}", extra={"request_id": request_id})
            raise
        avail = resp.json()
        if not avail.get("available"):
            logger.info("no availability", extra={"request_id": request_id})
            result = {"status": "rejected", "reason": "no_availability"}
            if idempotency_key:
                self._persist_idempotency(idempotency_key, result)
            return result

        # 2) Attempt booking (may need retries)
        book_url = f"{self.base_url}/book"
        try:
            resp = self._call_with_retry("POST", book_url, headers=headers, json_body=payload, retries=3, timeout=2.0)
        except Exception as ex:
            logger.error(f"booking failed after retries: {ex}", extra={"request_id": request_id})
            # Hard failure
            result = {"status": "failed", "reason": "booking_failed"}
            if idempotency_key:
                self._persist_idempotency(idempotency_key, result)
            raise

        book_resp = resp.json()
        booking_id = book_resp.get("booking_id")
        self._record_booking(booking_id, {"payload": payload, "book_resp": book_resp})
        logger.info("booked", extra={"request_id": request_id, "appointment_id": booking_id, "idempotency_key": idempotency_key})

        # 3) Confirm flow (simulate downstream step that may fail and require compensation)
        confirm_url = f"{self.base_url}/confirm"
        try:
            resp = self._call_with_retry("POST", confirm_url, headers=headers, json_body={"booking_id": booking_id}, retries=2, timeout=1.5)
        except Exception as ex:
            logger.error(f"confirm failed, initiating compensation: {ex}", extra={"request_id": request_id, "appointment_id": booking_id})
            # Compensation (Saga pattern)
            cancel_url = f"{self.base_url}/cancel"
            try:
                cresp = self.session.post(cancel_url, headers=headers, json={"booking_id": booking_id}, timeout=1.0)
                logger.info("compensation executed", extra={"request_id": request_id, "appointment_id": booking_id})
            except Exception as cex:
                logger.critical("compensation FAILED", extra={"request_id": request_id, "appointment_id": booking_id})
                # escalate
            result = {"status": "compensated", "booking_id": booking_id}
            if idempotency_key:
                self._persist_idempotency(idempotency_key, result)
            return result

        logger.info("confirmed", extra={"request_id": request_id, "appointment_id": booking_id})
        result = {"status": "confirmed", "booking_id": booking_id}
        if idempotency_key:
            self._persist_idempotency(idempotency_key, result)
        return result


# A helper to surface internal stores for tests/inspection
def _stores_snapshot():
    with _store_lock:
        return {
            "idempotency_store": dict(_idempotency_store),
            "booking_store": dict(_booking_store)
        }
