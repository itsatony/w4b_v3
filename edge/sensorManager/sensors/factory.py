#!/usr/bin/env python3
"""
Sensor factory and registry for the w4b sensor management system.

This module provides factory and registry patterns for dynamically creating
and tracking sensor instances based on their type.
"""

import importlib
import logging
from typing import Dict, Any, Type, Optional, List

from sensors.base import SensorBase, SensorInitializationError


class SensorRegistry:
    """
    Registry of available sensor types and their implementations.
    
    This class maintains a mapping between sensor type names and their
    implementation classes, allowing for dynamic sensor instantiation.
    """
    
    def __init__(self):
        """Initialize an empty sensor registry."""
        self._sensors = {}  # type: Dict[str, Type[SensorBase]]
        self.logger = logging.getLogger('sensors.registry')
        
    def register(self, sensor_type: str, sensor_class: Type[SensorBase]) -> None:
        """
        Register a sensor implementation class for a specific sensor type.
        
        Args:
            sensor_type: The type name for this sensor (e.g., 'dht22').
            sensor_class: The implementation class that inherits from SensorBase.
            
        Raises:
            TypeError: If sensor_class is not a subclass of SensorBase.
        """
        if not issubclass(sensor_class, SensorBase):
            raise TypeError(f"Sensor class must inherit from SensorBase: {sensor_class}")
            
        self._sensors[sensor_type] = sensor_class
        self.logger.debug(f"Registered sensor type '{sensor_type}'")
        
    def get_class(self, sensor_type: str) -> Optional[Type[SensorBase]]:
        """
        Get the implementation class for a sensor type.
        
        Args:
            sensor_type: The type name of the sensor.
            
        Returns:
            The sensor implementation class, or None if not registered.
        """
        return self._sensors.get(sensor_type)
        
    def list_types(self) -> List[str]:
        """
        Get a list of all registered sensor types.
        
        Returns:
            List of registered sensor type names.
        """
        return list(self._sensors.keys())


class SensorFactory:
    """
    Factory for creating sensor instances based on configuration.
    
    This class uses the SensorRegistry to instantiate appropriate sensor
    classes based on their type as specified in configuration.
    """
    
    def __init__(self, registry: SensorRegistry):
        """
        Initialize the sensor factory.
        
        Args:
            registry: The sensor registry to use for sensor creation.
        """
        self.registry = registry
        self.logger = logging.getLogger('sensors.factory')
        
    async def create_sensor(
        self,
        sensor_config: Dict[str, Any],
        sensor_type_config: Dict[str, Any]
    ) -> Optional[SensorBase]:
        """
        Create and initialize a sensor instance based on configuration.
        
        Args:
            sensor_config: Configuration for this specific sensor instance.
            sensor_type_config: Type-specific configuration for this sensor class.
            
        Returns:
            An initialized sensor instance, or None if creation fails.
            
        Raises:
            SensorInitializationError: If the sensor type is not registered or
                cannot be instantiated.
        """
        sensor_type = sensor_config.get('type')
        sensor_id = sensor_config.get('id')
        
        try:
            # Check if type is registered
            sensor_class = self.registry.get_class(sensor_type)
            
            if not sensor_class:
                # Try dynamic import if sensor class is not registered but specified in config
                if 'module' in sensor_type_config and 'class' in sensor_type_config:
                    module_name = sensor_type_config['module']
                    class_name = sensor_type_config['class']
                    
                    try:
                        module = importlib.import_module(module_name)
                        sensor_class = getattr(module, class_name)
                        self.registry.register(sensor_type, sensor_class)
                    except (ImportError, AttributeError) as e:
                        raise SensorInitializationError(
                            f"Failed to import sensor class: {e}"
                        )
                else:
                    raise SensorInitializationError(
                        f"Sensor type '{sensor_type}' is not registered"
                    )
            
            # Create the sensor instance
            sensor = sensor_class(
                sensor_id=sensor_id,
                interface_config=sensor_config.get('interface', {}),
                calibration_config=sensor_config.get('calibration', {})
            )
            
            # Initialize the sensor
            await sensor.initialize()
            self.logger.info(f"Initialized sensor: {sensor_id} (type: {sensor_type})")
            
            return sensor
            
        except Exception as e:
            self.logger.error(f"Failed to create sensor {sensor_id}: {e}")
            raise SensorInitializationError(f"Failed to create sensor {sensor_id}: {e}")
        
    async def create_sensors_from_config(
        self,
        sensors_config: List[Dict[str, Any]],
        sensor_types_config: Dict[str, Dict[str, Any]]
    ) -> Dict[str, SensorBase]:
        """
        Create multiple sensors from configuration.
        
        Args:
            sensors_config: List of sensor instance configurations.
            sensor_types_config: Dictionary of sensor type configurations.
            
        Returns:
            Dictionary mapping sensor IDs to initialized sensor instances.
        """
        sensors = {}
        
        for sensor_config in sensors_config:
            if not sensor_config.get('enabled', True):
                self.logger.debug(f"Skipping disabled sensor: {sensor_config.get('id')}")
                continue
                
            sensor_type = sensor_config.get('type')
            sensor_type_config = sensor_types_config.get(sensor_type, {})
            
            try:
                sensor = await self.create_sensor(sensor_config, sensor_type_config)
                if sensor:
                    sensors[sensor_config['id']] = sensor
            except SensorInitializationError as e:
                self.logger.error(f"Initialization error: {e}")
        
        return sensors
