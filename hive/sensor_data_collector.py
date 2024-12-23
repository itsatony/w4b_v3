#!/usr/bin/env python3
"""
Hive Sensor Data Collection Script
Version: 1.0.0
"""

import asyncio
import logging
import yaml
import sys
import os
from datetime import datetime, timezone
from typing import Dict, List, Any
from pathlib import Path

import asyncpg
from prometheus_client import start_http_server, Gauge, Counter
import importlib

class SensorManager:
    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.sensors = {}
        self.metrics = {}
        self.db_pool = None
        self._setup_logging()
        self._setup_metrics()

    def _load_config(self, path: str) -> dict:
        with open(path, 'r') as f:
            config = yaml.safe_load(f)
        return config

    def _setup_logging(self):
        logging.config.dictConfig(self.config['logging'])
        self.logger = logging.getLogger('sensors')

    def _setup_metrics(self):
        if self.config['metrics']['prometheus']['enabled']:
            # System metrics
            self.metrics['system_health'] = Gauge(
                'hive_system_health',
                'Overall system health status',
                ['hive_id', 'component']
            )
            
            # Sensor metrics
            self.metrics['sensor_status'] = Gauge(
                'hive_sensor_status',
                'Sensor operational status',
                ['hive_id', 'sensor_id', 'sensor_type']
            )
            
            # Collection metrics
            self.metrics['collection_errors'] = Counter(
                'hive_collection_errors_total',
                'Total number of collection errors',
                ['hive_id', 'sensor_id', 'error_type']
            )

            # Start Prometheus HTTP server
            start_http_server(
                self.config['metrics']['prometheus']['port']
            )

    async def initialize(self):
        """Initialize database connection and load sensors"""
        # Setup database connection pool
        self.db_pool = await asyncpg.create_pool(
            host=self.config['storage']['host'],
            port=self.config['storage']['port'],
            database=self.config['storage']['database'],
            user=self.config['storage']['user'],
            password=self.config['storage']['password']
        )

        # Initialize sensors
        for sensor_config in self.config['sensors']:
            if sensor_config['enabled']:
                await self._initialize_sensor(sensor_config)

    async def _initialize_sensor(self, sensor_config: Dict[str, Any]):
        """Initialize individual sensor based on configuration"""
        sensor_type = sensor_config['type']
        type_config = self.config['sensor_types'][sensor_type]

        try:
            # Dynamically import sensor module
            module = importlib.import_module(type_config['module'])
            sensor_class = getattr(module, type_config['class'])

            # Initialize sensor instance
            sensor = sensor_class(
                sensor_config['id'],
                sensor_config['interface'],
                sensor_config['calibration']
            )

            self.sensors[sensor_config['id']] = {
                'instance': sensor,
                'config': sensor_config,
                'last_collection': None,
                'metrics': {},
                'errors': 0
            }

            # Initialize Prometheus metrics for this sensor
            if self.config['metrics']['prometheus']['enabled']:
                for metric in sensor_config['metrics']:
                    metric_name = f"hive_sensor_{sensor_config['id']}_{metric['name']}"
                    self.metrics[f"{sensor_config['id']}_{metric['name']}"] = Gauge(
                        metric_name,
                        f"{metric['name']} from sensor {sensor_config['id']}",
                        ['hive_id', 'unit']
                    )

            self.logger.info(f"Initialized sensor {sensor_config['id']} of type {sensor_type}")

        except Exception as e:
            self.logger.error(f"Failed to initialize sensor {sensor_config['id']}: {str(e)}")
            if self.config['metrics']['prometheus']['enabled']:
                self.metrics['sensor_status'].labels(
                    hive_id=self.config['hive_id'],
                    sensor_id=sensor_config['id'],
                    sensor_type=sensor_type
                ).set(0)

    async def collect_data(self):
        """Main data collection loop"""
        while True:
            collection_tasks = []
            current_time = datetime.now(timezone.utc)

            for sensor_id, sensor_data in self.sensors.items():
                if self._should_collect(sensor_data, current_time):
                    collection_tasks.append(self._collect_sensor_data(sensor_id))

            if collection_tasks:
                await asyncio.gather(*collection_tasks, return_exceptions=True)

            await asyncio.sleep(1)  # Check every second

    def _should_collect(self, sensor_data: Dict[str, Any], current_time: datetime) -> bool:
        """Determine if sensor should be collected based on interval"""
        if sensor_data['last_collection'] is None:
            return True

        interval = sensor_data['config'].get('collection', {}).get(
            'interval',
            self.config['collectors']['interval']
        )
        
        time_diff = (current_time - sensor_data['last_collection']).total_seconds()
        return time_diff >= interval

    async def _collect_sensor_data(self, sensor_id: str):
        """Collect data from a specific sensor"""
        sensor_data = self.sensors[sensor_id]
        sensor = sensor_data['instance']
        config = sensor_data['config']

        try:
            # Collect measurements
            measurements = await sensor.read()
            
            # Store in database
            async with self.db_pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO sensor_data (hive_id, sensor_id, metric_name, value, unit, timestamp)
                    VALUES ($1, $2, $3, $4, $5, $6)
                ''', self.config['hive_id'], sensor_id, measurements['name'],
                    measurements['value'], measurements['unit'], datetime.now(timezone.utc))

            # Update Prometheus metrics
            if self.config['metrics']['prometheus']['enabled']:
                for metric_name, value in measurements.items():
                    metric_key = f"{sensor_id}_{metric_name}"
                    if metric_key in self.metrics:
                        self.metrics[metric_key].labels(
                            hive_id=self.config['hive_id'],
                            unit=config['metrics'][0]['unit']
                        ).set(value)

            sensor_data['last_collection'] = datetime.now(timezone.utc)
            sensor_data['errors'] = 0

            self.metrics['sensor_status'].labels(
                hive_id=self.config['hive_id'],
                sensor_id=sensor_id,
                sensor_type=config['type']
            ).set(1)

        except Exception as e:
            self.logger.error(f"Error collecting data from sensor {sensor_id}: {str(e)}")
            sensor_data['errors'] += 1
            
            self.metrics['collection_errors'].labels(
                hive_id=self.config['hive_id'],
                sensor_id=sensor_id,
                error_type=type(e).__name__
            ).inc()

            if sensor_data['errors'] >= config.get('collection', {}).get('retries', 3):
                self.metrics['sensor_status'].labels(
                    hive_id=self.config['hive_id'],
                    sensor_id=sensor_id,
                    sensor_type=config['type']
                ).set(0)

    async def cleanup(self):
        """Cleanup connections and resources"""
        if self.db_pool:
            await self.db_pool.close()

async def main():
    if len(sys.argv) != 2:
        print("Usage: sensor_collector.py <config_path>")
        sys.exit(1)

    config_path = sys.argv[1]
    manager = SensorManager(config_path)
    
    try:
        await manager.initialize()
        await manager.collect_data()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await manager.cleanup()

if __name__ == "__main__":
    asyncio.run(main())