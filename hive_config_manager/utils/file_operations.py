# hive_config_manager/utils/file_operations.py

import os
import yaml
from pathlib import Path
from typing import Dict, Any
from ..core.exceptions import FileSystemError

def safe_write_yaml(path: Path, data: Dict[str, Any]) -> None:
    """
    Safely write YAML data to file with atomic operation.
    
    Args:
        path: Path to write to
        data: Data to write
        
    Raises:
        FileSystemError: If write operation fails
    """
    temp_path = path.with_suffix('.tmp')
    try:
        with open(temp_path, 'w') as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
        # Atomic rename
        os.replace(temp_path, path)
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise FileSystemError(f"Failed to write configuration: {str(e)}")

def safe_read_yaml(path: Path) -> Dict[str, Any]:
    """
    Safely read YAML data from file.
    
    Args:
        path: Path to read from
        
    Returns:
        Parsed YAML data
        
    Raises:
        FileSystemError: If read operation fails
    """
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except Exception as e:
        raise FileSystemError(f"Failed to read configuration: {str(e)}")

def create_backup(source: Path, backup_dir: Path) -> Path:
    """
    Create a backup of a configuration file.
    
    Args:
        source: Source file to backup
        backup_dir: Directory for backups
        
    Returns:
        Path to backup file
        
    Raises:
        FileSystemError: If backup operation fails
    """
    from datetime import datetime
    
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{source.stem}_{timestamp}{source.suffix}"
    
    try:
        import shutil
        shutil.copy2(source, backup_path)
        return backup_path
    except Exception as e:
        raise FileSystemError(f"Failed to create backup: {str(e)}")

def check_file_permissions(path: Path) -> None:
    """
    Check if file permissions are secure.
    
    Args:
        path: Path to check
        
    Raises:
        FileSystemError: If permissions are insecure
    """
    try:
        stat = path.stat()
        # Check if file is owned by current user
        if stat.st_uid != os.getuid():
            raise FileSystemError(f"File {path} not owned by current user")
        # Check if file permissions are too open
        if stat.st_mode & 0o077:
            raise FileSystemError(f"File {path} has insecure permissions")
    except OSError as e:
        raise FileSystemError(f"Failed to check file permissions: {str(e)}")

def acquire_lock(path: Path, timeout: int = 10) -> bool:
    """
    Try to acquire a lock file with timeout.
    
    Args:
        path: Path to lock file
        timeout: Timeout in seconds
        
    Returns:
        True if lock acquired, False if timeout
        
    Raises:
        FileSystemError: If lock operation fails
    """
    import time
    lock_path = path.with_suffix('.lock')
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            if not lock_path.exists():
                lock_path.touch()
                return True
        except OSError as e:
            raise FileSystemError(f"Failed to create lock file: {str(e)}")
        time.sleep(0.1)
    
    return False

def release_lock(path: Path) -> None:
    """
    Release a lock file.
    
    Args:
        path: Path to lock file
        
    Raises:
        FileSystemError: If unlock operation fails
    """
    lock_path = path.with_suffix('.lock')
    try:
        if lock_path.exists():
            lock_path.unlink()
    except OSError as e:
        raise FileSystemError(f"Failed to release lock: {str(e)}")