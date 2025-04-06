#!/usr/bin/env python3
"""
Temperature sensor implementations for the w4b sensor management system.

This module provides concrete implementations of temperature sensors,
including 1-Wire DS18B20 sensors commonly used in beehive monitoring.
"""

import asyncio
import time
import random
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

from sensors.base import (
    SensorBase,
    SensorInitializationError,
    SensorReadError,
    SensorCalibrationError,
    SensorNotInitializedError,
    SensorValidationError
)
from utils.w1_utils import (
    validate_sensor,
    read_temperature,
    discover_temperature_sensors
)


class TemperatureW1Sensor(SensorBase):
    """
    Implementation for 1-Wire temperature sensors (DS18B20).
    
    This class supports reading temperature data from DS18B20 sensors
    connected to the 1-Wire bus. It provides functions for reading,
    calibrating, and validating the sensor.
    
    Attributes:
        _device_path (str): Path to the w1_slave file for this sensor
        _min_valid_temp (float): Minimum valid temperature reading (°C)
        _max_valid_temp (float): Maximum valid temperature reading (°C)
        _read_retries (int): Number of retries for failed readings
        _retry_delay (float): Delay between retries in seconds
    """
    
    def __init__(
        self,
        sensor_id: str,
        interface_config: Dict[str, Any],
        calibration_config: Dict[str, Any]
    ) -> None:
        """
        Initialize a new 1-Wire temperature sensor.
        
        Args:
            sensor_id: Unique identifier for this sensor instance
            interface_config: Configuration for the 1-Wire interface, including:
                - bus_path: Path to the w1_slave file for the sensor
                - min_valid_temp: Optional minimum valid temperature (default: -55°C)
                - max_valid_temp: Optional maximum valid temperature (default: 125°C)
                - read_retries: Optional number of read retries (default: 3)
                - retry_delay: Optional delay between retries (default: 0.5s)
            calibration_config: Calibration parameters for this sensor
        """
        super().__init__(sensor_id, interface_config, calibration_config)
        
        # Get device path from config or auto-discover if not provided
        self._device_path = interface_config.get("bus_path")
        
        # Set validation parameters with reasonable defaults for DS18B20
        self._min_valid_temp = interface_config.get("min_valid_temp", -55.0)
        self._max_valid_temp = interface_config.get("max_valid_temp", 125.0)
        
        # Set retry parameters
        self._read_retries = interface_config.get("read_retries", 3)
        self._retry_delay = interface_config.get("retry_delay", 0.5)

    async def initialize(self) -> bool:
        """
        Initialize the temperature sensor.
        
        This method validates that the sensor exists and can be read.
        If no device path was provided in the configuration, it attempts
        to auto-discover a suitable sensor.
        
        Returns:
            bool: True if initialization succeeded, False otherwise
            
        Raises:
            SensorInitializationError: If the sensor cannot be initialized
        """
        try:
            # If no device path was provided, try to auto-discover
            if not self._device_path:
                sensors = discover_temperature_sensors()
                if not sensors:
                    raise SensorInitializationError(
                        f"No temperature sensors found on 1-Wire bus"
                    )
                # Use the first available sensor
                self._device_path = sensors[0]["path"]
            
            # Validate the sensor
            valid, error_msg = validate_sensor(self._device_path)
            if not valid:
                raise SensorInitializationError(
                    f"Sensor validation failed: {error_msg}"
                )
                
            # Mark as initialized
            self._initialized = True
            self._status = "operational"
            return True
            
        except Exception as e:
            error_msg = f"Failed to initialize temperature sensor: {str(e)}"
            raise SensorInitializationError(error_msg) from e

    async def read(self) -> Dict[str, Any]:
        """
        Read the current temperature from the sensor.
        
        This method reads the raw temperature from the 1-Wire device,
        applies calibration, and validates the reading.
        
        Returns:
            Dict[str, Any]: A dictionary containing the sensor reading:
                - 'value': The temperature in Celsius
                - 'unit': 'celsius'
                - 'timestamp': When the reading was taken
                
        Raises:
            SensorNotInitializedError: If the sensor is not initialized
            SensorReadError: If reading from the sensor fails
        """
        if not self._initialized:
            raise SensorNotInitializedError("Temperature sensor not initialized")
            
        # Read with retries
        temp_c = None
        read_success = False
        last_error = None
        
        for attempt in range(self._read_retries):
            try:
                success, temp_c = read_temperature(self._device_path)
                if success and temp_c is not None:
                    read_success = True
                    break
                    
                # Wait before retrying
                if attempt < self._read_retries - 1:
                    await asyncio.sleep(self._retry_delay)
                    
            except Exception as e:
                last_error = e
                if attempt < self._read_retries - 1:
                    await asyncio.sleep(self._retry_delay)
        
        # If all retries failed, raise an error
        if not read_success:
            error_msg = f"Failed to read temperature after {self._read_retries} attempts"
            if last_error:
                error_msg += f": {str(last_error)}"
            
            self.update_status(False, error_msg)
            raise SensorReadError(error_msg)
        
        # Apply calibration to the raw temperature
        calibrated_temp = self.apply_calibration(temp_c)
        
        # Validate the reading
        if not self._is_valid_temperature(calibrated_temp):
            error_msg = f"Temperature out of valid range: {calibrated_temp}°C"
            self.update_status(False, error_msg)
            raise SensorReadError(error_msg)
            
        # Prepare the reading data
        now = datetime.now(timezone.utc)
        reading = {
            "value": calibrated_temp,
            "unit": "celsius",
            "timestamp": now,
            "raw_value": temp_c
        }
        
        # Update sensor state
        self._last_reading = reading
        self._last_read_time = now
        self.update_status(True)
        
        return reading

    async def calibrate(self) -> Dict[str, Any]:
        """
        Perform a calibration routine for the temperature sensor.
        
        In the basic implementation, this just confirms the current
        calibration settings. In a more advanced implementation,
        this could prompt for reference temperatures and calculate
        calibration factors.
        
        Returns:
            Dict[str, Any]: Updated calibration parameters
            
        Raises:
            SensorNotInitializedError: If the sensor is not initialized
            SensorCalibrationError: If calibration fails
        """
        if not self._initialized:
            raise SensorNotInitializedError("Temperature sensor not initialized")
            
        try:
            # For a basic implementation, just report current calibration
            # In a more advanced version, we could:
            # 1. Read raw temperature multiple times
            # 2. Compare with a reference temperature
            # 3. Calculate offset/scale factors
            
            method = self.calibration_config.get("method", "linear")
            
            result = {
                "status": "success",
                "method": method,
                "timestamp": datetime.now(timezone.utc)
            }
            
            # Include method-specific parameters
            if method == "offset":
                result["offset"] = self.calibration_config.get("offset", 0.0)
            elif method == "scale":
                result["scale"] = self.calibration_config.get("scale", 1.0)
            elif method == "linear":
                result["scale"] = self.calibration_config.get("scale", 1.0)
                result["offset"] = self.calibration_config.get("offset", 0.0)
            
            return result
            
        except Exception as e:
            error_msg = f"Temperature sensor calibration failed: {str(e)}"
            raise SensorCalibrationError(error_msg) from e

    async def validate(self) -> Tuple[bool, Optional[str]]:
        """
        Validate that the temperature sensor is operating correctly.
        
        This method checks:
        1. The sensor can be read
        2. The reading is within reasonable bounds
        
        Returns:
            Tuple containing:
            - Boolean indicating if the sensor is valid
            - Error message if validation failed, None otherwise
        """
        if not self._initialized:
            return False, "Sensor not initialized"
            
        try:
            # Read the sensor (no calibration)
            success, temp_c = read_temperature(self._device_path)
            
            if not success or temp_c is None:
                return False, "Failed to read temperature"
                
            # Check if temperature is within reasonable bounds for a DS18B20
            if not self._is_valid_temperature(temp_c):
                return False, f"Temperature out of valid range: {temp_c}°C"
                
            return True, None
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    async def cleanup(self) -> None:
        """
        Release resources and perform any necessary cleanup.
        
        For the 1-Wire sensor, there's not much to clean up as we're just
        reading from a file and don't maintain any persistent connections.
        """
        self._initialized = False
        self._status = "not_initialized"

    def _is_valid_temperature(self, temp_c: float) -> bool:
        """
        Check if a temperature reading is within valid range.
        
        Args:
            temp_c: Temperature in Celsius
            
        Returns:
            bool: True if temperature is within valid range
        """
        return self._min_valid_temp <= temp_c <= self._max_valid_temp

    def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about this temperature sensor instance.
        
        Returns:
            Dict[str, Any]: Extended metadata specific to temperature sensor
        """
        # Get base metadata
        metadata = super().get_metadata()
        
        # Add temperature-specific metadata
        metadata.update({
            "sensor_type": "temperature",
            "device_path": self._device_path,
            "min_valid_temp": self._min_valid_temp,
            "max_valid_temp": self._max_valid_temp,
            "calibration_method": self.calibration_config.get("method", "linear")
        })
        
        # Add the last reading if available
        if self._last_reading:
            metadata["last_value"] = self._last_reading.get("value")
            metadata["last_unit"] = self._last_reading.get("unit")
            
        return metadata


class MockTemperatureSensor(SensorBase):
    """
    Mock implementation of a temperature sensor for testing and development.
    
    This class simulates a temperature sensor with configurable parameters
    for testing the system without actual hardware.
    """
    
    def __init__(
        self,
        sensor_id: str,
        interface_config: Dict[str, Any],
        calibration_config: Dict[str, Any]
    ) -> None:
        """
        Initialize a new mock temperature sensor.
        
        Args:
            sensor_id: Unique identifier for this sensor instance
            interface_config: Configuration including:
                - base_temp: Base temperature value (default: 25.0)
                - variation: Random variation range (default: 2.0)
                - simulate_failures: Whether to simulate random failures (default: False)
                - failure_rate: Probability of failure (0.0-1.0, default: 0.1)
            calibration_config: Calibration parameters (same as real sensor)
        """
        super().__init__(sensor_id, interface_config, calibration_config)
        
        # Mock sensor parameters
        self._base_temp = interface_config.get("base_temp", 25.0)
        self._variation = interface_config.get("variation", 2.0)
        self._simulate_failures = interface_config.get("simulate_failures", False)
        self._failure_rate = interface_config.get("failure_rate", 0.1)
        
        # Mock sensor state
        self._current_temp = self._base_temp

    async def initialize(self) -> bool:
        """Initialize the mock temperature sensor."""
        # Simulate initialization
        await asyncio.sleep(0.1)
        
        # Optionally simulate a failure
        if self._simulate_failures and random.random() < self._failure_rate:
            raise SensorInitializationError("Simulated initialization failure")
            
        self._initialized = True
        self._status = "operational"
        return True

    async def read(self) -> Dict[str, Any]:
        """Generate a simulated temperature reading."""
        if not self._initialized:
            raise SensorNotInitializedError("Mock temperature sensor not initialized")
            
        # Simulate reading delay
        await asyncio.sleep(0.05)
        
        # Optionally simulate a failure
        if self._simulate_failures and random.random() < self._failure_rate:
            raise SensorReadError("Simulated read failure")
            
        # Generate a simulated temperature by varying the current temperature
        # This creates more realistic sequential readings than pure random values
        variation = random.uniform(-0.5, 0.5)
        self._current_temp += variation
        
        # Apply boundaries to keep the temperature in a reasonable range
        if abs(self._current_temp - self._base_temp) > self._variation:
            # Drift back toward base_temp
            self._current_temp = self._current_temp * 0.8 + self._base_temp * 0.2
            
        # Apply calibration
        calibrated_temp = self.apply_calibration(self._current_temp)
        
        # Create the reading
        now = datetime.now(timezone.utc)
        reading = {
            "value": round(calibrated_temp, 2),
            "unit": "celsius",
            "timestamp": now,
            "raw_value": round(self._current_temp, 2)
        }
        
        # Update sensor state
        self._last_reading = reading
        self._last_read_time = now
        self.update_status(True)
        
        return reading

    async def calibrate(self) -> Dict[str, Any]:
        """Simulate calibration of the mock temperature sensor."""
        if not self._initialized:
            raise SensorNotInitializedError("Mock temperature sensor not initialized")
            
        # Simulate calibration delay
        await asyncio.sleep(0.2)
        
        # Optionally simulate a failure
        if self._simulate_failures and random.random() < self._failure_rate:
            raise SensorCalibrationError("Simulated calibration failure")
            
        # Return mock calibration data
        return {
            "status": "success",
            "method": self.calibration_config.get("method", "linear"),
            "offset": self.calibration_config.get("offset", 0.0),
            "scale": self.calibration_config.get("scale", 1.0),
            "timestamp": datetime.now(timezone.utc)
        }

    async def validate(self) -> Tuple[bool, Optional[str]]:
        """Validate the mock temperature sensor."""
        if not self._initialized:
            return False, "Sensor not initialized"
            
        # Optionally simulate a validation failure
        if self._simulate_failures and random.random() < self._failure_rate:
            return False, "Simulated validation failure"
            
        return True, None

    async def cleanup(self) -> None:
        """Clean up the mock temperature sensor."""
        # Simulate cleanup delay
        await asyncio.sleep(0.05)
        self._initialized = False
        self._status = "not_initialized"
