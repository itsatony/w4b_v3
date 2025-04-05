"""
Hive Configuration Manager
A management tool for we4bee hive configurations.
"""

# Version information
__version__ = "1.0.0"

# Make key components available at package level
from .core.manager import HiveManager
from .core.exceptions import HiveConfigError, ConfigNotFoundError, ValidationError
