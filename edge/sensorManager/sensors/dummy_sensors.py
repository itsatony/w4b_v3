#!/usr/bin/env python3
"""
Dummy sensor implementations for the w4b sensor management system.

This module provides mock implementations of various sensor types for
development, testing, and demonstration purposes. Each sensor generates
realistic but simulated data that follows expected patterns.
"""

import asyncio
import random
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
import math
import logging

from sensors.base import (
    SensorBase,
    SensorInitializationError,
    SensorReadError,
    SensorCalibrationError,
    SensorNotInitializedError
)


class DummySensorBase(SensorBase):
    """
    Base class for all dummy sensors with common simulation functionality.
    
    This class provides common implementations for dummy sensors, including
    noise generation, simulated failures, and realistic data patterns.
    
    Attributes:
        _base_value (float): Base value around which readings will fluctuate
        _noise_level (float): Intensity of random noise in readings
        _drift_factor (float): How much the base value drifts over time
        _simulate_failures (bool): Whether to randomly simulate failures
        _failure_rate (float): Probability of a simulated failure (0.0-1.0)
        _seasonal_factor (float): Intensity of time-based patterns
        _init_delay (float): Simulated initialization delay in seconds
        _read_delay (float): Simulated read delay in seconds
        _last_value (float): Last generated reading (for continuity)
    """
    
    def __init__(
        self,
        sensor_id: str,
        interface_config: Dict[str, Any],
        calibration_config: Dict[str, Any]
    ) -> None:
        """Initialize dummy sensor with configuration."""
        super().__init__(sensor_id, interface_config, calibration_config)
        
        # Get simulation parameters from config or use defaults
        sim_config = interface_config.get("simulation", {})
        self._base_value = sim_config.get("base_value", 20.0)
        self._noise_level = sim_config.get("noise_level", 0.5)
        self._drift_factor = sim_config.get("drift_factor", 0.1)
        self._simulate_failures = sim_config.get("simulate_failures", False)
        self._failure_rate = sim_config.get("failure_rate", 0.05)
        self._seasonal_factor = sim_config.get("seasonal_factor", 1.0)
        self._init_delay = sim_config.get("init_delay", 0.5)
        self._read_delay = sim_config.get("read_delay", 0.2)
        
        # Internal state
        self._last_value = None
        self._creation_time = time.time()
        
        # Logger
        self.logger = logging.getLogger(f"sensors.dummy.{sensor_id}")

    async def initialize(self) -> bool:
        """Simulate sensor initialization."""
        self.logger.debug(f"Initializing dummy sensor {self.sensor_id}")
        
        # Simulate initialization delay
        await asyncio.sleep(self._init_delay)
        
        # Randomly fail initialization if configured
        if self._simulate_failures and random.random() < self._failure_rate:
            self.logger.warning(f"Simulating initialization failure for {self.sensor_id}")
            raise SensorInitializationError("Simulated initialization failure")
        
        self._initialized = True
        self._status = "operational"
        return True

    async def read(self) -> Dict[str, Any]:
        """Generate a simulated sensor reading."""
        if not self._initialized:
            raise SensorNotInitializedError(f"Dummy sensor {self.sensor_id} not initialized")
        
        try:
            # Simulate read delay
            await asyncio.sleep(self._read_delay)
            
            # Simulate read failure if configured
            if self._simulate_failures and random.random() < self._failure_rate:
                self.logger.warning(f"Simulating read failure for {self.sensor_id}")
                raise SensorReadError("Simulated read failure")
            
            # Generate simulated value
            raw_value = self._generate_reading()
            
            # Apply calibration
            calibrated_value = self.apply_calibration(raw_value)
            
            # Create reading result
            now = datetime.now(timezone.utc)
            result = {
                "value": calibrated_value,
                "raw_value": raw_value,
                "timestamp": now
            }
            
            # Update sensor state
            self._last_reading = result
            self._last_read_time = now
            self.update_status(True)
            
            return result
            
        except SensorReadError:
            self.update_status(False, "Read failure")
            raise
        except Exception as e:
            self.update_status(False, str(e))
            raise SensorReadError(f"Unexpected error in dummy sensor read: {str(e)}")

    async def calibrate(self) -> Dict[str, Any]:
        """Simulate sensor calibration."""
        if not self._initialized:
            raise SensorNotInitializedError(f"Dummy sensor {self.sensor_id} not initialized")
        
        # Simulate calibration delay
        await asyncio.sleep(1.0)
        
        # Simulate calibration failure if configured
        if self._simulate_failures and random.random() < self._failure_rate:
            raise SensorCalibrationError("Simulated calibration failure")
        
        # Create calibration result
        calibration_result = {
            "status": "success",
            "method": self.calibration_config.get("method", "linear"),
            "timestamp": datetime.now(timezone.utc)
        }
        
        # Add method-specific parameters to result
        method = self.calibration_config.get("method", "linear")
        if method == "offset":
            calibration_result["offset"] = self.calibration_config.get("offset", 0.0)
        elif method == "scale":
            calibration_result["scale"] = self.calibration_config.get("scale", 1.0)
        elif method == "linear":
            calibration_result["scale"] = self.calibration_config.get("scale", 1.0)
            calibration_result["offset"] = self.calibration_config.get("offset", 0.0)
        
        return calibration_result

    async def validate(self) -> Tuple[bool, Optional[str]]:
        """Simulate sensor validation."""
        if not self._initialized:
            return False, "Sensor not initialized"
        
        # Simulate validation failure if configured
        if self._simulate_failures and random.random() < self._failure_rate:
            return False, "Simulated validation failure"
        
        return True, None

    async def cleanup(self) -> None:
        """Simulate sensor cleanup."""
        # Simulate cleanup delay
        await asyncio.sleep(0.3)
        self._initialized = False
        self._status = "not_initialized"
        self.logger.debug(f"Cleaned up dummy sensor {self.sensor_id}")

    def _generate_reading(self) -> float:
        """
        Generate a simulated sensor reading.
        
        This base implementation creates values that follow realistic patterns:
        - Short-term noise (random fluctuations)
        - Medium-term drift (gradual changes over minutes/hours)
        - Long-term patterns (day/night cycles, etc.)
        - Continuity with previous readings
        
        Returns:
            float: The simulated sensor reading
        """
        # Get time factors for patterns
        elapsed_seconds = time.time() - self._creation_time
        
        # Base value
        value = self._base_value
        
        # Add short-term noise
        noise = random.uniform(-self._noise_level, self._noise_level)
        value += noise
        
        # Add medium-term drift (changes slowly over time)
        drift = math.sin(elapsed_seconds / 3600) * self._drift_factor
        value += drift
        
        # Add daily pattern (24-hour cycle)
        hour_of_day = (datetime.now().hour + datetime.now().minute / 60)
        daily_factor = math.sin((hour_of_day - 6) * math.pi / 12)  # Peak at noon, low at midnight
        value += daily_factor * self._seasonal_factor
        
        # Ensure continuity with last reading if available
        if self._last_value is not None:
            # Limit how much the value can change from last reading
            max_change = self._noise_level * 2
            if abs(value - self._last_value) > max_change:
                value = self._last_value + max_change * (1 if value > self._last_value else -1)
        
        self._last_value = value
        return value


