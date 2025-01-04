// FilePath: server/hub/internal/repository/timescale/timescale.sensor_data.go
package timescale

import (
	"context"
	"fmt"
	"time"

	"github.com/itsatony/w4b_v3/server/hub/internal/database"
	"github.com/itsatony/w4b_v3/server/hub/internal/errors"
	"github.com/itsatony/w4b_v3/server/hub/internal/models"
	nuts "github.com/vaudience/go-nuts"
)

type SensorDataRepo struct {
	db database.DB
}

func NewSensorDataRepository(db database.DB) (*SensorDataRepo, error) {
	repo := &SensorDataRepo{db: db}
	err := repo.initializeSchema()
	if err != nil {
		return nil, err
	}
	return repo, nil
}

func (r *SensorDataRepo) initializeSchema() error {
	// Create hypertable for sensor readings
	queries := []string{
		`CREATE TABLE IF NOT EXISTS sensor_readings (
			id TEXT PRIMARY KEY,
			sensor_id TEXT NOT NULL,
			value DOUBLE PRECISION NOT NULL,
			timestamp TIMESTAMPTZ NOT NULL
		)`,
		`SELECT create_hypertable('sensor_readings', 'timestamp', 
			chunk_time_interval => INTERVAL '1 day', 
			if_not_exists => TRUE
		)`,
		// Create continuous aggregates for different time intervals
		`CREATE MATERIALIZED VIEW IF NOT EXISTS sensor_readings_hourly
			WITH (timescaledb.continuous) AS
			SELECT sensor_id,
				time_bucket('1 hour', timestamp) AS bucket,
				MIN(value) as min_value,
				MAX(value) as max_value,
				AVG(value) as avg_value,
				COUNT(*) as reading_count
			FROM sensor_readings
			GROUP BY sensor_id, time_bucket('1 hour', timestamp)`,
		`CREATE MATERIALIZED VIEW IF NOT EXISTS sensor_readings_daily
			WITH (timescaledb.continuous) AS
			SELECT sensor_id,
				time_bucket('1 day', timestamp) AS bucket,
				MIN(value) as min_value,
				MAX(value) as max_value,
				AVG(value) as avg_value,
				COUNT(*) as reading_count
			FROM sensor_readings
			GROUP BY sensor_id, time_bucket('1 day', timestamp)`,
		// Add index for latest readings queries
		`CREATE INDEX IF NOT EXISTS idx_sensor_readings_sensor_timestamp 
         ON sensor_readings(sensor_id, timestamp DESC)`,
	}

	for _, query := range queries {
		_, err := r.db.GetDB().Exec(query)
		if err != nil {
			return errors.NewDatabaseError("failed to initialize schema", err)
		}
	}

	// Set up retention policies
	r.setupRetentionPolicies()
	return nil
}

func (r *SensorDataRepo) setupRetentionPolicies() {
	policies := []struct {
		name     string
		interval string
	}{
		{"recent_data", "30 hours"},
		{"medium_term_data", "70 days"},
		{"long_term_data", "13 months"},
	}

	for _, policy := range policies {
		query := fmt.Sprintf(`
			SELECT add_retention_policy('sensor_readings', 
				INTERVAL '%s', 
				if_not_exists => TRUE
			)`, policy.interval)

		_, err := r.db.GetDB().Exec(query)
		if err != nil {
			nuts.L.Errorf("[TimescaleDB] Failed to set up retention policy %s: %v", policy.name, err)
		}
	}
}

func (r *SensorDataRepo) InsertReading(ctx context.Context, sensorID string, value float64, timestamp time.Time) error {
	id := nuts.NID("sr", 12)
	query := `
		INSERT INTO sensor_readings (id, sensor_id, value, timestamp)
		VALUES ($1, $2, $3, $4)`

	_, err := r.db.GetDB().ExecContext(ctx, query, id, sensorID, value, timestamp)
	if err != nil {
		return errors.NewDatabaseError("failed to insert sensor reading", err)
	}
	return nil
}

func (r *SensorDataRepo) GetReadings(ctx context.Context, sensorID string, start, end time.Time) ([]models.SensorReading, error) {
	readings := []models.SensorReading{}
	query := `
		SELECT id, sensor_id, value, timestamp
		FROM sensor_readings
		WHERE sensor_id = $1 AND timestamp BETWEEN $2 AND $3
		ORDER BY timestamp DESC`

	err := r.db.GetDB().SelectContext(ctx, &readings, query, sensorID, start, end)
	if err != nil {
		return nil, errors.NewDatabaseError("failed to get sensor readings", err)
	}
	return readings, nil
}

