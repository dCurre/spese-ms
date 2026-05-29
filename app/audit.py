import logging

_logger = logging.getLogger('audit')
_logger.setLevel(logging.INFO)
_logger.propagate = False

_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter('%(asctime)s [AUDIT] %(message)s'))
_logger.addHandler(_handler)


def log_audit(action: str, **details):
    _logger.info("action=%s %s", action, " ".join(f"{k}={v}" for k, v in details.items()))
