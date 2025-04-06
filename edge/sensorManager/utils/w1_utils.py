#!/usr/bin/env python3
"""
Utility functions for working with 1-Wire sensors.

This module provides functions for discovering, validating, and interacting
with 1-Wire devices, particularly temperature sensors like DS18B20.
"""

import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Standard 1-Wire device path on Linux systems
W1_DEVICES_PATH = "/sys/bus/w1/devices"
# Family code for DS18B20 sensors is 28
DS18B20_PREFIX = "28-"

logger = logging.getLogger("sensors.w1")


def is_w1_available() -> bool:
    """
    Check if the 1-Wire subsystem is available on this system.
    
    Returns:
        bool: True if the 1-Wire bus is available, False otherwise.
    """
    return os.path.exists(W1_DEVICES_PATH)


def list_w1_devices(
    device_type: Optional[str] = None,
    base_path: str = W1_DEVICES_PATH
) -> List[str]:
    """
    List available 1-Wire devices.
    
    Args:
        device_type: Optional filter for specific device families (e.g., "28-" for DS18B20)
        base_path: Path to the 1-Wire devices directory
        
    Returns:
        List of device IDs (the full device ID including family code)
    """
    if not os.path.exists(base_path):
        logger.warning(f"1-Wire bus path {base_path} does not exist")
        return []
        
    try:
        devices = []
        for item in os.listdir(base_path):
            # Skip w1_bus_master device
            if item.startswith("w1_bus_master"):
                continue
                
            # Apply device type filter if specified
            if device_type and not item.startswith(device_type):
                continue
                
            devices.append(item)
            
        return devices
    except (PermissionError, FileNotFoundError) as e:
        logger.error(f"Error accessing 1-Wire bus: {e}")
        return []


def discover_temperature_sensors(
    base_path: str = W1_DEVICES_PATH
) -> List[Dict[str, str]]:
    """
    Discover DS18B20 temperature sensors on the 1-Wire bus.
    
    Args:
        base_path: Path to the 1-Wire devices directory
        
    Returns:
        List of dictionaries containing sensor information:
        - id: The full device ID
        - path: Full path to the device's w1_slave file
    """
    sensors = []
    devices = list_w1_devices(DS18B20_PREFIX, base_path)
    
    for device_id in devices:
        device_path = os.path.join(base_path, device_id, "w1_slave")
        if os.path.exists(device_path):
            sensors.append({
                "id": device_id,
                "path": device_path
            })
    
    logger.info(f"Discovered {len(sensors)} temperature sensors on the 1-Wire bus")
    return sensors


def read_raw_temp(device_path: str) -> Tuple[bool, Optional[str]]:
    """
    Read raw temperature data from a 1-Wire temperature sensor.
    
    Args:
        device_path: Path to the w1_slave file for the sensor
        
    Returns:
        Tuple containing:
        - Success flag (True if read was successful)
        - Raw data string if successful, None otherwise
    """
    try:
        with open(device_path, "r") as f:
            raw_data = f.read()
        return True, raw_data
    except (PermissionError, FileNotFoundError, IOError) as e:
        logger.error(f"Error reading from {device_path}: {e}")
        return False, None


def parse_temp_data(raw_data: str) -> Tuple[bool, Optional[float]]:
    """
    Parse raw temperature data from a DS18B20 sensor.
    
    Args:
        raw_data: Raw data string from the sensor
        
    Returns:
        Tuple containing:
        - Success flag (True if CRC check passed and temp was found)
        - Temperature in Celsius if successful, None otherwise
    """
    # Check if the CRC check passed
    if "YES" not in raw_data:
        logger.warning("CRC check failed in temperature data")
        return False, None
        
    # Extract the temperature value
    match = re.search(r"t=(-?\d+)", raw_data)
    if not match:
        logger.warning("Temperature data not found in sensor output")
        return False, None
        
    # Convert to Celsius (t=12345 means 12.345°C)
    temp_c = float(match.group(1)) / 1000.0
    return True, temp_c


def read_temperature(device_path: str) -> Tuple[bool, Optional[float]]:
    """
    Read temperature from a DS18B20 sensor.
    
    Args:
        device_path: Path to the w1_slave file for the sensor
        
    Returns:
        Tuple containing:
        - Success flag (True if read was successful)
        - Temperature in Celsius if successful, None otherwise
    """
    success, raw_data = read_raw_temp(device_path)
    if not success:
        return False, None
        
    return parse_temp_data(raw_data)


def validate_sensor(device_path: str) -> Tuple[bool, Optional[str]]:
    """
    Validate that a temperature sensor is working correctly.
    
    Args:
        device_path: Path to the w1_slave file for the sensor
        
    Returns:
        Tuple containing:
        - Validation success flag
        - Error message if validation failed, None otherwise
    """
    # Check if the device file exists
    if not os.path.exists(device_path):
        return False, f"Device path does not exist: {device_path}"
        
    # Try to read the temperature
    success, temp = read_temperature(device_path)
    if not success:
        return False, "Failed to read temperature from sensor"
        
    # Basic sanity check for reasonable temperature values
    if temp is not None and (temp < -55.0 or temp > 125.0):
        return False, f"Temperature reading out of range: {temp}°C"
        
    return True, None
