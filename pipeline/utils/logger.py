import os
import logging

log_dir = os.path.join(os.getcwd(), ".logs")
os.makedirs(log_dir, exist_ok=True)


def create_logger(log_file: str) -> logging.Logger:
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(os.path.join(log_dir, log_file))
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a named logger at INFO level. Propagates to root handler."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    return logger
