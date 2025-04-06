#!/usr/bin/env python3
"""
Tests for the configuration management system.
"""

import pytest
import os
import tempfile
from pathlib import Path
from config.config_manager import ConfigManager, ConfigurationError


class TestConfigManager:
    """Test the ConfigManager class functionality."""
    
    def test_load_config(self, test_config_path):
        """Test loading a valid configuration file."""
        config_manager = ConfigManager(test_config_path)
        
        # Verify basic config values
        assert config_manager.config['hive_id'] == 'test_hive'
        assert config_manager.config['timezone'] == 'UTC'
        assert config_manager.config['collectors']['interval'] == 60
        
    def test_env_var_substitution(self):
        """Test environment variable substitution in config."""
        # Create a temporary config with env vars
        config_content = """
        hive_id: ${TEST_HIVE_ID}
        api_key: ${TEST_API_KEY}
        """
        
        # Set the environment variables
        os.environ['TEST_HIVE_ID'] = 'hive_from_env'
        os.environ['TEST_API_KEY'] = 'secret_key_12345'
        
        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as temp:
            temp.write(config_content.encode('utf-8'))
            temp_path = temp.name
            
        try:
            # Load config with env vars
            config_manager = ConfigManager(temp_path)
            
            # Verify substitution
            assert config_manager.config['hive_id'] == 'hive_from_env'
            assert config_manager.config['api_key'] == 'secret_key_12345'
        finally:
            # Cleanup
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                
    def test_get_method(self, test_config_path):
        """Test the get method with dot notation."""
        config_manager = ConfigManager(test_config_path)
        
        # Test simple keys
        assert config_manager.get('hive_id') == 'test_hive'
        
        # Test nested keys
        assert config_manager.get('storage.host') == 'localhost'
        assert config_manager.get('storage.port') == 5432
        
        # Test array access
        assert config_manager.get('sensors.0.id') == 'temp_test_01'
        assert config_manager.get('sensors.0.interface.type') == 'gpio'
        
        # Test default value
        assert config_manager.get('nonexistent.key', 'default') == 'default'
        
    def test_get_sensors_by_type(self, test_config_path):
        """Test retrieving sensors by type."""
        config_manager = ConfigManager(test_config_path)
        
        # Get dht22 sensors
        dht22_sensors = config_manager.get_sensors_by_type('dht22')
        assert len(dht22_sensors) == 1
        assert dht22_sensors[0]['id'] == 'temp_test_01'
        
        # Get nonexistent sensor type
        nonexistent = config_manager.get_sensors_by_type('nonexistent')
        assert len(nonexistent) == 0
        
    def test_get_all_enabled_sensors(self, test_config_path):
        """Test retrieving all enabled sensors."""
        config_manager = ConfigManager(test_config_path)
        
        # By default, our test has one enabled sensor
        enabled_sensors = config_manager.get_all_enabled_sensors()
        assert len(enabled_sensors) == 1
        
        # Create a config with multiple sensors, some disabled
        config_content = """
        sensors:
          - id: sensor1
            type: temp
            enabled: true
          - id: sensor2
            type: humidity
            enabled: false
          - id: sensor3
            type: pressure
            enabled: true
        """
        
        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as temp:
            temp.write(config_content.encode('utf-8'))
            temp_path = temp.name
            
        try:
            config_manager = ConfigManager(temp_path)
            enabled = config_manager.get_all_enabled_sensors()
            
            assert len(enabled) == 2
            assert enabled[0]['id'] == 'sensor1'
            assert enabled[1]['id'] == 'sensor3'
        finally:
            # Cleanup
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                
    def test_file_not_found(self):
        """Test handling of nonexistent configuration file."""
        with pytest.raises(ConfigurationError) as excinfo:
            ConfigManager("/path/that/does/not/exist.yaml")
        
        assert "not found" in str(excinfo.value)
        
    def test_invalid_yaml(self):
        """Test handling of invalid YAML syntax."""
        # Create a temporary file with invalid YAML
        invalid_yaml = """
        key1: value1
        key2: value2:
          - this is invalid
            YAML syntax
        """
        
        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as temp:
            temp.write(invalid_yaml.encode('utf-8'))
            temp_path = temp.name
            
        try:
            with pytest.raises(ConfigurationError) as excinfo:
                ConfigManager(temp_path)
            
            assert "Error parsing YAML" in str(excinfo.value)
        finally:
            # Cleanup
            if os.path.exists(temp_path):
                os.unlink(temp_path)
