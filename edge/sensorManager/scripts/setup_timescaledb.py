#!/usr/bin/env python3
"""
Script to set up TimescaleDB schema for sensor data storage.

This script creates the necessary database schema for storing sensor data
and configures TimescaleDB features like hypertables and retention policies.
"""

import argparse
import asyncio
import logging
import sys
from typing import Dict, Any, Optional

import asyncpg
import yaml


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("db_setup")


async def create_database(config: Dict[str, Any]) -> bool:
    """
    Create the database if it doesn't exist.
    
    Args:
        config: Database configuration
        
    Returns:
        bool: True if successful
    """
    # Connect to postgres database to create our target database
    try:
        # Create a connection to default database
        conn = await asyncpg.connect(
            host=config.get("host", "localhost"),
            port=config.get("port", 5432),
            user=config.get("user", "postgres"),
            password=config.get("password", ""),
            database="postgres"  # Connect to default database
        )
        
        # Check if database exists
        db_exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname = $1)",
            config.get("database", "hivedb")
        )
        
        if not db_exists:
            logger.info(f"Creating database: {config.get('database', 'hivedb')}")
            # Create database
            await conn.execute(
                f"CREATE DATABASE {config.get('database', 'hivedb')}"
            )
            logger.info("Database created successfully")
        else:
            logger.info(f"Database {config.get('database', 'hivedb')} already exists")
            
        await conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Failed to create database: {str(e)}")
        return False


async def setup_schema(config: Dict[str, Any]) -> bool:
    """
    Set up the database schema for TimescaleDB.
    
    Args:
        config: Database configuration
        
    Returns:
        bool: True if successful
    """
    try:
        # Connect to the target database
        conn = await asyncpg.connect(
            host=config.get("host", "localhost"),
            port=config.get("port", 5432),
            user=config.get("user", "postgres"),
            password=config.get("password", ""),
            database=config.get("database", "hivedb")
        )
        
        # Check if TimescaleDB extension is installed
        has_timescaledb = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'timescaledb')"
        )
        
        if not has_timescaledb:
            logger.info("Creating TimescaleDB extension")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
        
        # Create sensor_readings table
        logger.info("Creating sensor_readings table")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sensor_readings (
                time TIMESTAMPTZ NOT NULL,
                hive_id TEXT NOT NULL,
                sensor_id TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                value DOUBLE PRECISION NOT NULL,
                unit TEXT NOT NULL,
                status TEXT DEFAULT 'valid',
                metadata JSONB DEFAULT '{}'::jsonb
            );
        """)
        
        # Check if already converted to hypertable
        is_hypertable = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM timescaledb_information.hypertables
                WHERE hypertable_name = 'sensor_readings'
            );
        """)
        
        if not is_hypertable:
            logger.info("Converting sensor_readings to hypertable")
            await conn.execute("""
                SELECT create_hypertable('sensor_readings', 'time', 
                                       if_not_exists => TRUE);
            """)
        
        # Create indexes
        logger.info("Creating indexes")
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS sensor_readings_hive_idx 
            ON sensor_readings (hive_id);
            
            CREATE INDEX IF NOT EXISTS sensor_readings_sensor_idx 
            ON sensor_readings (sensor_id);
            
            CREATE INDEX IF NOT EXISTS sensor_readings_metric_idx 
            ON sensor_readings (metric_name);
            
            CREATE INDEX IF NOT EXISTS sensor_readings_hive_sensor_idx 
            ON sensor_readings (hive_id, sensor_id);
        """)
        
        # Set up compression policy
        logger.info("Setting up compression policy")
        await conn.execute("""
            ALTER TABLE sensor_readings SET (
                timescaledb.compress,
                timescaledb.compress_segmentby = 'hive_id,sensor_id,metric_name'
            );
        """)
        
        # Create compression policy
        try:
            await conn.execute("""
                SELECT add_compression_policy('sensor_readings', INTERVAL '7 days');
            """)
            logger.info("Compression policy added")
        except asyncpg.exceptions.DuplicateObjectError:
            logger.info("Compression policy already exists")
        
        # Create retention policy if specified
        retention_days = config.get("retention_days")
        if retention_days:
            logger.info(f"Setting up retention policy: {retention_days} days")
            try:
                await conn.execute(f"""
                    SELECT add_retention_policy('sensor_readings', 
                                             INTERVAL '{retention_days} days');
                """)
                logger.info("Retention policy added")
            except asyncpg.exceptions.DuplicateObjectError:
                logger.info("Retention policy already exists")
        
        await conn.close()
        logger.info("Database schema setup complete")
        return True
        
    except Exception as e:
        logger.error(f"Failed to set up schema: {str(e)}")
        return False


async def main() -> int:
    """
    Main entry point.
    
    Returns:
        int: Exit code (0 for success, non-zero for error)
    """
    parser = argparse.ArgumentParser(description="Set up TimescaleDB for sensor data")
    parser.add_argument(
        "--config", "-c",
        default="config/sensor_config.yaml",
        help="Path to configuration file"
    )
    args = parser.parse_args()
    
    try:
        # Load configuration
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
        
        db_config = config.get("storage", {})
        
        # Create database
        if not await create_database(db_config):
            return 1
        
        # Set up schema
        if not await setup_schema(db_config):
            return 1
        
        logger.info("Database setup completed successfully")
        return 0
        
    except Exception as e:
        logger.exception(f"Unexpected error: {str(e)}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
