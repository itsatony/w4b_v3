#!/usr/bin/env python3
"""
Tests for temperature sensor implementations.
"""

import os
import pytest
import asyncio
from unittest.mock import patch, mock_open
from datetime import datetime, timezone
from typing import Dict, Any

from sensors.temperature import TemperatureW1Sensor, MockTemperatureSensor
from sensors.base import SensorNotInitializedError, SensorReadError


class TestTemperatureW1Sensor:
    """Test suite for the 1-Wire temperature sensor implementation."""
    
    @pytest.fixture
    def mock_device_data(self):
        """Mock data returned by the 1-Wire device file."""
        return (
            "75 01 4b 46 7f ff 0c 10 1c : crc=1c YES\n"
            "75 01 4b 46 7f ff 0c 10 1c t=23500"
        )
    
    @pytest.fixture
    def sensor_config(self):
        """Base configuration for temperature sensor tests."""
        return {
            "interface_config": {
                "bus_path": "/sys/bus/w1/devices/28-00000000/w1_slave",
                "min_valid_temp": -55.0,
                "max_valid_temp": 125.0,
                "read_retries": 2,
                "retry_delay": 0.1
            },
            "calibration_config": {
                "method": "linear",
                "offset": -0.5,
                "scale": 1.0
            }
        }
    
    @pytest.mark.asyncio
    async def test_initialization(self, sensor_config, mock_device_data):
        """Test sensor initialization."""
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=mock_device_data)):
            
            sensor = TemperatureW1Sensor(
                "test_temp_01",
                sensor_config["interface_config"],
                sensor_config["calibration_config"]
            )
            
            # Test initialization
            success = await sensor.initialize()
            assert success is True
            assert sensor._initialized is True
            assert sensor._status == "operational"
    
    @pytest.mark.asyncio
    async def test_initialization_failure(self, sensor_config):
        """Test sensor initialization failure."""
        with patch('os.path.exists', return_value=False):
            sensor = TemperatureW1Sensor(
                "test_temp_01",
                sensor_config["interface_config"],
                sensor_config["calibration_config"]
            )
            
            # Initialization should raise an exception when the device doesn't exist
            with pytest.raises(Exception):
                await sensor.initialize()
                
            assert sensor._initialized is False
    
    @pytest.mark.asyncio
    async def test_read_temperature(self, sensor_config, mock_device_data):
        """Test reading temperature from the sensor."""
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=mock_device_data)):
            
            sensor = TemperatureW1Sensor(
                "test_temp_01",
                sensor_config["interface_config"],
                sensor_config["calibration_config"]
            )
            
            # Initialize and read
            await sensor.initialize()
            reading = await sensor.read()
            
            # Check reading format
            assert isinstance(reading, dict)
            assert "value" in reading
            assert "unit" in reading
            assert "timestamp" in reading
            assert "raw_value" in reading
            
            # Check values (raw value is 23.5°C from mock data)
            # Calibrated value is 23.5 * 1.0 - 0.5 = 23.0°C
            assert reading["unit"] == "celsius"
            assert reading["raw_value"] == 23.5
            assert reading["value"] == 23.0
            assert isinstance(reading["timestamp"], datetime)
            
            # Check sensor state
            assert sensor._last_reading == reading
            assert sensor._last_read_time == reading["timestamp"]
    
    @pytest.mark.asyncio
    async def test_read_without_initialization(self, sensor_config):
        """Test that reading fails if sensor is not initialized."""
        sensor = TemperatureW1Sensor(
            "test_temp_01",
            sensor_config["interface_config"],
            sensor_config["calibration_config"]
        )
        
        # Reading without initialization should raise an exception
        with pytest.raises(SensorNotInitializedError):
            await sensor.read()
    
    @pytest.mark.asyncio
    async def test_read_invalid_data(self, sensor_config):
        """Test handling of invalid data from the sensor."""
        # Mock data with CRC failure
        invalid_data = "75 01 4b 46 7f ff 0c 10 1c : crc=1c NO\n"
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=invalid_data)):
            
            sensor = TemperatureW1Sensor(
                "test_temp_01",
                sensor_config["interface_config"],
                sensor_config["calibration_config"]
            )
            
            # Initialize and attempt to read
            await sensor.initialize()
            
            # Reading should fail due to CRC error
            with pytest.raises(SensorReadError):
                await sensor.read()
    
    @pytest.mark.asyncio
    async def test_calibration(self, sensor_config, mock_device_data):
        """Test sensor calibration."""
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=mock_device_data)):
            
            sensor = TemperatureW1Sensor(
                "test_temp_01",
                sensor_config["interface_config"],
                sensor_config["calibration_config"]
            )
            
            # Initialize and calibrate
            await sensor.initialize()
            calibration = await sensor.calibrate()
            
            # Check calibration format
            assert isinstance(calibration, dict)
            assert "status" in calibration
            assert "method" in calibration
            assert "timestamp" in calibration
            
            # Check values
            assert calibration["status"] == "success"
            assert calibration["method"] == "linear"
            assert calibration["scale"] == 1.0
            assert calibration["offset"] == -0.5
    
    @pytest.mark.asyncio
    async def test_validation(self, sensor_config, mock_device_data):
        """Test sensor validation."""
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=mock_device_data)):
            
            sensor = TemperatureW1Sensor(
                "test_temp_01",
                sensor_config["interface_config"],
                sensor_config["calibration_config"]
            )
            
            # Initialize and validate
            await sensor.initialize()
            valid, message = await sensor.validate()
            
            # Check validation result
            assert valid is True
            assert message is None
    
    @pytest.mark.asyncio
    async def test_cleanup(self, sensor_config, mock_device_data):
        """Test sensor cleanup."""
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=mock_device_data)):
            
            sensor = TemperatureW1Sensor(
                "test_temp_01",
                sensor_config["interface_config"],
                sensor_config["calibration_config"]
            )
            
            # Initialize, then clean up
            await sensor.initialize()
            assert sensor._initialized is True
            
            await sensor.cleanup()
            assert sensor._initialized is False
            assert sensor._status == "not_initialized"
    
    @pytest.mark.asyncio
    async def test_get_metadata(self, sensor_config, mock_device_data):
        """Test retrieving sensor metadata."""
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=mock_device_data)):
            
            sensor = TemperatureW1Sensor(
                "test_temp_01",
                sensor_config["interface_config"],
                sensor_config["calibration_config"]
            )
            
            # Get metadata without initialization
            metadata = sensor.get_metadata()
            assert metadata["sensor_id"] == "test_temp_01"
            assert metadata["initialized"] is False
            assert metadata["sensor_type"] == "temperature"
            
            # Initialize and read to update metadata
            await sensor.initialize()
            await sensor.read()
            
            # Get updated metadata
            metadata = sensor.get_metadata()
            assert metadata["initialized"] is True
            assert metadata["status"] == "operational"
            assert "last_value" in metadata
            assert metadata["last_value"] == 23.0
            assert metadata["last_unit"] == "celsius"


