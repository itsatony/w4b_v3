#!/usr/bin/env python3
"""
Pytest configuration and fixtures for the sensor management system tests.

This module defines fixtures and setup functions for testing the
sensor management system.
"""

import os
import sys
import asyncio
import logging
import tempfile
import pytest
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import modules we need for testing
from config.config_manager import ConfigManager
from sensors.base import SensorBase
from sensors.factory import SensorRegistry, SensorFactory
from utils.logging_setup import configure_logging


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_config_yaml():
    """Create a test configuration YAML string."""
    return """
version: 1.0.0
hive_id: test_hive
timezone: UTC

collectors:
  base_path: /tmp/collectors
  interval: 60
  timeout: 30

storage:
  type: timescaledb
  host: localhost
  port: 5432
  database: test_hivedb
  user: test_user
  password: test_password
  retention_days: 7
  batch_size: 100

sensors:
  - id: temp_test_01
    name: "Temperature Sensor Test"
    type: dht22
    enabled: true
    interface:
      type: gpio
      pin: 4
    collection:
      interval: 300
    calibration:
      method: linear
      offset: -0.5
      scale: 1.0
    metrics:
      - name: temperature
        unit: celsius
        precision: 1

sensor_types:
  dht22:
    module: tests.mock_sensors
    class: MockTemperatureSensor
    timeout: 5

logging:
  version: 1
  formatters:
    standard:
      format: '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
  handlers:
    console:
      class: logging.StreamHandler
      formatter: standard
      level: INFO
  loggers:
    sensors:
      level: INFO
      handlers: [console]
      propagate: false

metrics:
  prometheus:
    enabled: false
"""


@pytest.fixture
def test_config_path(test_config_yaml):
    """Create a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as temp:
        temp.write(test_config_yaml.encode('utf-8'))
        temp_path = temp.name
        
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def config_manager(test_config_path):
    """Create a ConfigManager instance with test configuration."""
    return ConfigManager(test_config_path)


@pytest.fixture
def sensor_registry():
    """Create a clean SensorRegistry for testing."""
    return SensorRegistry()


@pytest.fixture
def sensor_factory(sensor_registry):
    """Create a SensorFactory with the test registry."""
    return SensorFactory(sensor_registry)


# Define a mock sensor for testing
class MockSensor(SensorBase):
    """Mock sensor implementation for testing."""
    
    async def initialize(self):
        self._initialized = True
        self._status = "operational"
        return True
        
    async def read(self):
        if not self._initialized:
            raise SensorNotInitializedError("Sensor not initialized")
            
        # Return simulated data
        return {
            "value": 22.5,
            "unit": "celsius",
            "timestamp": datetime.now(timezone.utc)
        }
        
    async def calibrate(self):
        return {"status": "success", "method": "mock"}
        
    async def validate(self):
        return (True, None)
        
    async def cleanup(self):
        self._initialized = False
        self._status = "not_initialized"


# Ensure this import is available for fixtures
from datetime import datetime, timezone
from sensors.base import SensorNotInitializedError


# Create a module that our tests can import mock sensors from
@pytest.fixture(scope="session", autouse=True)
def create_mock_sensors_module():
    """Create a mock_sensors module for tests to import from."""
    module_dir = Path(__file__).parent / "mock_sensors"
    module_dir.mkdir(exist_ok=True)
    
    init_file = module_dir / "__init__.py"
    with open(init_file, "w") as f:
        f.write("""
from datetime import datetime, timezone
from sensors.base import SensorBase, SensorNotInitializedError

class MockTemperatureSensor(SensorBase):
    \"\"\"Mock temperature sensor for testing.\"\"\"
    
    async def initialize(self):
        self._initialized = True
        self._status = "operational"
        return True
        
    async def read(self):
        if not self._initialized:
            raise SensorNotInitializedError("Sensor not initialized")
            
        # Return simulated data
        return {
            "value": 22.5,
            "unit": "celsius",
            "timestamp": datetime.now(timezone.utc)
        }
        
    async def calibrate(self):
        return {"status": "success", "method": "mock"}
        
    async def validate(self):
        return (True, None)
        
    async def cleanup(self):
        self._initialized = False
        self._status = "not_initialized"
""")
    
    # Add to sys.path if not already there
    if str(module_dir.parent) not in sys.path:
        sys.path.insert(0, str(module_dir.parent))
        
    yield
    
    # Cleanup
    if init_file.exists():
        init_file.unlink()
    
    if module_dir.exists():
        module_dir.rmdir()
