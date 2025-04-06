#!/usr/bin/env python3
"""
Error handling utilities for the w4b sensor management system.

This module provides functions and classes for consistent error handling,
reporting, and recovery across the system.
"""

import sys
import traceback
import logging
import time
from typing import Callable, Any, Optional, Dict, List, TypeVar, Generic, Union
from functools import wraps

# Type definitions for the retry decorator
T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])


class RetryOptions:
    """Configuration options for the retry mechanism."""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        exceptions: Union[List[Exception], type] = Exception
    ):
        """
        Initialize retry options.
        
        Args:
            max_retries: Maximum number of retry attempts.
            base_delay: Initial delay between retries in seconds.
            max_delay: Maximum delay between retries in seconds.
            backoff_factor: Factor by which the delay increases with each retry.
            exceptions: Exception or list of exceptions that trigger retries.
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        
        # Convert single exception to list for consistent handling
        if isinstance(exceptions, type) and issubclass(exceptions, Exception):
            self.exceptions = [exceptions]
        else:
            self.exceptions = exceptions
            

def retry(
    func: Optional[F] = None,
    *,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    exceptions: Union[List[Exception], type] = Exception,
    logger: Optional[logging.Logger] = None
) -> Union[Callable[[F], F], F]:
    """
    Decorator that retries a function if it raises specified exceptions.
    
    Implements an exponential backoff strategy with jitter for retries.
    
    Args:
        func: The function to wrap (automatically provided when used as decorator).
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay between retries in seconds.
        max_delay: Maximum delay between retries in seconds.
        backoff_factor: Factor by which the delay increases with each retry.
        exceptions: Exception or list of exceptions that trigger retries.
        logger: Logger to use for logging retries.
        
    Returns:
        Decorated function that will be retried on exceptions.
        
    Example:
        >>> @retry(max_retries=5, exceptions=[ConnectionError, TimeoutError])
        >>> async def fetch_data():
        >>>     # Function that might fail
    """
    if func is None:
        # Called with parameters
        return lambda f: retry(
            f,
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
            backoff_factor=backoff_factor,
            exceptions=exceptions,
            logger=logger
        )
    
    options = RetryOptions(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        backoff_factor=backoff_factor,
        exceptions=exceptions
    )
    
    # Get logger if not provided
    nonlocal_logger = logger or logging.getLogger('error_handling')
    
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        last_exception = None
        retry_count = 0
        
        while retry_count <= options.max_retries:
            try:
                return await func(*args, **kwargs)
            except tuple(options.exceptions) as e:
                last_exception = e
                retry_count += 1
                
                if retry_count > options.max_retries:
                    break
                
                # Calculate delay with exponential backoff
                delay = min(
                    options.base_delay * (options.backoff_factor ** (retry_count - 1)),
                    options.max_delay
                )
                
                nonlocal_logger.warning(
                    f"Retry {retry_count}/{options.max_retries} for {func.__name__} "
                    f"after error: {str(e)}. Retrying in {delay:.2f}s"
                )
                
                await asyncio.sleep(delay)
        
        # If we get here, all retries failed
        nonlocal_logger.error(
            f"All {options.max_retries} retries failed for {func.__name__}: {last_exception}"
        )
        raise last_exception
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        last_exception = None
        retry_count = 0
        
        while retry_count <= options.max_retries:
            try:
                return func(*args, **kwargs)
            except tuple(options.exceptions) as e:
                last_exception = e
                retry_count += 1
                
                if retry_count > options.max_retries:
                    break
                
                # Calculate delay with exponential backoff
                delay = min(
                    options.base_delay * (options.backoff_factor ** (retry_count - 1)),
                    options.max_delay
                )
                
                nonlocal_logger.warning(
                    f"Retry {retry_count}/{options.max_retries} for {func.__name__} "
                    f"after error: {str(e)}. Retrying in {delay:.2f}s"
                )
                
                time.sleep(delay)
        
        # If we get here, all retries failed
        nonlocal_logger.error(
            f"All {options.max_retries} retries failed for {func.__name__}: {last_exception}"
        )
        raise last_exception
    
    # Determine if the function is async or sync
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


def format_exception_with_context(exc_info=None) -> str:
    """
    Format an exception with context information for better debugging.
    
    Args:
        exc_info: Exception info tuple from sys.exc_info(). If None, it will be obtained.
        
    Returns:
        Formatted exception string with context information.
    """
    if exc_info is None:
        exc_info = sys.exc_info()
        
    if exc_info[0] is None:
        return "No exception information available"
    
    # Get exception details
    exc_type, exc_value, exc_traceback = exc_info
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    
    # Format with additional context
    formatted = "Exception details:\n"
    formatted += "".join(tb_lines)
    
    return formatted


def handle_critical_error(
    error: Exception,
    logger: logging.Logger,
    exit_code: int = 1,
    should_exit: bool = True
) -> None:
    """
    Handle a critical error that requires application shutdown.
    
    Args:
        error: The exception that occurred.
        logger: Logger to use for recording the error.
        exit_code: Exit code to use when terminating the process.
        should_exit: Whether to terminate the process.
    """
    # Format and log the error
    error_details = format_exception_with_context()
    logger.critical(f"Critical error: {str(error)}")
    logger.debug(f"Detailed exception:\n{error_details}")
    
    # Exit if requested
    if should_exit:
        logger.critical(f"Exiting application with code {exit_code}")
        sys.exit(exit_code)


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for fault tolerance.
    
    This class implements the circuit breaker pattern to prevent repeated
    calls to a failing service or resource. It has three states:
    - CLOSED: Normal operation, calls pass through
    - OPEN: Service is failing, calls are short-circuited
    - HALF_OPEN: Testing if service has recovered
    """
    
    # Circuit states
    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half_open'
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        name: str = 'default',
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize a new circuit breaker.
        
        Args:
            failure_threshold: Number of consecutive failures before opening the circuit.
            recovery_timeout: Time in seconds before attempting recovery.
            name: Name for this circuit breaker instance.
            logger: Logger for recording circuit state changes.
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.logger = logger or logging.getLogger('circuit_breaker')
        
        # Circuit state
        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0
        
    @property
    def state(self) -> str:
        """Get the current state of the circuit."""
        # Check if we should try recovery
        if (
            self._state == self.OPEN and
            time.time() - self._last_failure_time > self.recovery_timeout
        ):
            self._state = self.HALF_OPEN
            self.logger.info(f"Circuit {self.name} changed to HALF_OPEN: attempting recovery")
            
        return self._state
        
    def success(self) -> None:
        """Record a successful operation, potentially closing the circuit."""
        if self._state == self.HALF_OPEN:
            self._state = self.CLOSED
            self._failure_count = 0
            self.logger.info(f"Circuit {self.name} CLOSED: service recovered")
        elif self._state == self.CLOSED:
            self._failure_count = 0
            
    def failure(self) -> None:
        """Record a failed operation, potentially opening the circuit."""
        self._last_failure_time = time.time()
        
        if self._state == self.HALF_OPEN:
            self._state = self.OPEN
            self.logger.warning(f"Circuit {self.name} OPENED: recovery attempt failed")
        elif self._state == self.CLOSED:
            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._state = self.OPEN
                self.logger.warning(
                    f"Circuit {self.name} OPENED: reached failure threshold "
                    f"({self.failure_threshold})"
                )
                
    def is_closed(self) -> bool:
        """Check if the circuit is closed (normal operation)."""
        return self.state == self.CLOSED
        
    def is_open(self) -> bool:
        """Check if the circuit is fully open (failing)."""
        return self.state == self.OPEN
        
    def can_execute(self) -> bool:
        """Check if operation execution is allowed."""
        return self.state == self.CLOSED or self.state == self.HALF_OPEN
        
    def reset(self) -> None:
        """Reset the circuit breaker to closed state."""
        self._state = self.CLOSED
        self._failure_count = 0
        self.logger.info(f"Circuit {self.name} RESET to closed state")
        
    async def execute(self, func, *args, **kwargs):
        """
        Execute a function with circuit breaker protection.
        
        Args:
            func: Function to execute.
            *args, **kwargs: Arguments to pass to the function.
            
        Returns:
            Result of the function execution.
            
        Raises:
            CircuitBreakerError: If the circuit is open.
            Exception: Any exception raised by the function.
        """
        if not self.can_execute():
            raise CircuitBreakerError(f"Circuit {self.name} is OPEN")
            
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
                
            self.success()
            return result
        except Exception as e:
            self.failure()
            raise


class CircuitBreakerError(Exception):
    """Exception raised when a circuit breaker prevents an operation."""
    pass


# Fix the missing import
import asyncio
