#!/usr/bin/env python3
"""
Logging configuration module for the FastMCP Rust documentation server.

Provides structured JSON logging with rotation and proper formatting.
"""

import datetime
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


class JsonFormatter(logging.Formatter):
    """Custom formatter to output logs in JSON format."""
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        # Add extra data if it exists
        if hasattr(record, 'extra_data'):
            log_record.update(record.extra_data)
        # Add exception info if it exists
        if record.exc_info:
            log_record['exc_info'] = self.formatException(record.exc_info)
        return json.dumps(log_record)


def setup_logging(logs_dir: Path = None):
    """
    Configures the structured JSON logger.
    
    Args:
        logs_dir: Directory to store log files. If None, uses "./logs"
        
    Returns:
        Configured logger instance
    """
    if logs_dir is None:
        logs_dir = Path("./logs")
    
    logs_dir.mkdir(exist_ok=True)
    
    logger = logging.getLogger("RustDocsServer")
    logger.setLevel(logging.INFO)
    
    # Prevent logging from propagating to the root logger
    logger.propagate = False
    
    # If handlers are already present, do nothing
    if logger.handlers:
        return logger
    
    log_file = logs_dir / f"{datetime.date.today()}.log"
    
    # Use RotatingFileHandler to prevent log files from growing too large
    handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    
    formatter = JsonFormatter()
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    return logger