"""Calendar provider mock used to simulate various behaviors for integration tests."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List


@dataclass
class Behavior:
    mode: str  # 'ok', 'fail_n_then_ok', 'timeout', 'always_fail'
    fail_n: int = 0
    delay_sec: float = 0.0


class CalendarMock:
    def __init__(self, behavior: Behavior):
        self.behavior = behavior
        self._calls = 0

    def book(self, appointment_id: str, start_ts: str, duration_minutes: int):
        self._calls += 1
        if self.behavior.delay_sec > 0:
            time.sleep(self.behavior.delay_sec)

        if self.behavior.mode == "ok":
            return {"status": "ok", "appointment_id": appointment_id}
        if self.behavior.mode == "fail_n_then_ok":
            if self._calls <= self.behavior.fail_n:
                raise RuntimeError("transient error")
            return {"status": "ok", "appointment_id": appointment_id}
        if self.behavior.mode == "timeout":
            raise TimeoutError("provider timeout")
        if self.behavior.mode == "always_fail":
            raise RuntimeError("permanent provider error")
        return {"status": "unknown"}

    def calls(self):
        return self._calls
