#!/usr/bin/env python3
"""
TimescaleDB connector for the w4b sensor management system.

This module provides database connectivity and operations for storing
and retrieving sensor data using TimescaleDB.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union

import asyncpg
from asyncpg.pool import Pool

from utils.error_handling import retry, CircuitBreaker


class DatabaseError(Exception):
    """Base exception for database-related errors."""
    pass


class TimescaleDBConnector:
    """
    Connector for TimescaleDB operations.
    
    This class provides a high-level interface to TimescaleDB for storing and
    retrieving sensor data, managing retention policies, and handling database
    connections efficiently.
    
    Attributes:
        db_config (Dict[str, Any]): Database configuration parameters
        logger (logging.Logger): Logger instance
        _pool (Optional[Pool]): Connection pool for database operations
        _circuit_breaker (CircuitBreaker): Circuit breaker for handling DB failures
    """
    
    def __init__(self, db_config: Dict[str, Any]):
        """
        Initialize the TimescaleDB connector.
        
        Args:
            db_config: Configuration for TimescaleDB connection, including:
                - host: Database host address
                - port: Database port
                - database: Database name
                - user: Database username
                - password: Database password
                - min_connections: Minimum connections in pool (default: 1)
                - max_connections: Maximum connections in pool (default: 10)
        """
        self.db_config = db_config
        self.logger = logging.getLogger("storage.db")
        self._pool = None
        
        # Set up circuit breaker for database operations
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60.0,
            name="db_operations",
            logger=self.logger
        )
    
    async def initialize(self) -> bool:
        """
        Initialize the database connection pool and verify connectivity.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        try:
            self.logger.info("Initializing TimescaleDB connection pool")
            
            # Create connection pool
            self._pool = await asyncpg.create_pool(
                host=self.db_config.get("host", "localhost"),
                port=self.db_config.get("port", 5432),
                database=self.db_config.get("database", "hivedb"),
                user=self.db_config.get("user", "postgres"),
                password=self.db_config.get("password", ""),
                min_size=self.db_config.get("min_connections", 1),
                max_size=self.db_config.get("max_connections", 10),
                command_timeout=self.db_config.get("command_timeout", 60.0)
            )
            
            # Test connection
            await self._test_connection()
            
            # Ensure schema exists
            await self._ensure_schema()
            
            self.logger.info("TimescaleDB connection pool initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize TimescaleDB: {str(e)}")
            return False
    
    @retry(max_retries=3, exceptions=asyncpg.PostgresError)
    async def _test_connection(self) -> None:
        """
        Test database connectivity.
        
        Raises:
            DatabaseError: If the connection test fails
        """
        if not self._pool:
            raise DatabaseError("Database connection pool not initialized")
            
        try:
            async with self._pool.acquire() as conn:
                version = await conn.fetchval("SELECT version()")
                self.logger.debug(f"Connected to database: {version}")
        except Exception as e:
            raise DatabaseError(f"Database connection test failed: {str(e)}")
    
    async def _ensure_schema(self) -> None:
        """
        Ensure the necessary database schema exists.
        
        Creates tables and hypertables if they don't exist.
        
        Raises:
            DatabaseError: If schema creation fails
        """
        if not self._pool:
            raise DatabaseError("Database connection pool not initialized")
            
        try:
            async with self._pool.acquire() as conn:
                # Create sensor_readings table
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
                
                # Check if hypertable conversion is needed
                is_hypertable = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM timescaledb_information.hypertables
                        WHERE hypertable_name = 'sensor_readings'
                    );
                """)
                
                if not is_hypertable:
                    self.logger.info("Converting sensor_readings to hypertable")
                    await conn.execute("""
                        SELECT create_hypertable('sensor_readings', 'time', 
                                               if_not_exists => TRUE);
                    """)
                
                # Create indexes for efficient queries
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
                
                # Set up retention policy if defined in config
                retention_days = self.db_config.get("retention_days")
                if retention_days:
                    self.logger.info(f"Setting up retention policy: {retention_days} days")
                    await conn.execute(f"""
                        SELECT add_retention_policy('sensor_readings', 
                                                 INTERVAL '{retention_days} days',
                                                 if_not_exists => TRUE);
                    """)
                
                self.logger.info("Database schema setup complete")
                
        except Exception as e:
            self.logger.error(f"Failed to ensure database schema: {str(e)}")
            raise DatabaseError(f"Schema setup failed: {str(e)}")
    
    async def store_reading(self, reading: Dict[str, Any]) -> bool:
        """
        Store a single sensor reading in the database.
        
        Args:
            reading: Sensor reading data containing:
                - hive_id: ID of the hive
                - sensor_id: ID of the sensor
                - metric_name: Name of the metric
                - value: The measurement value
                - unit: Unit of measurement
                - time: Timestamp (defaults to current time if not provided)
                - status: Reading status (defaults to 'valid')
                - metadata: Additional metadata (optional)
        
        Returns:
            bool: True if storage was successful, False otherwise
        
        Raises:
            DatabaseError: If the storage operation fails
        """
        if not self._pool:
            raise DatabaseError("Database connection pool not initialized")
            
        # Default time to now if not provided
        reading_time = reading.get("time", datetime.now(timezone.utc))
        
        try:
            # Use circuit breaker pattern for database operations
            return await self._circuit_breaker.execute(self._store_reading_internal, reading, reading_time)
            
        except Exception as e:
            self.logger.error(f"Failed to store sensor reading: {str(e)}")
            return False
    
    @retry(max_retries=3, exceptions=asyncpg.PostgresError)
    async def _store_reading_internal(self, reading: Dict[str, Any], reading_time: datetime) -> bool:
        """
        Internal method to store a reading with retry support.
        
        Args:
            reading: The sensor reading to store
            reading_time: Timestamp for the reading
        
        Returns:
            bool: True if successful
            
        Raises:
            DatabaseError: If the operation fails
        """
        async with self._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO sensor_readings 
                (time, hive_id, sensor_id, metric_name, value, unit, status, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
                reading_time,
                reading["hive_id"],
                reading["sensor_id"],
                reading["metric_name"],
                reading["value"],
                reading["unit"],
                reading.get("status", "valid"),
                reading.get("metadata", {})
            )
            return True
    
    async def store_readings_batch(self, readings: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Store multiple sensor readings in a batch operation.
        
        Args:
            readings: List of sensor reading data dicts
        
        Returns:
            Tuple containing (number of successful inserts, number of failed inserts)
        """
        if not self._pool:
            raise DatabaseError("Database connection pool not initialized")
            
        if not readings:
            return 0, 0
            
        try:
            # Use circuit breaker pattern
            return await self._circuit_breaker.execute(self._store_readings_batch_internal, readings)
            
        except Exception as e:
            self.logger.error(f"Batch storage operation failed: {str(e)}")
            return 0, len(readings)
    
    @retry(max_retries=2, exceptions=asyncpg.PostgresError)
    async def _store_readings_batch_internal(self, readings: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Internal method to store readings in batch with retry support.
        
        Args:
            readings: List of readings to store
            
        Returns:
            Tuple of (success_count, failure_count)
        """
        success_count = 0
        failure_count = 0
        
        async with self._pool.acquire() as conn:
            # Start a transaction for the batch insert
            async with conn.transaction():
                for reading in readings:
                    try:
                        reading_time = reading.get("time", datetime.now(timezone.utc))
                        
                        await conn.execute("""
                            INSERT INTO sensor_readings 
                            (time, hive_id, sensor_id, metric_name, value, unit, status, metadata)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        """,
                            reading_time,
                            reading["hive_id"],
                            reading["sensor_id"],
                            reading["metric_name"],
                            reading["value"],
                            reading["unit"],
                            reading.get("status", "valid"),
                            reading.get("metadata", {})
                        )
                        success_count += 1
                    except Exception as e:
                        self.logger.warning(f"Failed to insert reading: {str(e)}")
                        failure_count += 1
        
        return success_count, failure_count
    
    async def get_recent_readings(
        self,
        hive_id: str,
        sensor_id: Optional[str] = None,
        metric_name: Optional[str] = None,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get recent sensor readings from the database.
        
        Args:
            hive_id: ID of the hive
            sensor_id: Optional sensor ID filter
            metric_name: Optional metric name filter
            hours: Number of hours of history to retrieve
            
        Returns:
            List of sensor readings as dictionaries
        """
        if not self._pool:
            raise DatabaseError("Database connection pool not initialized")
            
        try:
            return await self._circuit_breaker.execute(
                self._get_recent_readings_internal,
                hive_id, sensor_id, metric_name, hours
            )
        except Exception as e:
            self.logger.error(f"Failed to get recent readings: {str(e)}")
            return []
    
    @retry(max_retries=3, exceptions=asyncpg.PostgresError)
    async def _get_recent_readings_internal(
        self, 
        hive_id: str,
        sensor_id: Optional[str],
        metric_name: Optional[str],
        hours: int
    ) -> List[Dict[str, Any]]:
        """
        Internal method to get recent readings with retry support.
        
        Args:
            hive_id: Hive ID
            sensor_id: Optional sensor ID filter
            metric_name: Optional metric name filter
            hours: Hours of history
            
        Returns:
            List of readings as dictionaries
        """
        # Build the query based on provided filters
        query = """
            SELECT time, hive_id, sensor_id, metric_name, value, unit, status, metadata
            FROM sensor_readings
            WHERE hive_id = $1
            AND time > $2
        """
        params = [hive_id, datetime.now(timezone.utc) - timedelta(hours=hours)]
        
        if sensor_id:
            query += " AND sensor_id = $3"
            params.append(sensor_id)
            
            if metric_name:
                query += " AND metric_name = $4"
                params.append(metric_name)
        elif metric_name:
            query += " AND metric_name = $3"
            params.append(metric_name)
            
        query += " ORDER BY time DESC"
        
        # Execute the query
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            
            # Convert rows to dictionaries
            return [
                {
                    "time": row["time"],
                    "hive_id": row["hive_id"],
                    "sensor_id": row["sensor_id"],
                    "metric_name": row["metric_name"],
                    "value": row["value"],
                    "unit": row["unit"],
                    "status": row["status"],
                    "metadata": row["metadata"]
                }
                for row in rows
            ]
    
    async def get_aggregated_readings(
        self,
        hive_id: str,
        sensor_id: Optional[str] = None,
        metric_name: Optional[str] = None,
        interval: str = "1 hour",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get aggregated sensor readings from the database.
        
        Args:
            hive_id: ID of the hive
            sensor_id: Optional sensor ID filter
            metric_name: Optional metric name filter
            interval: Aggregation interval (e.g., '1 hour', '1 day')
            start_time: Optional start time filter
            end_time: Optional end time filter
            
        Returns:
            List of aggregated sensor readings as dictionaries
        """
        if not self._pool:
            raise DatabaseError("Database connection pool not initialized")
            
        # Default time range to last 7 days if not specified
        if not end_time:
            end_time = datetime.now(timezone.utc)
        if not start_time:
            start_time = end_time - timedelta(days=7)
            
        try:
            return await self._circuit_breaker.execute(
                self._get_aggregated_readings_internal,
                hive_id, sensor_id, metric_name, interval, start_time, end_time
            )
        except Exception as e:
            self.logger.error(f"Failed to get aggregated readings: {str(e)}")
            return []
    
    @retry(max_retries=3, exceptions=asyncpg.PostgresError)
    async def _get_aggregated_readings_internal(
        self,
        hive_id: str,
        sensor_id: Optional[str],
        metric_name: Optional[str],
        interval: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Internal method to get aggregated readings with retry support.
        
        Args:
            hive_id: Hive ID
            sensor_id: Optional sensor ID filter
            metric_name: Optional metric name filter
            interval: Aggregation interval
            start_time: Start time
            end_time: End time
            
        Returns:
            List of aggregated readings
        """
        # Build the query with TimescaleDB time_bucket function
        query = f"""
            SELECT 
                time_bucket('{interval}', time) AS bucket,
                hive_id,
                sensor_id,
                metric_name,
                AVG(value) AS avg_value,
                MIN(value) AS min_value,
                MAX(value) AS max_value,
                COUNT(*) AS sample_count,
                mode() WITHIN GROUP (ORDER BY unit) AS unit
            FROM sensor_readings
            WHERE hive_id = $1
            AND time >= $2
            AND time <= $3
        """
        params = [hive_id, start_time, end_time]
        
        if sensor_id:
            query += " AND sensor_id = $4"
            params.append(sensor_id)
            
            if metric_name:
                query += " AND metric_name = $5"
                params.append(metric_name)
        elif metric_name:
            query += " AND metric_name = $4"
            params.append(metric_name)
            
        query += " GROUP BY bucket, hive_id, sensor_id, metric_name ORDER BY bucket DESC"
        
        # Execute the query
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            
            # Convert rows to dictionaries
            return [
                {
                    "time": row["bucket"],
                    "hive_id": row["hive_id"],
                    "sensor_id": row["sensor_id"],
                    "metric_name": row["metric_name"],
                    "avg_value": row["avg_value"],
                    "min_value": row["min_value"],
                    "max_value": row["max_value"],
                    "sample_count": row["sample_count"],
                    "unit": row["unit"]
                }
                for row in rows
            ]
    
    async def cleanup(self) -> None:
        """
        Close database connections and clean up resources.
        """
        if self._pool:
            self.logger.info("Closing database connection pool")
            await self._pool.close()
            self._pool = None


class DatabaseManager:
    """
    Singleton manager for database operations.
    
    This class provides a centralized point of access to the database
    connector, ensuring there's only one instance throughout the application.
    """
    
    _instance = None
    _connector = None
    
    @classmethod
    def get_instance(cls) -> 'DatabaseManager':
        """
        Get the singleton instance of the DatabaseManager.
        
        Returns:
            DatabaseManager: The singleton instance
        """
        if cls._instance is None:
            cls._instance = DatabaseManager()
        return cls._instance
    
    async def initialize(self, db_config: Dict[str, Any]) -> bool:
        """
        Initialize the database connector.
        
        Args:
            db_config: Database configuration
            
        Returns:
            bool: True if initialization was successful
        """
        self._connector = TimescaleDBConnector(db_config)
        return await self._connector.initialize()
    
    def get_connector(self) -> TimescaleDBConnector:
        """
        Get the database connector instance.
        
        Returns:
            TimescaleDBConnector: The connector instance
            
        Raises:
            DatabaseError: If the connector is not initialized
        """
        if not self._connector:
            raise DatabaseError("Database connector not initialized")
        return self._connector
    
    async def cleanup(self) -> None:
        """
        Clean up database resources.
        """
        if self._connector:
            await self._connector.cleanup()
            self._connector = None
