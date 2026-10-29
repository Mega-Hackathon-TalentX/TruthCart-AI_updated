import logging
import sys
import time
from typing import Optional, Dict, Any

def setup_logging(log_level: str = "INFO") -> logging.Logger:
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger = logging.getLogger("truthcart")
    logger.setLevel(level)

    # Avoid duplicate handlers if re-initialized
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger

logger = setup_logging()

class SafeLogger:
    """Safely logs events without leaking secrets, internal paths or credentials."""
    
    @staticmethod
    def sanitize(msg: str) -> str:
        # Sanitize windows user directories or potential internal paths
        import re
        sanitized = re.sub(r'[A-Za-z]:\\[^\s]+', '[REDACTED_PATH]', msg)
        sanitized = re.sub(r'/(?:Users|home)/[^\s]+', '[REDACTED_PATH]', sanitized)
        # Redact JWT tokens, passwords, and API secrets from logs
        sanitized = re.sub(r'Bearer\s+[A-Za-z0-9\-_\.]+', 'Bearer [REDACTED_TOKEN]', sanitized)
        sanitized = re.sub(r'(?:password|secret|token)["\':=\s]+[^\s,"\'\}]+', 'password=[REDACTED]', sanitized, flags=re.IGNORECASE)
        return sanitized

    @classmethod
    def info(cls, msg: str, **kwargs: Any) -> None:
        logger.info(cls.sanitize(msg))

    @classmethod
    def warning(cls, msg: str, **kwargs: Any) -> None:
        logger.warning(cls.sanitize(msg))

    @classmethod
    def error(cls, msg: str, **kwargs: Any) -> None:
        logger.error(cls.sanitize(msg))

    @classmethod
    def debug(cls, msg: str, **kwargs: Any) -> None:
        logger.debug(cls.sanitize(msg))
