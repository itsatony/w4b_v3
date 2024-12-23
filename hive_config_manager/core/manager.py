# hive_config_manager/core/manager.py

import os
from pathlib import Path
from typing import List, Dict, Optional, Union
import yaml
from datetime import datetime

from .schemas import validate_yaml_config
from .exceptions import HiveConfigError
from ..utils.id_generator import generate_hive_id, is_valid_hive_id
from ..utils.file_operations import safe_write_yaml, safe_read_yaml

from .validator import ConfigValidator
from .exceptions import (
    HiveConfigError, ConfigNotFoundError, DuplicateHiveError,
    ValidationError, LockError, FileSystemError
)

class HiveManager:
    """
    Manages hive configurations stored in YAML files.
    
    This class provides functionality to create, read, update, and delete
    hive configurations, as well as validate their structure and content.
    
    Attributes:
        base_path (Path): Base directory for hive configuration files
        
    Example:
        >>> manager = HiveManager()
        >>> hive_id = manager.create_hive(config_dict)
        >>> config = manager.get_hive(hive_id)
        >>> manager.update_hive(hive_id, new_config)
    """
    
    def __init__(self, base_path: Optional[Union[str, Path]] = None):
        """
        Initialize the HiveManager.
        
        Args:
            base_path: Optional path to configuration directory.
                      Defaults to {repo-root}/hives/
        """
        if base_path is None:
            # Try to find repository root (contains 'hives' directory)
            current = Path.cwd()
            while current.parent != current:
                if (current / 'hives').exists():
                    base_path = current / 'hives'
                    break
                current = current.parent
            if base_path is None:
                raise HiveConfigError("Could not find hives directory")
        
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)
        self.validator = ConfigValidator()

    def list_hives(self) -> List[str]:
        """
        List all existing hive configurations.
        
        Returns:
            List of hive IDs (without .yaml extension)
        """
        return [f.stem for f in self.base_path.glob('*.yaml')
                if f.stem != 'example']

    def get_hive(self, hive_id: str) -> Dict:
        """
        Get a hive configuration by ID.
        
        Args:
            hive_id: The ID of the hive to retrieve
            
        Returns:
            Dict containing the hive configuration
            
        Raises:
            HiveConfigError: If the hive doesn't exist or can't be read
        """
        config_path = self.base_path / f"{hive_id}.yaml"
        if not config_path.exists():
            raise HiveConfigError(f"Hive {hive_id} not found")
            
        try:
            return safe_read_yaml(config_path)
        except Exception as e:
            raise HiveConfigError(f"Error reading hive {hive_id}: {str(e)}")

    def create_hive(self, config: Dict) -> str:
        """
        Create a new hive configuration.
        
        Args:
            config: Dictionary containing the hive configuration
            
        Returns:
            The ID of the created hive
            
        Raises:
            HiveConfigError: If validation fails or file can't be written
        """
        try:
            # Validate configuration
            errors = self.validator.validate(config)
            if errors:
                raise ValidationError(errors)
            
            hive_id = config.get('hive_id')
            if hive_id:
                if not is_valid_hive_id(hive_id):
                    raise ValidationError(["Invalid hive ID format"])
            else:
                hive_id = generate_hive_id()
                config['hive_id'] = hive_id
            config_path = self.base_path / f"{hive_id}.yaml"
            
            if config_path.exists():
                raise DuplicateHiveError(hive_id)
            
            # Acquire lock before writing
            lock_path = config_path.with_suffix('.lock')
            if lock_path.exists():
                raise LockError(hive_id)
            
            try:
                lock_path.touch()
                safe_write_yaml(config_path, config)
                return hive_id
            finally:
                if lock_path.exists():
                    lock_path.unlink()
                    
        except OSError as e:
            raise FileSystemError(f"Failed to create hive: {str(e)}")

    def update_hive(self, hive_id: str, config: Dict) -> None:
        """
        Update an existing hive configuration.
        
        Args:
            hive_id: The ID of the hive to update
            config: New configuration dictionary
            
        Raises:
            HiveConfigError: If validation fails or file can't be written
        """
        config_path = self.base_path / f"{hive_id}.yaml"
        if not config_path.exists():
            raise ConfigNotFoundError(hive_id)
        
        # Validate configuration
        errors = self.validator.validate(config)
        if errors:
            raise ValidationError(errors)
        
        # Create backup and update with proper locking
        lock_path = config_path.with_suffix('.lock')
        if lock_path.exists():
            raise LockError(hive_id)
        
        try:
            lock_path.touch()
            self._backup_config(hive_id)
            safe_write_yaml(config_path, config)
        except OSError as e:
            raise FileSystemError(f"Failed to update hive: {str(e)}")
        finally:
            if lock_path.exists():
                lock_path.unlink()

    def delete_hive(self, hive_id: str) -> None:
        """
        Delete a hive configuration.
        
        Args:
            hive_id: The ID of the hive to delete
            
        Raises:
            HiveConfigError: If the hive doesn't exist or can't be deleted
        """
        config_path = self.base_path / f"{hive_id}.yaml"
        if not config_path.exists():
            raise HiveConfigError(f"Hive {hive_id} not found")
        
        try:
            # Create backup before deletion
            self._backup_config(hive_id)
            config_path.unlink()
        except Exception as e:
            raise HiveConfigError(f"Error deleting hive: {str(e)}")

    def validate_hive(self, hive_id: str) -> List[str]:
        """
        Validate a hive configuration.
        
        Args:
            hive_id: The ID of the hive to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        try:
            config = self.get_hive(hive_id)
            return self.validator.validate(config)
        except HiveConfigError as e:
            return [str(e)]
        except Exception as e:
            return [f"Unexpected error: {str(e)}"]

    def _backup_config(self, hive_id: str) -> None:
        """Create a backup of a hive configuration"""
        source = self.base_path / f"{hive_id}.yaml"
        if not source.exists():
            return
            
        backup_dir = self.base_path / "backups"
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"{hive_id}_{timestamp}.yaml"
        
        try:
            import shutil
            shutil.copy2(source, backup_path)
        except Exception as e:
            raise HiveConfigError(f"Error creating backup: {str(e)}")