import logging
import json

class JsonLineFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # include extra fields if provided
        if hasattr(record, "request_id"):
            payload["request_id"] = record.request_id
        if hasattr(record, "appointment_id"):
            payload["appointment_id"] = record.appointment_id
        if hasattr(record, "idempotency_key"):
            payload["idempotency_key"] = record.idempotency_key
        try:
            return json.dumps(payload)
        except Exception:
            return json.dumps({"msg": record.getMessage()})


def get_logger(name="oswe"):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler("logs/log_post.txt")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(JsonLineFormatter())
    logger.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    sh.setFormatter(JsonLineFormatter())
    logger.addHandler(sh)
    return logger
