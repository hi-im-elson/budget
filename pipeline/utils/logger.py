import os
import logging

log_dir = os.path.join(os.getcwd(), ".logs")
os.makedirs(log_dir, exist_ok=True)


def create_logger(log_file: str) -> logging.Logger:
    """Named logger that writes to .logs/<log_file>. Name is the file stem (e.g. 'gold')."""
    name = os.path.splitext(log_file)[0]
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler(os.path.join(log_dir, log_file))
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)
    return logger


def get_logger(name: str) -> logging.Logger:
    """Standard propagating logger for library/pipeline modules."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    return logger
