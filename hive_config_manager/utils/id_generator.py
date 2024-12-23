# hive_config_manager/utils/id_generator.py

import random
import string
import time
from typing import Optional

def generate_hive_id(prefix: str = "hive", length: int = 8) -> str:
    """
    Generate a unique hive identifier.
    
    Args:
        prefix: Prefix for the ID (default: "hive")
        length: Length of the random part (default: 8)
        
    Returns:
        A unique identifier string
        
    Example:
        >>> generate_hive_id()
        'hive_x7k9m2p4'
    """
    # Characters to use for ID generation (excluding similar-looking characters)
    chars = string.ascii_lowercase + string.digits
    chars = chars.replace('l', '').replace('1', '').replace('o', '').replace('0', '')
    
    # Generate random part
    random_part = ''.join(random.choice(chars) for _ in range(length))
    
    return f"{prefix}_{random_part}"

def generate_sensor_id(sensor_type: str, index: Optional[int] = None) -> str:
    """
    Generate a sensor identifier.
    
    Args:
        sensor_type: Type of sensor (e.g., 'temp', 'humid')
        index: Optional numeric index
        
    Returns:
        A sensor identifier string
        
    Example:
        >>> generate_sensor_id('temp', 1)
        'temp_01'
    """
    if index is not None:
        return f"{sensor_type}_{index:02d}"
    
    # Generate random part if no index provided
    random_part = ''.join(random.choice(string.digits) for _ in range(2))
    return f"{sensor_type}_{random_part}"

def is_valid_hive_id(hive_id: str) -> bool:
    """
    Validate a hive identifier format.
    
    Args:
        hive_id: The identifier to validate
        
    Returns:
        True if valid, False otherwise
    """
    import re
    pattern = r'^hive_[a-z0-9]{8}$'
    return bool(re.match(pattern, hive_id))

def is_valid_sensor_id(sensor_id: str) -> bool:
    """
    Validate a sensor identifier format.
    
    Args:
        sensor_id: The identifier to validate
        
    Returns:
        True if valid, False otherwise
    """
    import re
    pattern = r'^[a-z]+_\d{2}$'
    return bool(re.match(pattern, sensor_id))

class IdGenerator:
    """
    Thread-safe ID generator with memory of recently used IDs.
    """
    
    def __init__(self, prefix: str = "hive", max_memory: int = 1000):
        """
        Initialize the generator.
        
        Args:
            prefix: Prefix for generated IDs
            max_memory: Maximum number of recent IDs to remember
        """
        self.prefix = prefix
        self.max_memory = max_memory
        self.recent_ids = set()
        self._lock = None  # Initialize lock on first use
        
    @property
    def lock(self):
        """Lazy initialization of threading lock"""
        if self._lock is None:
            import threading
            self._lock = threading.Lock()
        return self._lock
    
    def generate_id(self, length: int = 8) -> str:
        """
        Generate a unique ID, ensuring no recent duplicates.
        
        Args:
            length: Length of the random part
            
        Returns:
            A unique identifier string
        """
        with self.lock:
            while True:
                new_id = generate_hive_id(self.prefix, length)
                if new_id not in self.recent_ids:
                    self.recent_ids.add(new_id)
                    if len(self.recent_ids) > self.max_memory:
                        self.recent_ids.pop()
                    return new_id
    
    def clear_memory(self):
        """Clear the memory of recent IDs"""
        with self.lock:
            self.recent_ids.clear()

# Create a default instance for general use
default_generator = IdGenerator()