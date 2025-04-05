#!/usr/bin/env python3
"""
File Operations Utilities for Hive Configuration Manager
"""

import os
import yaml
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Union
import logging
import fcntl

logger = logging.getLogger(__name__)

def safe_read_yaml(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Safely read a YAML file with error handling.
    
    Args:
        file_path: Path to the YAML file
        
    Returns:
        Dictionary containing the parsed YAML
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        yaml.YAMLError: If the file contains invalid YAML
        PermissionError: If the file can't be read due to permissions
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    
    try:
        with open(path, 'r') as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        logger.error(f"YAML parsing error in {path}: {str(e)}")
        raise
    except PermissionError as e:
        logger.error(f"Permission error reading {path}: {str(e)}")
        raise

def safe_write_yaml(file_path: Union[str, Path], data: Dict[str, Any]) -> None:
    """
    Safely write a dictionary to a YAML file using atomic operations.
    
    Args:
        file_path: Path to the YAML file
        data: Dictionary to write
        
    Raises:
        PermissionError: If the file can't be written due to permissions
        OSError: If the write operation fails
    """
    path = Path(file_path)
    
    # Create directory if it doesn't exist
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write to a temporary file first for atomicity
    temp_fd, temp_path = tempfile.mkstemp(
        prefix=f"{path.stem}_", 
        suffix='.yaml',
        dir=path.parent
    )
    try:
        with os.fdopen(temp_fd, 'w') as temp_file:
            yaml.safe_dump(data, temp_file, sort_keys=False, default_flow_style=False)
        
        # On Unix systems, rename is atomic
        os.replace(temp_path, path)
    except Exception as e:
        # Clean up the temporary file in case of error
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        logger.error(f"Error writing to {path}: {str(e)}")
        raise

def acquire_lock(file_path: Union[str, Path], timeout: Optional[float] = None) -> Optional[int]:
    """
    Acquire a lock on a file.
    
    Args:
        file_path: Path to the file to lock
        timeout: Optional timeout in seconds, or None to block indefinitely
        
    Returns:
        File descriptor if lock acquired, None otherwise
        
    Raises:
        TimeoutError: If timeout is reached
        OSError: If lock can't be acquired due to OS errors
    """
    path = Path(file_path)
    lock_path = path.with_suffix('.lock')
    
    try:
        # Create lock file if it doesn't exist
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT)
        
        # Try to acquire an exclusive lock
        fcntl.flock(fd, fcntl.LOCK_EX | (fcntl.LOCK_NB if timeout is not None else 0))
        return fd
    except BlockingIOError:
        # Lock is held by another process
        os.close(fd)
        raise TimeoutError(f"Timeout waiting for lock on {path}")
    except OSError as e:
        if fd:
            os.close(fd)
        logger.error(f"Failed to acquire lock on {path}: {str(e)}")
        raise

def release_lock(fd: int) -> None:
    """
    Release a previously acquired lock.
    
    Args:
        fd: File descriptor returned by acquire_lock
    """
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    except OSError as e:
        logger.error(f"Error releasing lock: {str(e)}")