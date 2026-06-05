import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logger(level: int = logging.INFO):
    log_dir = r"C:\AI\urix_AI\logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "urix.log")
    
    handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    # Clear existing handlers to prevent duplicate logs if setup_logger is called multiple times
    if not root_logger.handlers:
        root_logger.addHandler(handler)
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
