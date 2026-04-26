import logging
import logging.config
import os
from logging.handlers import RotatingFileHandler


def setup_logging(log_dir: str = None):
    if log_dir is None:
        base = os.path.abspath(os.path.dirname(__file__))
        log_dir = os.path.join(base, "logs")
    os.makedirs(log_dir, exist_ok=True)
    logfile = os.path.join(log_dir, "manarey.log")

    handler = RotatingFileHandler(
        logfile, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)

    root = logging.getLogger()
    if not root.handlers:
        root.setLevel(logging.INFO)
        root.addHandler(handler)

    # also expose a module logger
    return logging.getLogger("manarey")
