# hive_config_manager/core/manager.py

import os
from pathlib import Path
from typing import List, Dict, Optional, Union, Tuple, Any
import yaml
from datetime import datetime

from .validator import ConfigValidator
from .exceptions import (
    HiveConfigError,
    ConfigNotFoundError,
    ValidationError,
    DuplicateHiveError,
    FileSystemError
)
from ..utils.id_generator import generate_hive_id
from ..utils.file_operations import safe_write_yaml, safe_read_yaml, acquire_lock, release_lock
from ..utils.security import SecurityUtils

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
        self.security = SecurityUtils()

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
            raise ConfigNotFoundError(hive_id)
            
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
        # Validate configuration
        errors = self.validator.validate(config)
        if errors:
            raise ValidationError(errors)
        
        hive_id = config.get('hive_id', generate_hive_id())
        config_path = self.base_path / f"{hive_id}.yaml"
        
        if config_path.exists():
            raise DuplicateHiveError(hive_id)
        
        try:
            safe_write_yaml(config_path, config)
            return hive_id
        except Exception as e:
            raise HiveConfigError(f"Error creating hive: {str(e)}")

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
        
        try:
            # Create backup
            self._backup_config(hive_id)
            # Update configuration
            safe_write_yaml(config_path, config)
        except Exception as e:
            raise HiveConfigError(f"Error updating hive: {str(e)}")

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
            raise ConfigNotFoundError(hive_id)
        
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
        except Exception as e:
            return [str(e)]

    def generate_security_credentials(self, hive_id: str, server_endpoint: str) -> Dict[str, Any]:
        """
        Generate security credentials for a hive.
        
        This includes:
        - SSH key pair for remote access
        - WireGuard keys and configuration
        - Database credentials
        - Local access credentials
        
        Args:
            hive_id: Hive ID to generate credentials for
            server_endpoint: WireGuard server endpoint (IP:Port)
            
        Returns:
            Dictionary containing all generated security credentials
            
        Raises:
            HiveConfigError: If generation fails
        """
        try:
            # Generate SSH key pair
            ssh_keys = SecurityUtils.generate_ssh_keypair(f"hive-{hive_id}")
            
            # Generate WireGuard keys
            wg_keys = SecurityUtils.generate_wireguard_keys()
            
            # For this example, we'll use fixed server public key
            # In production, this should be retrieved from the server
            server_public_key = "YOUR_SERVER_PUBLIC_KEY"
            
            # Generate client IP (this would be assigned by the server in production)
            # For now, we'll use a placeholder
            client_ip = "10.10.0.X/32"
            
            # Generate WireGuard configuration
            wg_config = SecurityUtils.generate_wireguard_config(
                private_key=wg_keys['private_key'],
                server_public_key=server_public_key,
                server_endpoint=server_endpoint,
                client_ip=client_ip
            )
            
            # Generate database credentials
            db_password = SecurityUtils.generate_secure_password(20)
            
            # Generate local access credentials
            local_user = "hiveadmin"
            local_password = SecurityUtils.generate_secure_password(16)
            
            return {
                "ssh": ssh_keys,
                "wireguard": {
                    **wg_keys,
                    "config": wg_config,
                    "client_ip": client_ip
                },
                "database": {
                    "username": "hiveuser",
                    "password": db_password
                },
                "local_access": {
                    "username": local_user,
                    "password": local_password
                }
            }
            
        except Exception as e:
            raise HiveConfigError(f"Failed to generate security credentials: {str(e)}")

    def apply_security_credentials(self, hive_id: str, credentials: Dict[str, Any]) -> None:
        """
        Apply generated security credentials to a hive configuration.
        
        Args:
            hive_id: Hive ID to apply credentials to
            credentials: Security credentials generated by generate_security_credentials
            
        Raises:
            HiveConfigError: If application fails
        """
        try:
            # Get current configuration
            config = self.get_hive(hive_id)
            
            # Initialize security section if not present
            if 'security' not in config:
                config['security'] = {}
            
            # Apply SSH credentials
            config['security']['ssh'] = {
                'private_key': credentials['ssh']['private_key'],
                'public_key': credentials['ssh']['public_key'],
                'enable_password_auth': False,
                'allow_root': False,
                'port': 22
            }
            
            # Apply WireGuard credentials
            config['security']['wireguard'] = {
                'private_key': credentials['wireguard']['private_key'],
                'public_key': credentials['wireguard']['public_key'],
                'client_ip': credentials['wireguard']['client_ip'],
                'config': credentials['wireguard']['config']
            }
            
            # Apply database credentials
            config['security']['database'] = {
                'username': credentials['database']['username'],
                'password': credentials['database']['password'],
                'host': 'localhost',
                'port': 5432,
                'database': 'hivedb'
            }
            
            # Apply local access credentials
            config['security']['local_access'] = {
                'username': credentials['local_access']['username'],
                'password': credentials['local_access']['password'],
                'sudo_without_password': False
            }
            
            # Update the configuration
            self.update_hive(hive_id, config)
            
        except Exception as e:
            raise HiveConfigError(f"Failed to apply security credentials: {str(e)}")

    def get_security_credentials(self, hive_id: str) -> Dict[str, Any]:
        """
        Get security credentials for a hive.
        
        Args:
            hive_id: Hive ID to get credentials for
            
        Returns:
            Dictionary containing security credentials
            
        Raises:
            HiveConfigError: If retrieval fails
            ConfigNotFoundError: If hive doesn't exist
        """
        config = self.get_hive(hive_id)
        
        if 'security' not in config:
            raise HiveConfigError(f"No security credentials found for hive {hive_id}")
            
        return config['security']

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