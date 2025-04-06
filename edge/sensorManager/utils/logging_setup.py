#!/usr/bin/env python3
"""
Logging configuration for the w4b sensor management system.

This module provides functions to set up structured logging with
different outputs and formatting.
"""

import os
import sys
import logging
import logging.config
from pathlib import Path
from typing import Dict, Any, Optional, Union


def configure_logging(
    config: Dict[str, Any],
    default_level: int = logging.INFO,
    logs_dir: Optional[Union[str, Path]] = None
) -> None:
    """
    Configure the logging system based on configuration.
    
    Args:
        config: Logging configuration dictionary.
        default_level: Default logging level if no configuration is provided.
        logs_dir: Directory for log files. Created if it doesn't exist.
    
    Note:
        The logging configuration follows the format used by
        logging.config.dictConfig().
    """
    # Create logs directory if specified
    if logs_dir:
        logs_path = Path(logs_dir)
        logs_path.mkdir(parents=True, exist_ok=True)
        
    # Apply logging configuration
    try:
        if 'logging' in config:
            # Process file handlers to ensure directories exist
            if 'handlers' in config['logging']:
                for handler_name, handler_config in config['logging']['handlers'].items():
                    if handler_config.get('class') == 'logging.handlers.RotatingFileHandler':
                        log_file = Path(handler_config.get('filename', ''))
                        if log_file and log_file.parent:
                            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Apply configuration
            logging.config.dictConfig(config['logging'])
            return
    except Exception as e:
        # Fall back to basic configuration if the dictConfig fails
        print(f"Error setting up logging configuration: {e}", file=sys.stderr)
        
    # Fallback to basic configuration
    logging.basicConfig(
        level=default_level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.warning("Using fallback logging configuration")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    This is a convenience function that gets a logger and ensures
    it's set up correctly.
    
    Args:
        name: Logger name, typically using dot notation for hierarchy.
        
    Returns:
        Configured logger instance.
    """
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter that adds contextual information to log messages.
    
    This adapter allows adding context (like hive_id, sensor_id) to log
    messages without passing them to each log call.
    """
    
    def process(self, msg, kwargs):
        # Add contextual info to the message
        context_str = ' '.join(f'{k}={v}' for k, v in self.extra.items())
        if context_str:
            return f"{msg} [{context_str}]", kwargs
        return msg, kwargs


def get_contextual_logger(name: str, **context) -> LoggerAdapter:
    """
    Get a logger that automatically adds contextual information to messages.
    
    Args:
        name: Base logger name.
        **context: Contextual information to add to each log message.
        
    Returns:
        LoggerAdapter that adds the specified context to log messages.
        
    Example:
        >>> logger = get_contextual_logger('sensors', hive_id='hive1', sensor_id='temp1')
        >>> logger.info("Reading sensor")
        # Output: "2023-08-15 12:34:56 [INFO] sensors: Reading sensor [hive_id=hive1 sensor_id=temp1]"
    """
    return LoggerAdapter(logging.getLogger(name), context)
