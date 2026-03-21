"""
Responsibility: Configure and provide logger instances.
Sets up logging with configurable level from config.yml.
Used throughout the application for consistent logging.
"""

import logging
import sys
from app.config import config

def setup_logger(name: str) -> logging.Logger:
    """
    Create and configure a logger instance.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Set level from config
    log_level = getattr(logging, config.log_level.upper())
    logger.setLevel(log_level)
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    
    # Add handler to logger (avoid duplicates)
    if not logger.handlers:
        logger.addHandler(handler)
    
    return logger
