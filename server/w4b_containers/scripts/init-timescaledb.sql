# /server/w4b_containers/scripts/init-timescaledb.sql

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Create schemas
CREATE SCHEMA IF NOT EXISTS metrics;
CREATE SCHEMA IF NOT EXISTS meta;

-- Create hypertables for different metric types
-- Sensor readings
CREATE TABLE IF NOT EXISTS metrics.sensor_data (
    time TIMESTAMPTZ NOT NULL,
    sensor_id TEXT NOT NULL,
    hive_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit TEXT,
    metadata JSONB
);
SELECT create_hypertable('metrics.sensor_data', 'time');

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_sensor_data_sensor_id ON metrics.sensor_data (sensor_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_sensor_data_hive_id ON metrics.sensor_data (hive_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_sensor_data_metric ON metrics.sensor_data (metric_name, time DESC);

-- System metrics
CREATE TABLE IF NOT EXISTS metrics.system_health (
    time TIMESTAMPTZ NOT NULL,
    hive_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    metadata JSONB
);
SELECT create_hypertable('metrics.system_health', 'time');

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_system_health_hive ON metrics.system_health (hive_id, time DESC);

-- Continuous aggregates for sensor data
CREATE MATERIALIZED VIEW metrics.sensor_data_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    hive_id,
    sensor_id,
    metric_name,
    AVG(value) as avg_value,
    MIN(value) as min_value,
    MAX(value) as max_value,
    COUNT(*) as sample_count
FROM metrics.sensor_data
GROUP BY bucket, hive_id, sensor_id, metric_name;

-- Add retention policy (30 days for raw data, 1 year for aggregates)
SELECT add_retention_policy('metrics.sensor_data', INTERVAL '30 days');
SELECT add_retention_policy('metrics.system_health', INTERVAL '30 days');
SELECT add_retention_policy('metrics.sensor_data_hourly', INTERVAL '365 days');

-- Add compression policy (after 24 hours)
SELECT add_compression_policy('metrics.sensor_data', INTERVAL '1 day');
SELECT add_compression_policy('metrics.system_health', INTERVAL '1 day');

-- Meta tables for configuration
CREATE TABLE IF NOT EXISTS meta.sensors (
    sensor_id TEXT PRIMARY KEY,
    hive_id TEXT NOT NULL,
    sensor_type TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    config JSONB
);

CREATE TABLE IF NOT EXISTS meta.hives (
    hive_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    location JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

-- Update trigger for metadata tables
CREATE OR REPLACE FUNCTION meta.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_sensors_timestamp
    BEFORE UPDATE ON meta.sensors
    FOR EACH ROW
    EXECUTE FUNCTION meta.update_updated_at();

CREATE TRIGGER update_hives_timestamp
    BEFORE UPDATE ON meta.hives
    FOR EACH ROW
    EXECUTE FUNCTION meta.update_updated_at();

