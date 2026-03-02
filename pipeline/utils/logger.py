import os
import logging

# Configure logging
log_dir = os.path.join(os.getcwd(), ".logs")
os.makedirs(log_dir, exist_ok=True)

def create_logger(log_file: str):
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(os.path.join(log_dir, log_file))
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger