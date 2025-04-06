#!/usr/bin/env python3
"""
Main entry point for the w4b sensor management system.

This script initializes the sensor management system, loads the configuration,
discovers and initializes sensors, and starts the data collection process.
"""

import os
import sys
import asyncio
import argparse
import logging
import logging.config
import signal
from datetime import datetime, timezone
from pathlib import Path

import yaml
from prometheus_client import start_http_server

from config.config_manager import ConfigManager, ConfigurationError
from sensors.factory import SensorRegistry, SensorFactory
from utils.logging_setup import configure_logging, get_logger
from utils.error_handling import handle_critical_error


# Global variables for cleanup handling
sensor_factory = None
running = True


async def shutdown(sig, loop):
    """
    Handle graceful shutdown on signals.
    
    Args:
        sig: Signal number
        loop: Event loop
    """
    global running
    logger = get_logger('main')
    
    logger.info(f"Received shutdown signal {sig.name}...")
    running = False
    
    # Wait for any pending tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    
    if tasks:
        logger.info(f"Waiting for {len(tasks)} active tasks to complete...")
        await asyncio.gather(*tasks, return_exceptions=True)
        
    loop.stop()


async def initialize_system(config_path: str) -> bool:
    """
    Initialize the sensor management system.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        bool: True if initialization succeeded, False otherwise
    """
    global sensor_factory
    logger = get_logger('main')
    
    try:
        # Load configuration
        logger.info(f"Loading configuration from {config_path}")
        config_manager = ConfigManager(config_path)
        
        # Configure logging from config
        configure_logging(config_manager.config)
        
        # Set up Prometheus metrics if enabled
        if config_manager.get('metrics.prometheus.enabled', False):
            prometheus_port = config_manager.get('metrics.prometheus.port', 9100)
            logger.info(f"Starting Prometheus metrics server on port {prometheus_port}")
            start_http_server(prometheus_port)
        
        # Initialize sensor registry and factory
        registry = SensorRegistry()
        sensor_factory = SensorFactory(registry)
        
        # Get sensor configurations
        enabled_sensors = config_manager.get_all_enabled_sensors()
        sensor_types = config_manager.get('sensor_types', {})
        
        # Create and initialize sensors
        logger.info(f"Initializing {len(enabled_sensors)} sensors")
        sensors = await sensor_factory.create_sensors_from_config(
            enabled_sensors,
            sensor_types
        )
        
        if not sensors:
            logger.warning("No enabled sensors were successfully initialized")
            return False
            
        logger.info(f"Successfully initialized {len(sensors)} sensors")
        return True
    
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        return False
    except Exception as e:
        logger.exception(f"Error during initialization: {e}")
        return False


async def run_collection_loop():
    """
    Main data collection loop.
    
    This function runs the continuous collection loop until a shutdown
    signal is received.
    """
    global running
    logger = get_logger('main')
    
    logger.info("Starting sensor data collection loop")
    
    try:
        # TODO: Implement actual collection loop
        # For now, just keep the process running
        while running:
            # Process collection here
            await asyncio.sleep(1)
    
    except asyncio.CancelledError:
        logger.info("Collection loop cancelled")
    except Exception as e:
        logger.exception(f"Error in collection loop: {e}")
        running = False


async def cleanup_system():
    """
    Perform system cleanup before shutdown.
    
    This function ensures all resources are properly released.
    """
    global sensor_factory
    logger = get_logger('main')
    
    if sensor_factory:
        logger.info("Cleaning up sensor resources")
        # TODO: Implement cleanup of sensors and other resources
    
    logger.info("Cleanup complete")


async def main():
    """Main program entry point."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="w4b Sensor Management System")
    parser.add_argument(
        "--config", "-c",
        default="config/sensor_config.yaml",
        help="Path to configuration file"
    )
    args = parser.parse_args()
    
    # Set up basic logging (will be reconfigured after loading config)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    logger = get_logger('main')
    
    logger.info("Starting w4b Sensor Management System")
    
    # Initialize the system
    if not await initialize_system(args.config):
        logger.error("System initialization failed")
        return 1
    
    # Set up signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(shutdown(s, loop))
        )
    
    try:
        # Run the collection loop
        await run_collection_loop()
    finally:
        # Clean up resources
        await cleanup_system()
    
    logger.info("w4b Sensor Management System shutdown complete")
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
        sys.exit(130)
    except Exception as e:
        print(f"Unhandled exception: {e}", file=sys.stderr)
        sys.exit(1)
