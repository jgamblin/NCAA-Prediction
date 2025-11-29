"""
Retry utilities for robust pipeline execution.
Provides decorators and functions for retrying operations with exponential backoff.
"""

import time
import functools
from typing import Callable, TypeVar, Any

T = TypeVar('T')


def retry_on_failure(
    max_retries: int = 3,
    initial_delay: float = 5.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    """
    Decorator to retry failed operations with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        backoff_factor: Multiplier for delay after each retry
        exceptions: Tuple of exception types to catch and retry
        
    Returns:
        Decorated function with retry logic
        
    Example:
        @retry_on_failure(max_retries=3, initial_delay=5)
        def fetch_data():
            return requests.get(url)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None
            delay = initial_delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        print(f"  ⚠️ Attempt {attempt + 1}/{max_retries + 1} failed: {e}")
                        print(f"  Retrying in {delay:.1f} seconds...")
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        print(f"  ❌ All {max_retries + 1} attempts failed")
            
            raise last_exception  # type: ignore
        return wrapper
    return decorator


def retry_call(
    func: Callable[..., T],
    *args: Any,
    max_retries: int = 3,
    initial_delay: float = 5.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
    **kwargs: Any,
) -> T:
    """
    Call a function with retry logic.
    
    Args:
        func: Function to call
        *args: Positional arguments to pass to func
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        backoff_factor: Multiplier for delay after each retry
        exceptions: Tuple of exception types to catch and retry
        **kwargs: Keyword arguments to pass to func
        
    Returns:
        Result of the function call
        
    Example:
        result = retry_call(fetch_data, url, max_retries=3)
    """
    last_exception = None
    delay = initial_delay
    
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            if attempt < max_retries:
                print(f"  ⚠️ Attempt {attempt + 1}/{max_retries + 1} failed: {e}")
                print(f"  Retrying in {delay:.1f} seconds...")
                time.sleep(delay)
                delay *= backoff_factor
            else:
                print(f"  ❌ All {max_retries + 1} attempts failed")
    
    raise last_exception  # type: ignore