class DummyTemperatureSensor(DummySensorBase):
    """
    Mock implementation of a temperature sensor.
    
    This class simulates temperature readings with realistic daily patterns
    and gradual changes.
    """
    
    def __init__(
        self,
        sensor_id: str,
        interface_config: Dict[str, Any],
        calibration_config: Dict[str, Any]
    ) -> None:
        """Initialize temperature sensor simulation."""
        # Set defaults for temperature sensor
        if "simulation" not in interface_config:
            interface_config["simulation"] = {}
        if "base_value" not in interface_config["simulation"]:
            interface_config["simulation"]["base_value"] = 22.5  # Average room temperature
        if "noise_level" not in interface_config["simulation"]:
            interface_config["simulation"]["noise_level"] = 0.2  # Small temperature fluctuations
        if "seasonal_factor" not in interface_config["simulation"]:
            interface_config["simulation"]["seasonal_factor"] = 3.0  # Bigger day/night difference
            
        super().__init__(sensor_id, interface_config, calibration_config)

    async def read(self) -> Dict[str, Any]:
        """Read temperature with appropriate units."""
        reading = await super().read()
        reading["unit"] = "celsius"
        reading["temperature"] = reading["value"]  # Add named field
        return reading


class DummyHumiditySensor(DummySensorBase):
    """
    Mock implementation of a humidity sensor.
    
    This class simulates humidity readings with an inverse correlation
    to temperature (higher temps = lower humidity).
    """
    
    def __init__(
        self,
        sensor_id: str,
        interface_config: Dict[str, Any],
        calibration_config: Dict[str, Any]
    ) -> None:
        """Initialize humidity sensor simulation."""
        # Set defaults for humidity sensor
        if "simulation" not in interface_config:
            interface_config["simulation"] = {}
        if "base_value" not in interface_config["simulation"]:
            interface_config["simulation"]["base_value"] = 45.0  # Average humidity
        if "noise_level" not in interface_config["simulation"]:
            interface_config["simulation"]["noise_level"] = 1.5  # Fluctuations
        if "seasonal_factor" not in interface_config["simulation"]:
            interface_config["simulation"]["seasonal_factor"] = 5.0  # Bigger day/night difference
            
        super().__init__(sensor_id, interface_config, calibration_config)

    async def read(self) -> Dict[str, Any]:
        """Read humidity with inverse correlation to temperature."""
        reading = await super().read()
        reading["unit"] = "percent"
        
        # Apply constraints for realistic humidity (0-100%)
        if reading["value"] < 0:
            reading["value"] = 0
        elif reading["value"] > 100:
            reading["value"] = 100
            
        reading["humidity"] = reading["value"]  # Add named field
        return reading


