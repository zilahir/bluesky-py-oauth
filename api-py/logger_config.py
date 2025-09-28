"""
Common logging configuration for the application.

This module provides a centralized logging setup with consistent formatting
and log levels across all application modules.
"""

import logging
import sys
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """Custom formatter to add colors to log levels"""

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }

    def format(self, record):
        # Add color to the level name
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.COLORS['RESET']}"

        return super().format(record)


def setup_logger(
    name: str,
    level: str = "INFO",
    format_string: Optional[str] = None
) -> logging.Logger:
    """
    Set up a logger with consistent formatting.

    Args:
        name: Logger name (usually __name__ of the module)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom format string (optional)

    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(name)

    # Prevent duplicate handlers if logger already exists
    if logger.handlers:
        return logger

    # Set log level
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Default format string
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Create formatter
    formatter = ColoredFormatter(format_string)
    console_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(console_handler)

    return logger


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """
    Get or create a logger with the standard configuration.

    Args:
        name: Logger name (usually __name__ of the module)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        logging.Logger: Configured logger instance
    """
    return setup_logger(name, level)


# Application-wide logger instances for common modules
campaign_logger = get_logger("campaign")
scheduler_logger = get_logger("scheduler")
worker_logger = get_logger("worker")
api_logger = get_logger("api")
task_logger = get_logger("tasks")


def log_exception(logger: logging.Logger, message: str, exc: Exception):
    """
    Log an exception with consistent formatting.

    Args:
        logger: Logger instance to use
        message: Context message about the exception
        exc: Exception instance
    """
    logger.error(f"{message}: {exc}", exc_info=True)


def log_campaign_event(campaign_id: int, event: str, details: str = ""):
    """
    Log a campaign-related event with consistent formatting.

    Args:
        campaign_id: Campaign ID
        event: Event description
        details: Additional details (optional)
    """
    message = f"Campaign {campaign_id}: {event}"
    if details:
        message += f" - {details}"
    campaign_logger.info(message)


def log_scheduler_event(job_id: str, event: str, details: str = ""):
    """
    Log a scheduler-related event with consistent formatting.

    Args:
        job_id: Job ID
        event: Event description
        details: Additional details (optional)
    """
    message = f"Job {job_id}: {event}"
    if details:
        message += f" - {details}"
    scheduler_logger.info(message)