func (r *SensorDataRepo) GetAggregates(ctx context.Context, sensorID string, start, end time.Time, interval string) ([]models.SensorAggregate, error) {
	var tableName string
	switch interval {
	case "hour":
		tableName = "sensor_readings_hourly"
	case "day":
		tableName = "sensor_readings_daily"
	default:
		return nil, errors.NewValidationError("invalid interval", nil)
	}

	aggregates := []models.SensorAggregate{}
	query := fmt.Sprintf(`
		SELECT 
			sensor_id,
			min_value as min,
			max_value as max,
			avg_value as avg,
			reading_count as count,
			bucket as start_time,
			bucket + INTERVAL '1 %s' as end_time
		FROM %s
		WHERE sensor_id = $1 AND bucket BETWEEN $2 AND $3
		ORDER BY bucket DESC`, interval, tableName)

	err := r.db.GetDB().SelectContext(ctx, &aggregates, query, sensorID, start, end)
	if err != nil {
		return nil, errors.NewDatabaseError("failed to get sensor aggregates", err)
	}
	return aggregates, nil
}

func (r *SensorDataRepo) DeleteOldData(ctx context.Context, before time.Time) error {
	query := `DELETE FROM sensor_readings WHERE timestamp < $1`

	result, err := r.db.GetDB().ExecContext(ctx, query, before)
	if err != nil {
		return errors.NewDatabaseError("failed to delete old data", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return errors.NewDatabaseError("failed to get rows affected", err)
	}

	nuts.L.Infof("[TimescaleDB] Deleted %d old sensor readings before %v", rows, before)
	return nil
}

// HandleAnomalyDetection increases data collection frequency when anomalies are detected
func (r *SensorDataRepo) HandleAnomalyDetection(ctx context.Context, sensorID string, value float64) error {
	// Check for temperature spikes (more than 5°C change in an hour)
	query := `
		SELECT value 
		FROM sensor_readings 
		WHERE sensor_id = $1 
		AND timestamp > NOW() - INTERVAL '1 hour'
		ORDER BY timestamp DESC 
		LIMIT 1`

	var lastValue float64
	err := r.db.GetDB().GetContext(ctx, &lastValue, query, sensorID)
	if err == nil && abs(value-lastValue) > 5.0 {
		nuts.L.Infof("[TimescaleDB] Temperature spike detected for sensor %s: %f -> %f",
			sensorID, lastValue, value)
		// Logic to increase sampling frequency would go here
	}

	return nil
}

func abs(x float64) float64 {
	if x < 0 {
		return -x
	}
	return x
}

func (r *SensorDataRepo) GetLatestReadingsBySensor(ctx context.Context, sensorID string) (*models.SensorReading, error) {
	reading := &models.SensorReading{}
	query := `
        SELECT id, sensor_id, value, timestamp
        FROM sensor_readings
        WHERE sensor_id = $1
        ORDER BY timestamp DESC
        LIMIT 1`

	err := r.db.GetDB().GetContext(ctx, reading, query, sensorID)
	if err != nil {
		return nil, errors.NewDatabaseError("failed to get latest sensor reading", err)
	}
	return reading, nil
}

func (r *SensorDataRepo) GetLatestReadingsByHive(ctx context.Context, hiveID string) (map[string]*models.SensorReading, error) {
	// Use a window function to get the latest reading for each sensor efficiently
	query := `
        WITH RankedReadings AS (
            SELECT sr.id, sr.sensor_id, sr.value, sr.timestamp,
                   ROW_NUMBER() OVER (PARTITION BY sr.sensor_id ORDER BY sr.timestamp DESC) as rn
            FROM sensor_readings sr
            JOIN sensors s ON s.id = sr.sensor_id
            WHERE s.hive_id = $1
        )
        SELECT id, sensor_id, value, timestamp
        FROM RankedReadings
        WHERE rn = 1`

	readings := []*models.SensorReading{}
	err := r.db.GetDB().SelectContext(ctx, &readings, query, hiveID)
	if err != nil {
		return nil, errors.NewDatabaseError("failed to get latest hive readings", err)
	}

	// Convert to map for easier access
	result := make(map[string]*models.SensorReading)
	for _, reading := range readings {
		result[reading.SensorID] = reading
	}
	return result, nil
}