class DummyWeightSensor(DummySensorBase):
    """
    Mock implementation of a weight/scale sensor.
    
    This class simulates weight readings with very small natural variations
    and occasional larger changes (simulating hive activity).
    """
    
    def __init__(
        self,
        sensor_id: str,
        interface_config: Dict[str, Any],
        calibration_config: Dict[str, Any]
    ) -> None:
        """Initialize weight sensor simulation."""
        # Set defaults for weight sensor
        if "simulation" not in interface_config:
            interface_config["simulation"] = {}
        if "base_value" not in interface_config["simulation"]:
            interface_config["simulation"]["base_value"] = 25000.0  # 25kg base weight
        if "noise_level" not in interface_config["simulation"]:
            interface_config["simulation"]["noise_level"] = 5.0  # Small weight fluctuations
        if "drift_factor" not in interface_config["simulation"]:
            interface_config["simulation"]["drift_factor"] = 0.02  # Very small drift
            
        super().__init__(sensor_id, interface_config, calibration_config)
        
        # Weight-specific simulation parameters
        self._hive_activity_chance = interface_config.get("simulation", {}).get("activity_chance", 0.02)
        self._activity_magnitude = interface_config.get("simulation", {}).get("activity_magnitude", 100.0)
        self._daily_weight_change = interface_config.get("simulation", {}).get("daily_change", 15.0)
        self._days_elapsed = 0

    def _generate_reading(self) -> float:
        """
        Generate a simulated weight reading.
        
        In addition to normal variations, this adds:
        - Small daily weight increases (honey production)
        - Occasional activity spikes (bee activity, inspection)
        
        Returns:
            float: Simulated weight value
        """
        # Get base reading with normal patterns
        value = super()._generate_reading()
        
        # Add slow daily weight change (honey production/consumption)
        # Calculate days elapsed since creation (for weight progression)
        current_days = int((time.time() - self._creation_time) / 86400)
        if current_days > self._days_elapsed:
            # Add weight for each new day passed
            days_difference = current_days - self._days_elapsed
            value += self._daily_weight_change * days_difference
            self._days_elapsed = current_days
        
        # Simulate occasional hive activity (inspection, bee activity)
        if random.random() < self._hive_activity_chance:
            activity = random.choice([-1, 1]) * random.uniform(0, self._activity_magnitude)
            value += activity
            self.logger.debug(f"Simulated hive activity: {activity}g weight change")
            
        return value

    async def read(self) -> Dict[str, Any]:
        """Read weight with grams unit."""
        reading = await super().read()
        reading["unit"] = "grams"
        reading["weight"] = reading["value"]  # Add named field
        return reading


