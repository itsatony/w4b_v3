#!/usr/bin/env python3
"""
ID Generation Utilities for Hive Configuration
"""

import re
import nanoid
from typing import Optional

def generate_hive_id() -> str:
    """
    Generate a unique hive ID.
    
    Returns:
        A unique string in the format "hive_<nanoid>"
    """
    return f"hive_{nanoid.generate(size=8)}"

def generate_sensor_id(sensor_type: str, counter: Optional[int] = None) -> str:
    """
    Generate a sensor ID based on type and counter.
    
    Args:
        sensor_type: Type of sensor (e.g., 'temp', 'weight')
        counter: Optional counter to include in ID
        
    Returns:
        A sensor ID in the format "<type>_<counter>"
    """
    # Normalize sensor type to lowercase short form
    type_map = {
        'temperature': 'temp',
        'humidity': 'hum',
        'weight': 'weight',
        'pressure': 'press',
        'light': 'light',
        'sound': 'sound',
        'image': 'img',
        'dht22': 'temp',
        'hx711': 'weight',
        'ds18b20': 'temp'
    }
    
    # Get normalized type or use input directly
    norm_type = type_map.get(sensor_type.lower(), sensor_type.lower())
    
    # Generate ID with or without counter
    if counter is not None:
        return f"{norm_type}_{counter:02d}"
    else:
        # Use nanoid for a unique sensor ID
        return f"{norm_type}_{nanoid.generate(size=6)}"

def is_valid_hive_id(hive_id: str) -> bool:
    """
    Check if a string is a valid hive ID.
    
    Args:
        hive_id: String to check
        
    Returns:
        True if valid, False otherwise
    """
    return bool(re.match(r'^hive_[\w-]{8,}$', hive_id))

def is_valid_sensor_id(sensor_id: str) -> bool:
    """
    Check if a string is a valid sensor ID.
    
    Args:
        sensor_id: String to check
        
    Returns:
        True if valid, False otherwise
    """
    return bool(re.match(r'^[\w-]+_[\w-]+$', sensor_id))