#!/usr/bin/env python3
"""
Data collection service for the w4b sensor management system.

This module implements the main collection loop and manages sensor
reading operations, buffering, and persistence.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Set, Tuple

from sensors.base import SensorBase, SensorReadError, SensorNotInitializedError
from storage.db_connector import DatabaseManager, DatabaseError
from utils.error_handling import retry, CircuitBreaker
from utils.logging_setup import get_contextual_logger


class CollectionError(Exception):
    """Exception raised when data collection fails."""
    pass


class CollectionService:
    """
    Main service for collecting sensor data.
    
    This class manages the data collection process, including scheduling,
    buffering, and persisting sensor readings to the database.
    
    Attributes:
        hive_id (str): ID of the hive
        sensors (Dict[str, SensorBase]): Dictionary of sensor instances
        sensor_configs (Dict[str, Dict]): Sensor configuration parameters
        collection_config (Dict): Collection configuration parameters
        logger (logging.Logger): Logger instance
        running (bool): Flag indicating if collection is running
        last_collection (Dict[str, datetime]): Timestamp of last collection per sensor
        buffer (List[Dict]): Buffer for readings before database persistence
        _retry_counts (Dict[str, int]): Count of consecutive read failures per sensor
        _circuit_breakers (Dict[str, CircuitBreaker]): Circuit breaker per sensor
    """
    
    def __init__(
        self,
        hive_id: str,
        sensors: Dict[str, SensorBase],
        sensor_configs: Dict[str, Dict],
        collection_config: Dict
    ):
        """
        Initialize the collection service.
        
        Args:
            hive_id: ID of the hive
            sensors: Dictionary of sensor instances by ID
            sensor_configs: Configuration for each sensor
            collection_config: Global collection configuration
        """
        self.hive_id = hive_id
        self.sensors = sensors
        self.sensor_configs = sensor_configs
        self.collection_config = collection_config
        
        self.logger = logging.getLogger("collectors.service")
        self.running = False
        self.last_collection = {}
        self.buffer = []
        
        # Set up retry counters and circuit breakers for each sensor
        self._retry_counts = {sensor_id: 0 for sensor_id in sensors}
        self._circuit_breakers = {
            sensor_id: CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=300.0,  # 5 min recovery timeout
                name=f"sensor_{sensor_id}",
                logger=get_contextual_logger("collectors.circuit", sensor_id=sensor_id)
            )
            for sensor_id in sensors
        }
        
        # Initialize last collection times based on intervals
        now = datetime.now(timezone.utc)
        for sensor_id, config in sensor_configs.items():
            # Calculate an initial offset to stagger collections
            # This prevents all sensors from being read at once on startup
            stagger_offset = hash(sensor_id) % 60  # Max 1 minute stagger
            interval = config.get("collection", {}).get(
                "interval", collection_config.get("interval", 60)
            )
            self.last_collection[sensor_id] = now - timedelta(
                seconds=(interval - stagger_offset)
            )
    
    async def start(self) -> None:
        """
        Start the collection service.
        
        This method begins the main collection loop.
        """
        if self.running:
            self.logger.warning("Collection service is already running")
            return
            
        self.running = True
        self.logger.info(f"Starting collection service for hive {self.hive_id}")
        
        # Start collection loop as a task
        asyncio.create_task(self._collection_loop())
    
    async def stop(self) -> None:
        """
        Stop the collection service.
        
        This method stops the collection loop and flushes any buffered data.
        """
        if not self.running:
            return
            
        self.logger.info("Stopping collection service")
        self.running = False
        
        # Flush any remaining buffered data
        await self._flush_buffer()
    
    async def _collection_loop(self) -> None:
        """
        Main collection loop.
        
        This method continuously checks for sensors that need reading
        and collects data at appropriate intervals.
        """
        self.logger.info("Collection loop started")
        
        while self.running:
            try:
                # Get current time
                now = datetime.now(timezone.utc)
                
                # Find sensors that need to be collected
                sensors_to_collect = []
                
                for sensor_id, sensor in self.sensors.items():
                    # Skip if circuit breaker is open
                    if not self._circuit_breakers[sensor_id].can_execute():
                        self.logger.debug(f"Circuit breaker open for sensor {sensor_id}")
                        continue
                    
                    # Calculate time since last collection
                    last_time = self.last_collection.get(sensor_id, datetime.min.replace(tzinfo=timezone.utc))
                    elapsed = (now - last_time).total_seconds()
                    
                    # Get collection interval from config
                    interval = self.sensor_configs[sensor_id].get("collection", {}).get(
                        "interval", self.collection_config.get("interval", 60)
                    )
                    
                    # Check if collection is due
                    if elapsed >= interval:
                        sensors_to_collect.append(sensor_id)
                
                # Collect data from due sensors
                if sensors_to_collect:
                    collection_tasks = [
                        self._collect_sensor_data(sensor_id)
                        for sensor_id in sensors_to_collect
                    ]
                    # Run collections concurrently
                    await asyncio.gather(*collection_tasks, return_exceptions=True)
                    
                    # Check if buffer should be flushed
                    buffer_size = len(self.buffer)
                    batch_size = self.collection_config.get("batch_size", 50)
                    
                    if buffer_size >= batch_size:
                        await self._flush_buffer()
                
                # Sleep for a short time before checking again
                # Short sleep allows for responsive shutdown
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error in collection loop: {str(e)}")
                # Continue the loop despite errors
    
    async def _collect_sensor_data(self, sensor_id: str) -> None:
        """
        Collect data from a specific sensor.
        
        Args:
            sensor_id: ID of the sensor to collect from
        """
        sensor = self.sensors[sensor_id]
        config = self.sensor_configs[sensor_id]
        sensor_logger = get_contextual_logger(
            "collectors.sensor", 
            sensor_id=sensor_id, 
            sensor_type=config.get("type", "unknown")
        )
        
        try:
            # Use circuit breaker pattern for sensor operations
            reading = await self._circuit_breakers[sensor_id].execute(sensor.read)
            
            # Process the reading
            for metric in config.get("metrics", []):
                metric_name = metric.get("name")
                if metric_name in reading:
                    reading_value = reading[metric_name]
                    
                    # Round to specified precision if defined
                    precision = metric.get("precision")
                    if precision is not None and isinstance(reading_value, (float, int)):
                        reading_value = round(reading_value, precision)
                    
                    # Create full reading record
                    reading_record = {
                        "hive_id": self.hive_id,
                        "sensor_id": sensor_id,
                        "metric_name": metric_name,
                        "value": reading_value,
                        "unit": metric.get("unit", reading.get("unit", "unknown")),
                        "time": datetime.now(timezone.utc),
                        "status": "valid",
                        "metadata": {
                            "sensor_type": config.get("type", "unknown"),
                            "raw_value": reading.get("raw_value", None)
                        }
                    }
                    
                    # Add to buffer
                    self.buffer.append(reading_record)
                    
                    sensor_logger.debug(f"Collected {metric_name}: {reading_value} {reading_record['unit']}")
            
            # Update last collection time
            self.last_collection[sensor_id] = datetime.now(timezone.utc)
            
            # Reset retry counter
            self._retry_counts[sensor_id] = 0
            
            # Record success in circuit breaker
            self._circuit_breakers[sensor_id].success()
            
        except (SensorReadError, SensorNotInitializedError) as e:
            # Increment retry counter
            self._retry_counts[sensor_id] += 1
            retry_limit = config.get("collection", {}).get(
                "retries", self.collection_config.get("retries", 3)
            )
            
            error_msg = f"Failed to collect data from sensor {sensor_id}: {str(e)}"
            if self._retry_counts[sensor_id] >= retry_limit:
                sensor_logger.error(f"{error_msg} (reached retry limit of {retry_limit})")
            else:
                sensor_logger.warning(f"{error_msg} (attempt {self._retry_counts[sensor_id]}/{retry_limit})")
            
            # Record failure in circuit breaker
            self._circuit_breakers[sensor_id].failure()
            
        except Exception as e:
            sensor_logger.error(f"Unexpected error collecting from sensor {sensor_id}: {str(e)}")
            # Record failure in circuit breaker
            self._circuit_breakers[sensor_id].failure()
    
    async def _flush_buffer(self) -> None:
        """
        Flush buffered readings to the database.
        
        This method sends all buffered readings to the database and
        clears the buffer.
        """
        if not self.buffer:
            return
            
        try:
            # Get database connector
            db_connector = DatabaseManager.get_instance().get_connector()
            
            # Store readings in a batch
            buffer_copy = self.buffer.copy()
            self.buffer = []  # Clear buffer before DB operation to avoid data loss
            
            success_count, failure_count = await db_connector.store_readings_batch(buffer_copy)
            
            if failure_count > 0:
                self.logger.warning(
                    f"Failed to store {failure_count} of {len(buffer_copy)} readings"
                )
            else:
                self.logger.debug(f"Successfully stored {success_count} readings")
                
        except DatabaseError as e:
            self.logger.error(f"Database error when flushing buffer: {str(e)}")
            # Put readings back in the buffer for retry
            self.buffer.extend(buffer_copy)
            
        except Exception as e:
            self.logger.error(f"Unexpected error when flushing buffer: {str(e)}")
            # Put readings back in the buffer for retry
            self.buffer.extend(buffer_copy)
