#!/usr/bin/env python3
"""
Base sensor interface for the w4b sensor management system.

This module defines the abstract base class that all sensor implementations
must inherit from, ensuring a consistent interface across different sensor types.
"""

import abc
from datetime import datetime
from typing import Dict, Any, Optional, List, Union, Tuple


class SensorBase(abc.ABC):
    """
    Abstract base class for all sensor implementations.
    
    This class defines the standard interface that all sensor implementations
    must adhere to, ensuring consistent behavior across different sensor types.
    
    Attributes:
        sensor_id (str): Unique identifier for the sensor instance.
        interface_config (Dict[str, Any]): Hardware interface configuration.
        calibration_config (Dict[str, Any]): Calibration parameters for the sensor.
        _initialized (bool): Flag indicating if the sensor has been initialized.
        _status (str): Current operational status of the sensor.
        _last_reading (Optional[Dict[str, Any]]): Most recent sensor reading.
        _last_read_time (Optional[datetime]): Timestamp of the most recent reading.
        _error_count (int): Counter for consecutive read errors.
    """

    def __init__(
        self,
        sensor_id: str,
        interface_config: Dict[str, Any],
        calibration_config: Dict[str, Any]
    ) -> None:
        """
        Initialize a new sensor instance.
        
        Args:
            sensor_id: Unique identifier for this sensor instance.
            interface_config: Configuration for the hardware interface.
            calibration_config: Calibration parameters for this sensor.
        """
        self.sensor_id = sensor_id
        self.interface_config = interface_config
        self.calibration_config = calibration_config
        self._initialized = False
        self._status = "not_initialized"
        self._last_reading = None
        self._last_read_time = None
        self._error_count = 0

    @abc.abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize the sensor hardware and prepare it for operation.
        
        This method should establish communication with the sensor hardware,
        configure it according to the interface_config, and ensure it is 
        operational.
        
        Returns:
            bool: True if initialization succeeded, False otherwise.
        
        Raises:
            SensorInitializationError: If the sensor cannot be initialized due to
                hardware failure, communication errors, or invalid configuration.
        """
        pass

    @abc.abstractmethod
    async def read(self) -> Dict[str, Any]:
        """
        Read the current value from the sensor.
        
        This method should obtain the current reading from the sensor,
        apply any necessary calibration, and return the processed value(s).
        
        Returns:
            Dict[str, Any]: A dictionary containing the sensor reading with at least:
                - 'value': The primary sensor reading value
                - 'unit': The unit of measurement (e.g., 'celsius', 'percent')
                - 'timestamp': When the reading was taken
                
                May also include additional sensor-specific data.
        
        Raises:
            SensorReadError: If the reading fails due to communication errors
                or hardware malfunction.
            SensorNotInitializedError: If read is called before initialization.
        """
        pass

    @abc.abstractmethod
    async def calibrate(self) -> Dict[str, Any]:
        """
        Perform a calibration routine for the sensor.
        
        This method should implement any sensor-specific calibration procedure
        and update the calibration parameters.
        
        Returns:
            Dict[str, Any]: Updated calibration parameters and calibration status.
        
        Raises:
            SensorCalibrationError: If calibration fails.
            SensorNotInitializedError: If calibrate is called before initialization.
        """
        pass

    @abc.abstractmethod
    async def validate(self) -> Tuple[bool, Optional[str]]:
        """
        Validate that the sensor is operating correctly.
        
        This method should perform checks to ensure the sensor is functioning
        properly and its readings are valid.
        
        Returns:
            Tuple[bool, Optional[str]]: A tuple containing:
                - A boolean indicating if the sensor is valid
                - An optional error message if validation failed
        """
        pass

    @abc.abstractmethod
    async def cleanup(self) -> None:
        """
        Release resources and perform any necessary cleanup.
        
        This method should properly shut down the sensor, release any acquired
        resources, and ensure the hardware is left in a safe state.
        """
        pass

    def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about this sensor instance.
        
        Returns:
            Dict[str, Any]: Metadata including sensor type, status, configuration,
                and other relevant information.
        """
        return {
            "sensor_id": self.sensor_id,
            "initialized": self._initialized,
            "status": self._status,
            "interface_type": self.interface_config.get("type", "unknown"),
            "last_read_time": self._last_read_time,
            "error_count": self._error_count,
        }

    def apply_calibration(self, raw_value: float) -> float:
        """
        Apply calibration parameters to a raw sensor value.
        
        This is a helper method that implements common calibration formulas.
        Sensor implementations can override this for sensor-specific calibration.
        
        Args:
            raw_value: The uncalibrated value from the sensor.
            
        Returns:
            float: The calibrated sensor value.
        """
        method = self.calibration_config.get("method", "linear")
        
        if method == "offset":
            offset = self.calibration_config.get("offset", 0.0)
            return raw_value + offset
            
        elif method == "scale":
            scale = self.calibration_config.get("scale", 1.0)
            return raw_value * scale
            
        elif method == "linear":
            # y = mx + b
            scale = self.calibration_config.get("scale", 1.0)
            offset = self.calibration_config.get("offset", 0.0)
            return (raw_value * scale) + offset
            
        elif method == "polynomial":
            # y = ax² + bx + c  (for 2nd degree, can extend for higher)
            coefficients = self.calibration_config.get("coefficients", [0, 1, 0])
            result = 0.0
            for i, coef in enumerate(reversed(coefficients)):
                result += coef * (raw_value ** i)
            return result
            
        # Default: return raw value if no valid calibration method
        return raw_value

    def update_status(self, is_success: bool, error_msg: Optional[str] = None) -> None:
        """
        Update the operational status of this sensor.
        
        Args:
            is_success: Whether the most recent operation succeeded.
            error_msg: Optional error message if operation failed.
        """
        if is_success:
            self._status = "operational"
            self._error_count = 0
        else:
            self._error_count += 1
            if self._error_count >= 3:
                self._status = "error"
            self._status = "warning"


class SensorError(Exception):
    """Base exception class for all sensor-related errors."""
    pass


class SensorInitializationError(SensorError):
    """Exception raised when sensor initialization fails."""
    pass


class SensorReadError(SensorError):
    """Exception raised when sensor reading operation fails."""
    pass


class SensorCalibrationError(SensorError):
    """Exception raised when sensor calibration fails."""
    pass


class SensorNotInitializedError(SensorError):
    """Exception raised when operations are attempted on an uninitialized sensor."""
    pass


class SensorValidationError(SensorError):
    """Exception raised when sensor validation fails."""
    pass
