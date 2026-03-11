from __future__ import annotations

import functools
import logging
import time
from typing import Callable

logger = logging.getLogger(__name__)


def log_decision(subsystem: str) -> Callable:
    """Decorator factory that logs function calls with subsystem context.

    Logs at INFO level on call entry and on successful return (including the
    result). Logs at ERROR level when an exception occurs, then re-raises.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger.info(
                "[%s] Calling %s with args=%s kwargs=%s",
                subsystem,
                func.__name__,
                args,
                kwargs,
            )
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                logger.error(
                    "[%s] %s raised %s: %s",
                    subsystem,
                    func.__name__,
                    type(exc).__name__,
                    exc,
                )
                raise
            logger.info(
                "[%s] %s returned: %s",
                subsystem,
                func.__name__,
                result,
            )
            return result

        return wrapper

    return decorator


def timed(operation_name: str) -> Callable:
    """Decorator factory that logs execution time at DEBUG level.

    Elapsed time is reported in milliseconds.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.monotonic()
            try:
                result = func(*args, **kwargs)
            finally:
                elapsed_ms = (time.monotonic() - start) * 1000.0
                logger.debug(
                    "[timed] %s (%s) elapsed %.3f ms",
                    operation_name,
                    func.__name__,
                    elapsed_ms,
                )
            return result

        return wrapper

    return decorator
