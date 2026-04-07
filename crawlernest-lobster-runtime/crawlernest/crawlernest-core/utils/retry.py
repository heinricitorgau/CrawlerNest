"""
Retry decorator for handling transient failures.
"""

import functools
import logging
import time
from typing import Callable, TypeVar

T = TypeVar('T')


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    log_attempt_failures: bool = True,
    log_final_failure: bool = True,
):
    """
    Decorator to retry a function on failure.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch
        log_attempt_failures: Whether to log each failed retry attempt
        log_final_failure: Whether to log when all attempts fail
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            current_delay = delay
            last_exception = None
            logger = logging.getLogger('UniversityCrawler')
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        if log_attempt_failures:
                            logger.warning(
                                f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e}. "
                                f"Retrying in {current_delay:.1f}s..."
                            )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        if log_final_failure:
                            logger.error(f"All {max_attempts} attempts failed for {func.__name__}: {e}")
            
            if last_exception is not None:
                raise last_exception
            raise RuntimeError(f"Retry failed for {func.__name__} without captured exception.")
        
        return wrapper
    return decorator
