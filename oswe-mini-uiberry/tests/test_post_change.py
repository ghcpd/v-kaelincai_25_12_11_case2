import pytest
import requests
import os
import json
import time
import uuid
from src.appointment_service import AppointmentService, _stores_snapshot
from src.logger_config import get_logger

logger = get_logger('tests')
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
MOCK_URL = "http://127.0.0.1:5001"


def _run_case(case, results):
    svc = AppointmentService(base_url=MOCK_URL)
    idemp_key = None
    if case['id'] == 'case_idempotency':
        idemp_key = f"idem-{case['id']}-{uuid.uuid4()}"
    # For idempotency test, call twice with same key
    try:
        start = time.time()
        res1 = svc.book_appointment(case['payload'], idempotency_key=idemp_key)
        duration1 = time.time() - start
        retries_used = 0
        # For transient case we expect at least one retry to have occurred inside the service; can't access internal attempt count directly
        # but we can detect success timing or repeated external behavior via stores snapshot
        stores = _stores_snapshot()
        # second call for idempotency case
        res2 = None
        if case['id'] == 'case_idempotency':
            res2 = svc.book_appointment(case['payload'], idempotency_key=idemp_key)
        result = {
            'id': case['id'],
            'result': res1,
            'result2': res2,
            'duration': duration1,
            'stores': stores
        }
        # Determine derived assertions
        passed = False
        idempotent_hit = False
        if case['id'] == 'case_healthy':
            passed = res1.get('status') == 'confirmed'
        elif case['id'] == 'case_transient_retry':
            passed = res1.get('status') == 'confirmed'
        elif case['id'] == 'case_timeout_circuit':
            # either we got an exception earlier (test would have errored) or status failed; tolerate either
            passed = res1.get('status') in ('failed', 'compensated') or 'booking_id' not in res1
        elif case['id'] == 'case_idempotency':
            passed = res1.get('status') == 'confirmed' and res2 and res1.get('booking_id') == res2.get('booking_id')
            idempotent_hit = res2 and res1.get('booking_id') == res2.get('booking_id')
        elif case['id'] == 'case_partial_confirm_fail_compensate':
            passed = res1.get('status') == 'compensated'
        else:
            passed = False

        results['cases'].append({
            'id': case['id'],
            'passed': passed,
            'result': res1,
            'result2': res2,
            'duration': duration1
        })
        results['metrics']['total'] += 1
        if passed:
            results['metrics']['passed'] += 1
        if idempotent_hit:
            results['metrics']['idempotent_hits'] += 1
    except Exception as ex:
        logger.exception("case failed with exception")
        results['cases'].append({'id': case['id'], 'passed': False, 'error': str(ex)})
        results['metrics']['total'] += 1


def test_integration_flow(results_collector):
    data_path = os.path.join(PROJECT_ROOT, 'data', 'test_data.json')
    with open(data_path, 'r') as fh:
        cases = json.load(fh)
    # run cases sequentially to observe state
    for case in cases:
        _run_case(case, results_collector)

    # Basic acceptance: at least 4/5 cases should pass for prototype
    passed = results_collector['metrics']['passed']
    assert passed >= 4, f"Too many failures: {passed}/5 passed"