class DummyPressureSensor(DummySensorBase):
    """
    Mock implementation of a barometric pressure sensor.
    
    This class simulates atmospheric pressure readings with weather-like
    patterns and gradual changes.
    """
    
    def __init__(
        self,
        sensor_id: str,
        interface_config: Dict[str, Any],
        calibration_config: Dict[str, Any]
    ) -> None:
        """Initialize pressure sensor simulation."""
        # Set defaults for pressure sensor
        if "simulation" not in interface_config:
            interface_config["simulation"] = {}
        if "base_value" not in interface_config["simulation"]:
            interface_config["simulation"]["base_value"] = 1013.25  # Standard atmosphere in hPa
        if "noise_level" not in interface_config["simulation"]:
            interface_config["simulation"]["noise_level"] = 0.5  # Small fluctuations
        if "drift_factor" not in interface_config["simulation"]:
            interface_config["simulation"]["drift_factor"] = 2.0  # Weather pattern changes
            
        super().__init__(sensor_id, interface_config, calibration_config)

    async def read(self) -> Dict[str, Any]:
        """Read pressure with hPa unit."""
        reading = await super().read()
        reading["unit"] = "hPa"
        reading["pressure"] = reading["value"]  # Add named field
        return reading


class DummyLightSensor(DummySensorBase):
    """
    Mock implementation of a light intensity sensor.
    
    This class simulates light readings with strong day/night cycles.
    """
    
    def __init__(
        self,
        sensor_id: str,
        interface_config: Dict[str, Any],
        calibration_config: Dict[str, Any]
    ) -> None:
        """Initialize light sensor simulation."""
        # Set defaults for light sensor
        if "simulation" not in interface_config:
            interface_config["simulation"] = {}
        if "base_value" not in interface_config["simulation"]:
            interface_config["simulation"]["base_value"] = 10000.0  # Daylight in lux
        if "noise_level" not in interface_config["simulation"]:
            interface_config["simulation"]["noise_level"] = 100.0  # Light fluctuations
        if "seasonal_factor" not in interface_config["simulation"]:
            interface_config["simulation"]["seasonal_factor"] = 10000.0  # Strong day/night cycle
            
        super().__init__(sensor_id, interface_config, calibration_config)

    def _generate_reading(self) -> float:
        """
        Generate a light reading with realistic day/night pattern.
        
        Returns:
            float: Simulated light value
        """
        # Check if it's night (10 PM to 6 AM)
        hour = datetime.now().hour
        is_night = hour < 6 or hour >= 22
        
        if is_night:
            # Generate night reading (very low, moonlight-level)
            value = random.uniform(0, 10)
        else:
            # Generate daytime reading with normal pattern
            value = super()._generate_reading()
            
            # If cloudy (random chance), reduce light level
            if random.random() < 0.2:  # 20% chance of cloud
                value *= random.uniform(0.3, 0.7)  # 30-70% reduction
        
        return max(0, value)  # Light can't be negative

    async def read(self) -> Dict[str, Any]:
        """Read light with lux unit."""
        reading = await super().read()
        reading["unit"] = "lux"
        reading["light"] = reading["value"]  # Add named field
        return reading