class TestMockTemperatureSensor:
    """Test suite for the mock temperature sensor implementation."""
    
    @pytest.fixture
    def sensor_config(self):
        """Base configuration for mock temperature sensor tests."""
        return {
            "interface_config": {
                "base_temp": 22.0,
                "variation": 1.0,
                "simulate_failures": False
            },
            "calibration_config": {
                "method": "offset",
                "offset": 0.5
            }
        }
    
    @pytest.mark.asyncio
    async def test_mock_read(self, sensor_config):
        """Test reading from mock temperature sensor."""
        sensor = MockTemperatureSensor(
            "mock_temp_01",
            sensor_config["interface_config"],
            sensor_config["calibration_config"]
        )
        
        # Initialize and read
        await sensor.initialize()
        reading = await sensor.read()
        
        # Check reading format
        assert isinstance(reading, dict)
        assert "value" in reading
        assert "unit" in reading
        assert "timestamp" in reading
        assert "raw_value" in reading
        
        # Check values are in reasonable range
        base = sensor_config["interface_config"]["base_temp"]
        variation = sensor_config["interface_config"]["variation"]
        offset = sensor_config["calibration_config"]["offset"]
        
        assert reading["unit"] == "celsius"
        assert abs(reading["raw_value"] - base) <= variation
        # Calibrated value should be raw + offset for offset method
        assert abs(reading["value"] - (reading["raw_value"] + offset)) < 0.001
    
    @pytest.mark.asyncio
    async def test_mock_calibration(self, sensor_config):
        """Test calibration of mock temperature sensor."""
        sensor = MockTemperatureSensor(
            "mock_temp_01",
            sensor_config["interface_config"],
            sensor_config["calibration_config"]
        )
        
        # Initialize and calibrate
        await sensor.initialize()
        calibration = await sensor.calibrate()
        
        # Check calibration data
        assert calibration["status"] == "success"
        assert calibration["method"] == "offset"
        assert calibration["offset"] == 0.5
    
    @pytest.mark.asyncio
    async def test_mock_failures(self):
        """Test simulated failures in mock temperature sensor."""
        # Configure to always fail
        config = {
            "interface_config": {
                "base_temp": 22.0,
                "simulate_failures": True,
                "failure_rate": 1.0  # Always fail
            },
            "calibration_config": {
                "method": "offset",
                "offset": 0.5
            }
        }
        
        sensor = MockTemperatureSensor(
            "mock_temp_01",
            config["interface_config"],
            config["calibration_config"]
        )
        
        # Initialization should fail
        with pytest.raises(Exception):
            await sensor.initialize()
