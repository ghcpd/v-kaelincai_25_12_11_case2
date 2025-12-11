from flask import Flask, request, jsonify
import threading
import time
import uuid

app = Flask(__name__)

# Internal store to simulate idempotency and scenario-driven behavior
_seen_idempotency = {}
_bookings = {}
_scenarios = {}

@app.route('/configure', methods=['POST'])
def configure():
    payload = request.get_json() or {}
    _scenarios.clear()
    _scenarios.update(payload.get('scenarios', {}))
    return jsonify({"ok": True})

@app.route('/availability', methods=['POST'])
def availability():
    data = request.get_json() or {}
    scenario = data.get('scenario')
    cfg = _scenarios.get(scenario, {})
    delay = cfg.get('availability_delay', 0)
    if delay:
        time.sleep(delay)
    available = cfg.get('available', True)
    return jsonify({"available": available})

@app.route('/book', methods=['POST'])
def book():
    data = request.get_json() or {}
    idemp = request.headers.get('Idempotency-Key')
    scenario = data.get('scenario')
    cfg = _scenarios.get(scenario, {})

    # Simulate transient failure pattern
    transient_fail = cfg.get('book_transient_fail', 0)
    if transient_fail:
        counter = _seen_idempotency.setdefault((idemp, 'book_transient_counter'), 0)
        if counter < transient_fail:
            _seen_idempotency[(idemp, 'book_transient_counter')] = counter + 1
            return (jsonify({"error": "transient"}), 500)

    # Simulate processing delay
    time.sleep(cfg.get('book_delay', 0))

    # Idempotency: if we've seen this key, return previous booking
    if idemp and idemp in _seen_idempotency:
        return jsonify(_seen_idempotency[idemp])

    booking_id = str(uuid.uuid4())
    resp = {"booking_id": booking_id, "provider_status": "booked"}
    _seen_idempotency[idemp] = resp
    _bookings[booking_id] = {"data": data, "status": "booked"}
    return jsonify(resp)

@app.route('/confirm', methods=['POST'])
def confirm():
    data = request.get_json() or {}
    booking_id = data.get('booking_id')
    # find scenario from booking payload
    bk = _bookings.get(booking_id, {})
    scenario = bk.get('data', {}).get('scenario')
    cfg = _scenarios.get(scenario, {})
    # Simulate confirm transient failure or permanent failure
    if cfg.get('confirm_fail', False):
        return (jsonify({"error": "confirm_failed"}), 500)
    time.sleep(cfg.get('confirm_delay', 0))
    _bookings[booking_id]['status'] = 'confirmed'
    return jsonify({"status": "confirmed", "booking_id": booking_id})

@app.route('/cancel', methods=['POST'])
def cancel():
    data = request.get_json() or {}
    booking_id = data.get('booking_id')
    time.sleep(0.1)
    if booking_id in _bookings:
        _bookings[booking_id]['status'] = 'cancelled'
    return jsonify({"status": "cancelled", "booking_id": booking_id})

@app.route('/admin/state', methods=['GET'])
def state():
    return jsonify({
        "seen_idempotency": list(_seen_idempotency.keys()),
        "bookings": {k: v['status'] for k, v in _bookings.items()},
        "scenarios": _scenarios
    })

@app.route('/shutdown', methods=['POST'])
def shutdown():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        return jsonify({"error": "not running with the Werkzeug Server"}), 500
    func()
    return jsonify({"ok": True})


def start_mock_server(host='127.0.0.1', port=5001):
    # For tests, we run Flask dev server in a background thread
    thread = threading.Thread(target=lambda: app.run(host=host, port=port, debug=False, use_reloader=False), daemon=True)
    thread.start()
    # Wait briefly for server to be ready
    time.sleep(0.5)
    return thread

if __name__ == '__main__':
    start_mock_server(host='0.0.0.0', port=5001)
    print('Mock provider running on http://0.0.0.0:5001')
    while True:
        time.sleep(1)