class DummyWindSensor(DummySensorBase):
    """
    Mock implementation of a wind sensor.
    
    This class simulates wind speed readings with gusts and calm periods.
    """
    
    def __init__(
        self,
        sensor_id: str,
        interface_config: Dict[str, Any],
        calibration_config: Dict[str, Any]
    ) -> None:
        """Initialize wind sensor simulation."""
        # Set defaults for wind sensor
        if "simulation" not in interface_config:
            interface_config["simulation"] = {}
        if "base_value" not in interface_config["simulation"]:
            interface_config["simulation"]["base_value"] = 2.5  # Light breeze in m/s
        if "noise_level" not in interface_config["simulation"]:
            interface_config["simulation"]["noise_level"] = 1.0  # Wind variations
            
        super().__init__(sensor_id, interface_config, calibration_config)
        
        # Wind-specific parameters
        self._gust_chance = interface_config.get("simulation", {}).get("gust_chance", 0.05)
        self._gust_magnitude = interface_config.get("simulation", {}).get("gust_magnitude", 5.0)
        self._direction = random.uniform(0, 360)  # Random initial wind direction
        self._direction_change_rate = interface_config.get("simulation", {}).get("direction_change", 15.0)

    def _generate_reading(self) -> float:
        """
        Generate a simulated wind speed reading with gusts.
        
        Returns:
            float: Wind speed in m/s
        """
        # Get base value
        value = super()._generate_reading()
        
        # Add occasional gusts
        if random.random() < self._gust_chance:
            value += random.uniform(0, self._gust_magnitude)
            self.logger.debug(f"Simulated wind gust: {value:.1f} m/s")
        
        # Wind can't be negative
        return max(0, value)

    async def read(self) -> Dict[str, Any]:
        """Read wind with speed and direction."""
        reading = await super().read()
        reading["unit"] = "m/s"
        reading["wind_speed"] = reading["value"]
        
        # Update simulated wind direction (slowly changes over time)
        self._direction += random.uniform(-self._direction_change_rate, self._direction_change_rate)
        self._direction = self._direction % 360  # Keep in 0-360 range
        
        # Add direction to reading
        reading["wind_direction"] = self._direction
        reading["wind_direction_unit"] = "degrees"
        
        return reading


class DummyRainSensor(DummySensorBase):
    """
    Mock implementation of a rain sensor.
    
    This class simulates rainfall with occasional rain events.
    """
    
    def __init__(
        self,
        sensor_id: str,
        interface_config: Dict[str, Any],
        calibration_config: Dict[str, Any]
    ) -> None:
        """Initialize rain sensor simulation."""
        # Set defaults for rain sensor
        if "simulation" not in interface_config:
            interface_config["simulation"] = {}
        if "base_value" not in interface_config["simulation"]:
            interface_config["simulation"]["base_value"] = 0.0  # Default is no rain
        if "noise_level" not in interface_config["simulation"]:
            interface_config["simulation"]["noise_level"] = 0.1  # Small variations
            
        super().__init__(sensor_id, interface_config, calibration_config)
        
        # Rain-specific simulation parameters
        self._rain_chance = interface_config.get("simulation", {}).get("rain_chance", 0.1)
        self._rain_duration = interface_config.get("simulation", {}).get("rain_duration", 3600)  # Duration in seconds
        self._rain_amount = interface_config.get("simulation", {}).get("rain_amount", 5.0)  # mm/hour
        
        self._is_raining = False
        self._rain_start_time = 0
        self._rain_intensity = 0.0

    def _generate_reading(self) -> float:
        """
        Generate a simulated rainfall reading with occasional rain events.
        
        Returns:
            float: Rainfall in mm
        """
        current_time = time.time()
        
        # Check if we should start/stop raining
        if not self._is_raining:
            if random.random() < self._rain_chance / 3600:  # Convert to per-second chance
                # Start a rain event
                self._is_raining = True
                self._rain_start_time = current_time
                self._rain_intensity = random.uniform(0.5, self._rain_amount)
                self.logger.info(f"Simulated rain event started: {self._rain_intensity:.1f} mm/h")
        else:
            # Check if rain event should end
            rain_elapsed = current_time - self._rain_start_time
            if rain_elapsed > self._rain_duration:
                self._is_raining = False
                self.logger.info("Simulated rain event ended")
        
        # Generate reading based on rain state
        if self._is_raining:
            # Convert mm/hour to mm for this specific reading interval
            # Assume read interval is around 60 seconds for this calculation
            reading_interval_hours = 1/60.0
            rain_amount = self._rain_intensity * reading_interval_hours
            
            # Add some variation
            rain_amount *= random.uniform(0.8, 1.2)
            
            return rain_amount
        else:
            return 0.0

    async def read(self) -> Dict[str, Any]:
        """Read rainfall with mm unit."""
        reading = await super().read()
        reading["unit"] = "mm"
        reading["rainfall"] = reading["value"]  # Add named field
        
        # Add additional information
        reading["is_raining"] = self._is_raining
        if self._is_raining:
            reading["rain_intensity"] = self._rain_intensity
            reading["rain_intensity_unit"] = "mm/h"
            
        return reading


