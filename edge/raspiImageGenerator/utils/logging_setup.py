#!/usr/bin/env python3
"""
Logging utilities for the W4B Raspberry Pi Image Generator.

This module provides functions for setting up and configuring logging
throughout the application.
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union


def configure_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    log_format: Optional[str] = None
) -> None:
    """
    Configure the logging system.
    
    Args:
        level: Logging level to use
        log_file: Path to log file (if None, logs to console only)
        log_format: Format string for log messages
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        handler.close()
        root_logger.removeHandler(handler)
    
    # Set up console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # Set up formatter
    if log_format is None:
        log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    formatter = logging.Formatter(log_format)
    console_handler.setFormatter(formatter)
    
    # Add console handler to root logger
    root_logger.addHandler(console_handler)
    
    # Set up file handler if requested
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Create application-specific logger
    image_gen_logger = logging.getLogger("image_generator")
    image_gen_logger.setLevel(level)
    
    # Configure other loggers to be less verbose
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)


class ContextAdapter(logging.LoggerAdapter):
    """
    Logger adapter that adds context information to log records.
    
    This class allows adding additional context fields to log messages
    for better traceability and filtering.
    """
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """
        Process the log message and add context information.
        
        Args:
            msg: Original log message
            kwargs: Keyword arguments for the logger method
            
        Returns:
            tuple: (modified_message, modified_kwargs)
        """
        # Format message to include context
        if self.extra:
            context_str = " ".join(f"[{k}={v}]" for k, v in self.extra.items())
            msg = f"{msg} {context_str}"
        
        return msg, kwargs


def get_logger(name: str, **context: Any) -> Union[logging.Logger, ContextAdapter]:
    """
    Get a logger with optional context information.
    
    Args:
        name: Logger name
        **context: Additional context fields to include in logs
        
    Returns:
        Union[logging.Logger, ContextAdapter]: Logger instance
    """
    logger = logging.getLogger(name)
    
    if context:
        return ContextAdapter(logger, context)
    else:
        return logger


def configure_build_logging(
    work_dir: Path,
    build_id: str,
    debug: bool = False
) -> Path:
    """
    Configure logging for a specific build process.
    
    Args:
        work_dir: Working directory for the build
        build_id: Unique ID for the build
        debug: Whether to enable debug logging
        
    Returns:
        Path: Path to the log file
    """
    log_dir = work_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = log_dir / f"build_{build_id}_{timestamp}.log"
    
    # Configure root logger
    level = logging.DEBUG if debug else logging.INFO
    configure_logging(
        level=level,
        log_file=str(log_file),
        log_format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    return log_file
