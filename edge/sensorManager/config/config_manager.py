#!/usr/bin/env python3
"""
Configuration management for the w4b sensor system.

This module handles loading, validating, and providing access to the
system configuration from YAML files with environment variable substitution.
"""

import os
import re
import yaml
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple

import jsonschema
from jsonschema import validate


class ConfigurationError(Exception):
    """Exception raised for configuration errors."""
    pass


class ConfigManager:
    """
    Manages configuration loading, validation and access for the sensor system.
    
    This class handles loading configuration from YAML files, validating against
    a schema, substituting environment variables, and providing structured access
    to configuration values.
    
    Attributes:
        config (Dict[str, Any]): The loaded and validated configuration.
        config_path (Path): Path to the configuration file.
        schema_path (Optional[Path]): Path to the JSON schema for validation.
    """
    
    # Environment variable pattern: ${VAR_NAME}
    ENV_VAR_PATTERN = re.compile(r'\${([A-Za-z0-9_]+)}')
    
    def __init__(
        self, 
        config_path: Union[str, Path], 
        schema_path: Optional[Union[str, Path]] = None
    ) -> None:
        """
        Initialize a new configuration manager.
        
        Args:
            config_path: Path to the YAML configuration file.
            schema_path: Optional path to a JSON schema file for validation.
        
        Raises:
            ConfigurationError: If the configuration file cannot be loaded or parsed.
        """
        self.logger = logging.getLogger('sensors.config')
        self.config_path = Path(config_path)
        self.schema_path = Path(schema_path) if schema_path else None
        self.config = {}
        
        # Load configuration
        self._load_config()
        
    def _load_config(self) -> None:
        """
        Load and validate the configuration from the YAML file.
        
        This method loads the configuration, substitutes environment variables,
        and validates it against the schema if provided.
        
        Raises:
            ConfigurationError: If the configuration is invalid or cannot be loaded.
        """
        try:
            # Check if config file exists
            if not self.config_path.exists():
                raise ConfigurationError(f"Configuration file not found: {self.config_path}")
            
            # Load raw YAML
            with open(self.config_path, 'r') as f:
                raw_yaml = f.read()
            
            # Substitute environment variables
            processed_yaml = self._substitute_env_vars(raw_yaml)
            
            # Parse YAML
            self.config = yaml.safe_load(processed_yaml)
            
            # Validate against schema if provided
            if self.schema_path:
                self._validate_config()
                
            self.logger.info(f"Configuration loaded successfully from {self.config_path}")
                
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Error parsing YAML: {str(e)}")
        except Exception as e:
            raise ConfigurationError(f"Error loading configuration: {str(e)}")
    
    def _substitute_env_vars(self, raw_yaml: str) -> str:
        """
        Substitute environment variables in the raw YAML string.
        
        Args:
            raw_yaml: Raw YAML content with possible ${VAR_NAME} patterns.
            
        Returns:
            str: YAML with environment variables substituted.
            
        Raises:
            ConfigurationError: If a required environment variable is missing.
        """
        def replace_env_var(match):
            var_name = match.group(1)
            value = os.environ.get(var_name)
            if value is None:
                self.logger.warning(f"Environment variable not found: {var_name}")
                # Return the original ${VAR_NAME} if not found
                return match.group(0)
            return value
            
        return self.ENV_VAR_PATTERN.sub(replace_env_var, raw_yaml)
    
    def _validate_config(self) -> None:
        """
        Validate the configuration against the JSON schema.
        
        Raises:
            ConfigurationError: If the configuration does not match the schema.
        """
        try:
            # Load schema
            with open(self.schema_path, 'r') as f:
                schema = json.load(f)
                
            # Validate config against schema
            validate(instance=self.config, schema=schema)
            self.logger.info("Configuration validated successfully against schema")
            
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Error parsing schema: {str(e)}")
        except jsonschema.exceptions.ValidationError as e:
            raise ConfigurationError(f"Configuration validation failed: {str(e)}")
        except Exception as e:
            raise ConfigurationError(f"Error during schema validation: {str(e)}")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a configuration value by its dot-separated path.
        
        Args:
            key_path: Dot-separated path to the configuration value.
            default: Value to return if the path is not found.
            
        Returns:
            The configuration value, or the default if not found.
        
        Examples:
            >>> config.get('storage.host')
            'localhost'
            >>> config.get('sensors.0.id')
            'temp_01'
        """
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                # Handle array indices
                if key.isdigit() and isinstance(value, list):
                    index = int(key)
                    value = value[index]
                else:
                    value = value[key]
            return value
        except (KeyError, IndexError, TypeError):
            return default
    
    def get_sensors_by_type(self, sensor_type: str) -> List[Dict[str, Any]]:
        """
        Get all sensor configurations of a specific type.
        
        Args:
            sensor_type: The type of sensors to retrieve.
            
        Returns:
            List of sensor configurations matching the specified type.
        """
        sensors = self.get('sensors', [])
        return [s for s in sensors if s.get('type') == sensor_type and s.get('enabled', False)]
    
    def get_all_enabled_sensors(self) -> List[Dict[str, Any]]:
        """
        Get all enabled sensor configurations.
        
        Returns:
            List of all enabled sensor configurations.
        """
        sensors = self.get('sensors', [])
        return [s for s in sensors if s.get('enabled', False)]
