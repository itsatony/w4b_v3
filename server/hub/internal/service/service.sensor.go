package service

import (
	"context"
	"time"

	"github.com/itsatony/w4b_v3/server/hub/internal/models"
	nuts "github.com/vaudience/go-nuts"
)

// SensorService handles sensor-related business logic
type SensorService interface {
	CreateSensor(ctx context.Context, sensor *models.Sensor) error
	UpdateSensor(ctx context.Context, sensor *models.Sensor) error
	DeleteSensor(ctx context.Context, id string) error
	GetSensorData(ctx context.Context, id string, start, end time.Time, interval string) ([]models.SensorAggregate, error)
	RecordSensorReading(ctx context.Context, sensorID string, value float64, timestamp time.Time) error
}

func (s *Service) RecordSensorReading(ctx context.Context, sensorID string, value float64, timestamp time.Time) error {
	// Get sensor to validate and update last value
	sensor, err := s.sensors.Get(ctx, sensorID)
	if err != nil {
		return err
	}

	// Validate value against sensor limits
	if value < sensor.MinValue || value > sensor.MaxValue {
		nuts.L.Warnf("[SensorService] Value %f out of range for sensor %s", value, sensorID)
		// Still record the value but mark it as potentially invalid
	}

	// Record the reading
	if err := s.sensorData.InsertReading(ctx, sensorID, value, timestamp); err != nil {
		return err
	}

	// Update sensor's last value
	if err := s.sensors.UpdateLastValue(ctx, sensorID, value, timestamp); err != nil {
		nuts.L.Warnf("[SensorService] Failed to update sensor last value: %v", err)
	}

	// Update hive's last sensor data timestamp
	if err := s.hives.UpdateLastSensorData(ctx, sensor.HiveID, timestamp); err != nil {
		nuts.L.Warnf("[SensorService] Failed to update hive last sensor data: %v", err)
	}

	// Check for anomalies and adjust data collection if needed
	go s.handleAnomalyDetection(ctx, sensor, value)

	return nil
}

func (s *Service) handleAnomalyDetection(ctx context.Context, sensor *models.Sensor, value float64) {
	// TODO: Implement anomaly detection
	// This would contain the logic for anomaly detection and handling
	// Implemented separately to avoid blocking the main flow
	// err := s.sensorData.HandleAnomalyDetection(ctx, sensor.ID, value)
	// if err != nil {
	// 	nuts.L.Errorf("[SensorService] Anomaly detection error: %v", err)
	// }
}

// Additional methods would follow similar patterns
// ...existing code for other SensorService methods...
