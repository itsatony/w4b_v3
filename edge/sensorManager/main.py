#!/usr/bin/env python3
"""
Main entry point for the w4b sensor management system.

This script initializes and runs the sensor management system, handling
configuration, sensor discovery and initialization, and data collection.
"""

import asyncio
import argparse
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

from config.config_manager import ConfigManager, ConfigurationError
from sensors.factory import SensorRegistry, SensorFactory
from storage.db_connector import DatabaseManager, DatabaseError
from collectors.collection_service import CollectionService
from utils.logging_setup import configure_logging, get_logger
from utils.error_handling import handle_critical_error

# Global state variables
running = True
collection_service = None


async def initialize_system(config_path: str) -> bool:
    """
    Initialize all system components.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        bool: True if initialization was successful
    """
    logger = get_logger("main")
    
    try:
        # Load configuration
        logger.info(f"Loading configuration from {config_path}")
        config_manager = ConfigManager(config_path)
        
        # Configure logging based on configuration
        configure_logging(
            config_manager.config,
            logs_dir=config_manager.get("logging.directory", "/var/log/hive")
        )
        
        # Initialize database
        logger.info("Initializing database connection")
        db_manager = DatabaseManager.get_instance()
        db_success = await db_manager.initialize(config_manager.config["storage"])
        
        if not db_success:
            logger.error("Failed to initialize database connection")
            return False
            
        # Initialize sensors
        logger.info("Initializing sensors")
        registry = SensorRegistry()
        factory = SensorFactory(registry)
        
        # Get sensor configurations
        enabled_sensors = config_manager.get_all_enabled_sensors()
        sensor_types = config_manager.get("sensor_types", {})
        
        if not enabled_sensors:
            logger.warning("No enabled sensors found in configuration")
            return False
            
        # Create and initialize sensors
        logger.info(f"Creating {len(enabled_sensors)} sensors")
        sensors = await factory.create_sensors_from_config(
            enabled_sensors,
            sensor_types
        )
        
        if not sensors:
            logger.error("Failed to initialize any sensors")
            return False
            
        logger.info(f"Successfully initialized {len(sensors)} sensors")
        
        # Create sensor configurations dictionary
        sensor_configs = {
            sensor_config["id"]: sensor_config
            for sensor_config in enabled_sensors
            if sensor_config["id"] in sensors
        }
        
        # Create and start collection service
        global collection_service
        collection_service = CollectionService(
            config_manager.get("hive_id", "unknown"),
            sensors,
            sensor_configs,
            config_manager.get("collectors", {})
        )
        
        await collection_service.start()
        
        logger.info("System initialization complete")
        return True
        
    except ConfigurationError as e:
        logger.error(f"Configuration error: {str(e)}")
        return False
        
    except Exception as e:
        logger.exception(f"Unexpected error during initialization: {str(e)}")
        return False


async def shutdown() -> None:
    """
    Gracefully shut down the system, cleaning up resources.
    """
    global running, collection_service
    
    logger = get_logger("main")
    logger.info("Shutting down...")
    
    running = False
    
    # Stop collection service if running
    if collection_service:
        logger.info("Stopping collection service")
        await collection_service.stop()
    
    # Clean up database connection
    try:
        logger.info("Closing database connection")
        await DatabaseManager.get_instance().cleanup()
    except Exception as e:
        logger.error(f"Error during database cleanup: {str(e)}")
    
    logger.info("Shutdown complete")


def handle_signal(sig_name: str) -> None:
    """
    Handle OS signals for graceful shutdown.
    
    Args:
        sig_name: Name of the signal received
    """
    logger = get_logger("main")
    logger.info(f"Received signal {sig_name}")
    
    # Create task to run shutdown
    if asyncio.get_event_loop().is_running():
        asyncio.create_task(shutdown())
    else:
        # We're not in an async context
        logger.warning("Signal received outside of async context, shutting down immediately")
        sys.exit(0)


async def main() -> int:
    """
    Main application entry point.
    
    Returns:
        int: Exit code (0 for success, non-zero for error)
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="w4b Sensor Management System")
    parser.add_argument(
        "--config", "-c",
        default=os.environ.get("W4B_CONFIG_PATH", "config/sensor_config.yaml"),
        help="Path to configuration file"
    )
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable debug logging"
    )
    args = parser.parse_args()
    
    # Set up basic logging (will be reconfigured when config is loaded)
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    logger = get_logger("main")
    logger.info("Starting w4b Sensor Management System")
    
    # Set up signal handlers
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda s, f: handle_signal(signal.Signals(s).name))
    
    try:
        # Initialize the system
        init_success = await initialize_system(args.config)
        if not init_success:
            logger.error("System initialization failed")
            return 1
        
        # Run until signaled to stop
        while running:
            await asyncio.sleep(1)
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
        
    except Exception as e:
        logger.exception(f"Unhandled exception: {str(e)}")
        return 1
        
    finally:
        # Ensure cleanup happens
        await shutdown()


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
