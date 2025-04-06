#!/usr/bin/env python3
"""
Error handling utilities for the W4B Raspberry Pi Image Generator.

This module provides custom exception types and utilities for handling errors
in a consistent manner throughout the application.
"""

import logging
import functools
import time
import traceback
from typing import Type, Callable, Any, List, Dict, Optional, Union, Tuple


class ImageGeneratorError(Exception):
    """Base exception for all image generator errors."""
    pass


class ConfigError(ImageGeneratorError):
    """Exception raised for configuration errors."""
    pass


class ImageBuildError(ImageGeneratorError):
    """Exception raised for errors during image building."""
    pass


class DiskOperationError(ImageGeneratorError):
    """Exception raised for errors during disk operations."""
    pass


class ValidationError(ImageGeneratorError):
    """Exception raised for validation errors."""
    pass


class NetworkError(ImageGeneratorError):
    """Exception raised for network-related errors."""
    pass


class SecurityError(ImageGeneratorError):
    """Exception raised for security-related errors."""
    pass


class RetryableError(ImageGeneratorError):
    """Exception that can be retried."""
    pass


def retry(
    max_retries: int = 3, 
    delay: float = 1.0, 
    backoff: float = 2.0,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception
) -> Callable:
    """
    Retry decorator for functions that might fail temporarily.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Backoff multiplier (how much to increase delay after each failure)
        exceptions: Exception types that trigger a retry
        
    Returns:
        Callable: Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = logging.getLogger(func.__module__)
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                            f"after error: {str(e)}"
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"Maximum retries ({max_retries}) reached for {func.__name__}. "
                            f"Last error: {str(e)}"
                        )
            
            raise last_exception

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = logging.getLogger(func.__module__)
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                            f"after error: {str(e)}"
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"Maximum retries ({max_retries}) reached for {func.__name__}. "
                            f"Last error: {str(e)}"
                        )
            
            raise last_exception
        
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for fault tolerance.
    
    This class implements the circuit breaker pattern to prevent repeated calls
    to failing operations, allowing time for the system to recover.
    
    Attributes:
        failure_threshold (int): Number of failures before opening the circuit
        recovery_timeout (float): Time in seconds to wait before trying again
        name (str): Name for this circuit breaker
        logger (logging.Logger): Logger instance
        failures (int): Current failure count
        last_failure_time (Optional[float]): Time of the last failure
        state (str): Current state - 'closed', 'open', or 'half-open'
    """
    
    def __init__(
        self, 
        failure_threshold: int = 3, 
        recovery_timeout: float = 60.0,
        name: str = "default",
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening the circuit
            recovery_timeout: Time in seconds to wait before trying again
            name: Name for this circuit breaker
            logger: Logger instance
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self.logger = logger or logging.getLogger("circuit_breaker")
        
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    def can_execute(self) -> bool:
        """
        Check if the operation can be executed.
        
        Returns:
            bool: True if the circuit is closed or half-open, False if open
        """
        if self.state == "closed":
            return True
        
        if self.state == "open":
            # Check if recovery timeout has passed
            if self.last_failure_time is not None:
                elapsed = time.time() - self.last_failure_time
                if elapsed >= self.recovery_timeout:
                    self.logger.info(
                        f"Circuit {self.name} entering half-open state after {elapsed:.1f}s"
                    )
                    self.state = "half-open"
                    return True
            return False
        
        # Half-open state
        return True
    
    def success(self) -> None:
        """Record a successful operation."""
        if self.state == "half-open":
            self.logger.info(f"Circuit {self.name} closing after successful operation")
            self.reset()
        elif self.state == "closed":
            # Reset failure count on success in closed state
            self.failures = 0
    
    def failure(self) -> None:
        """Record a failed operation."""
        self.failures += 1
        self.last_failure_time = time.time()
        
        if self.state == "half-open" or (self.state == "closed" and self.failures >= self.failure_threshold):
            self.state = "open"
            self.logger.warning(
                f"Circuit {self.name} opened after {self.failures} failures"
            )
    
    def reset(self) -> None:
        """Reset the circuit breaker to closed state."""
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"
    
    async def execute(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Execute a function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            Any: Result of the function
            
        Raises:
            Exception: If the function fails or circuit is open
        """
        if not self.can_execute():
            raise RetryableError(
                f"Circuit {self.name} is open due to previous failures"
            )
        
        try:
            import inspect
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
                
            self.success()
            return result
            
        except Exception as e:
            self.failure()
            raise e


def format_traceback(e: Exception) -> str:
    """
    Format an exception's traceback into a readable string.
    
    Args:
        e: The exception
        
    Returns:
        str: Formatted traceback
    """
    return "".join(traceback.format_exception(type(e), e, e.__traceback__))