class DummyDustSensor(DummySensorBase):
    """
    Mock implementation of a fine dust sensor (PM2.5/PM10).
    
    This class simulates particulate matter readings with patterns
    affected by time of day and simulated weather.
    """
    
    def __init__(
        self,
        sensor_id: str,
        interface_config: Dict[str, Any],
        calibration_config: Dict[str, Any]
    ) -> None:
        """Initialize dust sensor simulation."""
        # Set defaults for dust sensor
        if "simulation" not in interface_config:
            interface_config["simulation"] = {}
        if "base_value" not in interface_config["simulation"]:
            interface_config["simulation"]["base_value"] = 10.0  # Average PM2.5 in μg/m³
        if "noise_level" not in interface_config["simulation"]:
            interface_config["simulation"]["noise_level"] = 2.0  # Fluctuations
            
        super().__init__(sensor_id, interface_config, calibration_config)

    async def read(self) -> Dict[str, Any]:
        """Read particulate matter with μg/m³ unit."""
        reading = await super().read()
        reading["unit"] = "μg/m³"
        
        # Ensure non-negative
        reading["value"] = max(0, reading["value"])
        
        # Calculate PM10 (typically higher than PM2.5)
        pm25 = reading["value"]
        pm10 = pm25 * random.uniform(1.5, 2.5)
        
        # Add named fields
        reading["pm25"] = pm25
        reading["pm10"] = pm10
        reading["pm10_unit"] = "μg/m³"
        
        return reading


class DummySoundSensor(DummySensorBase):
    """
    Mock implementation of a sound sensor.
    
    This class simulates sound level readings with daily patterns
    and occasional disturbances.
    """
    
    def __init__(
        self,
        sensor_id: str,
        interface_config: Dict[str, Any],
        calibration_config: Dict[str, Any]
    ) -> None:
        """Initialize sound sensor simulation."""
        # Set defaults for sound sensor
        if "simulation" not in interface_config:
            interface_config["simulation"] = {}
        if "base_value" not in interface_config["simulation"]:
            interface_config["simulation"]["base_value"] = 35.0  # Quiet ambient in dB
        if "noise_level" not in interface_config["simulation"]:
            interface_config["simulation"]["noise_level"] = 3.0  # Normal variations
            
        super().__init__(sensor_id, interface_config, calibration_config)
        
        # Sound-specific simulation parameters
        self._disturbance_chance = interface_config.get("simulation", {}).get("disturbance_chance", 0.02)
        self._disturbance_magnitude = interface_config.get("simulation", {}).get("disturbance_magnitude", 15.0)
        self._bee_activity_level = random.uniform(0.5, 1.5)  # Simulated colony activity factor

    def _generate_reading(self) -> float:
        """
        Generate a simulated sound level reading.
        
        Returns:
            float: Sound level in dB
        """
        # Get base reading with normal patterns
        value = super()._generate_reading()
        
        # Higher sound level during the day
        hour = datetime.now().hour
        if 8 <= hour <= 18:  # Daytime = more activity
            value += 5 * self._bee_activity_level
        
        # Add occasional disturbances
        if random.random() < self._disturbance_chance:
            value += random.uniform(5, self._disturbance_magnitude)
            self.logger.debug(f"Simulated sound disturbance: {value:.1f} dB")
            
        return value

    async def read(self) -> Dict[str, Any]:
        """Read sound level with dB unit."""
        reading = await super().read()
        reading["unit"] = "dB"
        reading["sound_level"] = reading["value"]  # Add named field
        
        # Add frequency characteristics (simulated)
        reading["frequency_peak"] = random.uniform(200, 500)  # Main bee frequency range
        reading["frequency_peak_unit"] = "Hz"
        
        return reading
