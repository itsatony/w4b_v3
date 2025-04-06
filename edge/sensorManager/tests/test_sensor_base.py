#!/usr/bin/env python3
"""
Tests for the sensor base classes and interfaces.
"""

import pytest
import asyncio
from datetime import datetime
from sensors.base import SensorBase, SensorError, SensorNotInitializedError


class TestSensorBase:
    """Test the SensorBase abstract class functionality."""
    
    def test_abstract_methods(self):
        """Test that SensorBase cannot be instantiated directly."""
        with pytest.raises(TypeError):
            # Should fail because SensorBase is abstract
            SensorBase(
                sensor_id="test",
                interface_config={},
                calibration_config={}
            )
            
    def test_calibration_methods(self):
        """Test the apply_calibration helper method."""
        # Create a concrete subclass for testing
        class TestSensor(SensorBase):
            async def initialize(self): pass
            async def read(self): pass
            async def calibrate(self): pass
            async def validate(self): pass
            async def cleanup(self): pass
            
        # Test linear calibration
        sensor = TestSensor(
            sensor_id="test1",
            interface_config={},
            calibration_config={
                "method": "linear",
                "scale": 2.0,
                "offset": 5.0
            }
        )
        # y = mx + b
        assert sensor.apply_calibration(10.0) == 25.0  # (10.0 * 2.0) + 5.0
        
        # Test offset calibration
        sensor = TestSensor(
            sensor_id="test2",
            interface_config={},
            calibration_config={
                "method": "offset",
                "offset": -2.5
            }
        )
        assert sensor.apply_calibration(10.0) == 7.5  # 10.0 + (-2.5)
        
        # Test scale calibration
        sensor = TestSensor(
            sensor_id="test3",
            interface_config={},
            calibration_config={
                "method": "scale",
                "scale": 0.5
            }
        )
        assert sensor.apply_calibration(10.0) == 5.0  # 10.0 * 0.5
        
        # Test polynomial calibration
        sensor = TestSensor(
            sensor_id="test4",
            interface_config={},
            calibration_config={
                "method": "polynomial",
                "coefficients": [2.0, 3.0, 1.0]  # 2x² + 3x + 1
            }
        )
        assert sensor.apply_calibration(2.0) == 15.0  # 2*(2²) + 3*2 + 1 = 8 + 6 + 1 = 15
        
    def test_status_update(self):
        """Test the status update mechanism."""
        # Create a concrete subclass for testing
        class TestSensor(SensorBase):
            async def initialize(self): pass
            async def read(self): pass
            async def calibrate(self): pass
            async def validate(self): pass
            async def cleanup(self): pass
            
        sensor = TestSensor(
            sensor_id="test_status",
            interface_config={},
            calibration_config={}
        )
        
        # Check initial status
        assert sensor._status == "not_initialized"
        assert sensor._error_count == 0
        
        # Test success update
        sensor.update_status(True)
        assert sensor._status == "operational"
        assert sensor._error_count == 0
        
        # Test error update
        sensor.update_status(False, "Test error")
        assert sensor._status == "warning"
        assert sensor._error_count == 1
        
        # Test error threshold
        sensor.update_status(False, "Another error")
        assert sensor._status == "warning"
        assert sensor._error_count == 2
        
        sensor.update_status(False, "Third error")
        assert sensor._status == "error"
        assert sensor._error_count == 3
        
        # Test recovery
        sensor.update_status(True)
        assert sensor._status == "operational"
        assert sensor._error_count == 0
        
    def test_metadata(self):
        """Test the metadata retrieval functionality."""
        # Create a concrete subclass for testing
        class TestSensor(SensorBase):
            async def initialize(self): pass
            async def read(self): pass
            async def calibrate(self): pass
            async def validate(self): pass
            async def cleanup(self): pass
            
        now = datetime.now()
        sensor = TestSensor(
            sensor_id="test_metadata",
            interface_config={"type": "test_interface"},
            calibration_config={}
        )
        
        # Set some values for testing
        sensor._initialized = True
        sensor._status = "operational"
        sensor._last_read_time = now
        
        # Get and check metadata
        metadata = sensor.get_metadata()
        assert metadata["sensor_id"] == "test_metadata"
        assert metadata["initialized"] is True
        assert metadata["status"] == "operational"
        assert metadata["interface_type"] == "test_interface"
        assert metadata["last_read_time"] == now
        assert metadata["error_count"] == 0
