#!/usr/bin/env python3
"""
Configuration management for the W4B Raspberry Pi Image Generator.

This module handles loading, validation, and access to all configuration
settings needed for image generation, including environment variables,
command-line arguments, and configuration files.
"""

import os
import sys  # Add missing sys import
import logging
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

import yaml

from utils.error_handling import ConfigError


class ConfigManager:
    """
    Manages configuration for the image generator.
    
    This class handles loading configuration from multiple sources (environment
    variables, command-line arguments, YAML files) with proper precedence and
    validation.
    
    Attributes:
        config_file (Optional[str]): Path to YAML configuration file
        hive_id (Optional[str]): ID of the hive to configure
        cli_args (Dict[str, Any]): Command-line arguments
        config (Dict[str, Any]): Merged configuration
        logger (logging.Logger): Logger instance
    """
    
    # Default configuration values
    DEFAULT_CONFIG = {
        "base_image": {
            "version": "2023-12-05-raspios-bullseye-arm64-lite",
            "url_template": "https://downloads.raspberrypi.org/raspios_lite_arm64/images/raspios_lite_arm64-{version}/2023-12-05-raspios-bullseye-arm64-lite.img.xz",
            "checksum_type": "sha256",
            "checksum": None,  # Will be fetched dynamically
            "model": "pi4"
        },
        "system": {
            "hostname_prefix": "hive",
            "timezone": "UTC",
            "locale": "en_US.UTF-8",
            "keyboard": "us",
            "ssh": {
                "enabled": True,
                "password_auth": True,  # For initial setup
                "port": 22
            }
        },
        "security": {
            "firewall": {
                "enabled": True,
                "allow_ports": [22, 51820, 9100]
            },
            "vpn": {
                "type": "wireguard",
                "server": None,  # Must be provided
                "subnet": "10.10.0.0/24"
            }
        },
        "services": {
            "sensor_manager": {
                "enabled": True,
                "auto_start": True
            },
            "monitoring": {
                "enabled": True,
                "metrics_port": 9100
            },
            "database": {
                "type": "timescaledb",
                "version": "latest",
                "retention_days": 30
            }
        },
        "software": {
            "packages": [
                "postgresql-14",
                "postgresql-14-timescaledb-2",
                "wireguard",
                "python3-pip",
                "python3-venv",
                "prometheus-node-exporter"
            ],
            "python_packages": [
                "asyncpg",
                "prometheus-client",
                "pyyaml"
            ]
        },
        "output": {
            "directory": "/tmp",
            "naming_template": "{timestamp}_{hive_id}",
            "compress": True,
            "upload": False,
            "upload_url": None
        }
    }
    
    # Environment variable mapping
    ENV_MAPPING = {
        "W4B_HIVE_ID": ["hive_id"],
        "W4B_IMAGE_OUTPUT_DIR": ["output", "directory"],
        "W4B_RASPIOS_VERSION": ["base_image", "version"],
        "W4B_PI_MODEL": ["base_image", "model"],
        "W4B_TIMEZONE": ["system", "timezone"],
        "W4B_HOSTNAME_PREFIX": ["system", "hostname_prefix"],
        "W4B_DOWNLOAD_SERVER": ["output", "download_server"],
        "W4B_VPN_SERVER": ["security", "vpn", "server"]
    }
    
    def __init__(
        self, 
        config_file: Optional[str] = None,
        hive_id: Optional[str] = None,
        cli_args: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the configuration manager.
        
        Args:
            config_file: Path to YAML configuration file
            hive_id: ID of the hive to configure
            cli_args: Command-line arguments
        """
        self.config_file = config_file
        self.hive_id = hive_id
        self.cli_args = cli_args or {}
        self.config = {}
        self.logger = logging.getLogger("config")
    
    async def load(self) -> Dict[str, Any]:
        """
        Load and merge configuration from all sources.
        
        Configuration is loaded with the following precedence (highest to lowest):
        1. Command-line arguments
        2. Environment variables
        3. Configuration file
        4. Default values
        
        Returns:
            Dict[str, Any]: The merged configuration
        """
        # Start with default configuration
        self.config = self._deep_copy(self.DEFAULT_CONFIG)
        
        # If hive_id was provided to constructor, set it
        if self.hive_id:
            self.config["hive_id"] = self.hive_id
        
        # Load from configuration file
        if self.config_file:
            file_config = await self._load_from_file(self.config_file)
            self._merge_config(self.config, file_config)
        
        # Load from environment variables
        env_config = self._load_from_env()
        self._merge_config(self.config, env_config)
        
        # Load from command-line arguments
        cli_config = self._load_from_cli()
        self._merge_config(self.config, cli_config)
        
        # Substitute environment variables in string values
        self._substitute_env_vars(self.config)
        
        # If hive_id is specified, try to load hive-specific configuration
        if "hive_id" in self.config:
            hive_config = await self._load_hive_config(self.config["hive_id"])
            if hive_config:
                self._merge_config(self.config, hive_config)
        
        self.logger.debug(f"Loaded configuration: {self.config}")
        return self.config
    
    async def _load_from_file(self, file_path: str) -> Dict[str, Any]:
        """
        Load configuration from a YAML file.
        
        Args:
            file_path: Path to the YAML file
            
        Returns:
            Dict[str, Any]: Configuration from the file
            
        Raises:
            ConfigError: If the file cannot be read or parsed
        """
        try:
            path = Path(file_path)
            if not path.exists():
                self.logger.warning(f"Configuration file not found: {file_path}")
                return {}
                
            with open(path, "r") as f:
                config = yaml.safe_load(f)
                
            if not isinstance(config, dict):
                raise ConfigError(f"Invalid configuration format in {file_path}")
                
            return config
            
        except Exception as e:
            raise ConfigError(f"Error loading configuration from {file_path}: {e}")
    
    def _load_from_env(self) -> Dict[str, Any]:
        """
        Load configuration from environment variables.
        
        Returns:
            Dict[str, Any]: Configuration from environment variables
        """
        config = {}
        
        for env_var, path in self.ENV_MAPPING.items():
            value = os.environ.get(env_var)
            if value is not None:
                # Convert to appropriate type
                if value.lower() in ("true", "yes", "1"):
                    value = True
                elif value.lower() in ("false", "no", "0"):
                    value = False
                elif value.isdigit():
                    value = int(value)
                    
                # Set in nested config dict
                current = config
                for i, key in enumerate(path):
                    if i == len(path) - 1:
                        current[key] = value
                    else:
                        if key not in current:
                            current[key] = {}
                        current = current[key]
        
        return config
    
    def _load_from_cli(self) -> Dict[str, Any]:
        """
        Load configuration from command-line arguments.
        
        Returns:
            Dict[str, Any]: Configuration from CLI arguments
        """
        config = {}
        
        for key, value in self.cli_args.items():
            if value is not None:
                # Convert CLI args with dashes to nested dict paths
                if key.startswith("--"):
                    key = key[2:]  # Remove leading dashes
                
                path = key.replace("-", "_").split("_")
                
                # Set in nested config dict
                current = config
                for i, part in enumerate(path):
                    if i == len(path) - 1:
                        current[part] = value
                    else:
                        if part not in current:
                            current[part] = {}
                        current = current[part]
        
        return config
    
    async def _load_hive_config(self, hive_id: str) -> Dict[str, Any]:
        """
        Load hive-specific configuration from the hive configuration manager.
        
        Args:
            hive_id: ID of the hive
            
        Returns:
            Dict[str, Any]: Hive-specific configuration
        """
        try:
            # Try to import the hive configuration manager
            sys.path.append(str(Path(__file__).parents[3]))
            from hive_config_manager.core.manager import HiveManager
            
            # Get the hive configuration
            manager = HiveManager()
            hive_config = manager.get_hive(hive_id)
            
            # Map the hive config to our image generator config structure
            result = {}
            
            # Map security configuration
            if "security" in hive_config:
                security = hive_config["security"]
                
                # SSH configuration
                if "ssh" in security:
                    ssh = security["ssh"]
                    if "system" not in result:
                        result["system"] = {}
                    if "ssh" not in result["system"]:
                        result["system"]["ssh"] = {}
                    
                    if "public_key" in ssh:
                        result["system"]["ssh"]["public_key"] = ssh["public_key"]
                    if "private_key" in ssh:
                        result["system"]["ssh"]["private_key"] = ssh["private_key"]
                
                # WireGuard configuration
                if "wireguard" in security:
                    wg = security["wireguard"]
                    if "security" not in result:
                        result["security"] = {}
                    if "vpn" not in result["security"]:
                        result["security"]["vpn"] = {}
                    
                    if "private_key" in wg:
                        result["security"]["vpn"]["private_key"] = wg["private_key"]
                    if "public_key" in wg:
                        result["security"]["vpn"]["public_key"] = wg["public_key"]
                    if "endpoint" in wg:
                        result["security"]["vpn"]["server"] = wg["endpoint"]
                    if "config" in wg:
                        result["security"]["vpn"]["config"] = wg["config"]
                
                # Database configuration
                if "database" in security:
                    db = security["database"]
                    if "services" not in result:
                        result["services"] = {}
                    if "database" not in result["services"]:
                        result["services"]["database"] = {}
                    
                    if "password" in db:
                        result["services"]["database"]["password"] = db["password"]
                    if "username" in db:
                        result["services"]["database"]["username"] = db["username"]
            
            # Map hive metadata
            if "metadata" in hive_config:
                meta = hive_config["metadata"]
                
                if "name" in meta:
                    result["hive_name"] = meta["name"]
                
                if "location" in meta:
                    if "timezone" in meta["location"]:
                        if "system" not in result:
                            result["system"] = {}
                        result["system"]["timezone"] = meta["location"]["timezone"]
            
            return result
            
        except ImportError:
            self.logger.warning("Hive configuration manager not found, using default configuration")
            return {}
        except Exception as e:
            self.logger.warning(f"Error loading hive configuration: {str(e)}")
            return {}
    
    def _merge_config(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """
        Recursively merge source configuration into target.
        
        Args:
            target: Target configuration to merge into
            source: Source configuration to merge from
        """
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                # Recursively merge dictionaries
                self._merge_config(target[key], value)
            else:
                # Replace or add values
                target[key] = value
    
    def _substitute_env_vars(self, config: Dict[str, Any]) -> None:
        """
        Recursively substitute environment variables in string values.
        
        Environment variables should be in the format ${VAR_NAME} or ${VAR_NAME:-default}.
        
        Args:
            config: Configuration dictionary to process
        """
        for key, value in config.items():
            if isinstance(value, dict):
                self._substitute_env_vars(value)
            elif isinstance(value, str):
                # Pattern: ${VAR_NAME} or ${VAR_NAME:-default}
                pattern = r'\${([A-Za-z0-9_]+)(?::-([^}]*))?}'
                
                def replace_env_var(match):
                    var_name = match.group(1)
                    default = match.group(2)
                    return os.environ.get(var_name, default if default is not None else '')
                
                config[key] = re.sub(pattern, replace_env_var, value)
    
    def _deep_copy(self, obj: Any) -> Any:
        """
        Create a deep copy of an object.
        
        Args:
            obj: Object to copy
            
        Returns:
            Any: Deep copy of the object
        """
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy(item) for item in obj]
        else:
            return obj
    
    def validate(self) -> bool:
        """
        Validate the loaded configuration.
        
        Returns:
            bool: True if the configuration is valid, False otherwise
        """
        try:
            # Check for required fields
            required_fields = [
                ("hive_id", "Hive ID is required"),
            ]
            
            for field, message in required_fields:
                if field not in self.config or not self.config[field]:
                    self.logger.error(message)
                    return False
            
            # Validate hive_id format
            hive_id = self.config["hive_id"]
            if not re.match(r'^[a-zA-Z0-9_-]+$', hive_id):
                self.logger.error(f"Invalid hive ID format: {hive_id}")
                return False
            
            # If we have VPN configuration, validate it
            if "security" in self.config and "vpn" in self.config["security"]:
                vpn = self.config["security"]["vpn"]
                if vpn.get("type") == "wireguard":
                    if not vpn.get("server"):
                        self.logger.error("WireGuard VPN server endpoint is required")
                        return False
            
            # More validation rules can be added here
            
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration validation error: {str(e)}")
            return False
    
    def get(self, path: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        
        Args:
            path: Path to the configuration value (e.g., "system.timezone")
            default: Default value if the path doesn't exist
            
        Returns:
            Any: The configuration value or default
        """
        parts = path.split(".")
        current = self.config
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        
        return current
