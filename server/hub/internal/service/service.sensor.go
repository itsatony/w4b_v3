package service

import (
	"context"
	"fmt"
	"time"

	"github.com/itsatony/struccy"
	"github.com/itsatony/w4b_v3/server/hub/internal/errors"
	"github.com/itsatony/w4b_v3/server/hub/internal/models"
	nuts "github.com/vaudience/go-nuts"
)

// SensorService handles sensor-related business logic
type SensorService interface {
	CreateSensor(ctx context.Context, sensor *models.Sensor) error
	GetSensor(ctx context.Context, id string) (*models.Sensor, error)
	UpdateSensor(ctx context.Context, sensor *models.Sensor) error
	DeleteSensor(ctx context.Context, id string) error
	ListSensorsByHive(ctx context.Context, hiveID string) ([]*models.Sensor, error)
	RecordSensorReading(ctx context.Context, sensorID string, value float64, timestamp time.Time) error
	GetSensorReadings(ctx context.Context, sensorID string, start, end time.Time, interval string) ([]models.SensorAggregate, error)
	CalibrateSensor(ctx context.Context, sensorID string, calibration models.CalibrationInfo) error
	SetHighResolutionMode(ctx context.Context, sensorID string, duration time.Duration) error
}

// CreateSensor creates a new sensor with validation and initialization
func (s *Service) CreateSensor(ctx context.Context, sensor *models.Sensor) error {
	// Validate required fields
	if err := s.validateSensor(sensor); err != nil {
		return err
	}

	// Verify hive exists and user has access
	if err := s.verifyHiveAccess(ctx, sensor.HiveID); err != nil {
		return err
	}

	// Generate new ID if not provided
	if sensor.ID == "" {
		sensor.ID = nuts.NID("sn", 12)
	}

	// Set timestamps
	now := time.Now()
	sensor.CreatedAt = now
	sensor.UpdatedAt = now
	sensor.Status = "active"

	nuts.L.Infof("[SensorService] Creating new sensor: %s (type: %s) for hive: %s",
		sensor.Name, sensor.Type, sensor.HiveID)

	return s.sensors.Create(ctx, sensor)
}

// UpdateSensor updates sensor configuration with role-based access control
func (s *Service) UpdateSensor(ctx context.Context, sensor *models.Sensor) error {
	existing, err := s.sensors.Get(ctx, sensor.ID)
	if err != nil {
		return err
	}

	roles := GetUserRoles(ctx)
	updatedFields, _, err := struccy.UpdateStructFields(existing, sensor, roles, true, true)
	if err != nil {
		return errors.NewAuthorizationError("unauthorized field update", err)
	}

	sensor.UpdatedAt = time.Now()

	nuts.L.Infof("[SensorService] Updating sensor %s, fields changed: %v", sensor.ID, updatedFields)
	return s.sensors.Update(ctx, sensor)
}

// GetSensor retrieves a sensor with role-based field filtering
func (s *Service) GetSensor(ctx context.Context, id string) (*models.Sensor, error) {
	sensor, err := s.sensors.Get(ctx, id)
	if err != nil {
		return nil, err
	}

	roles := GetUserRoles(ctx)
	filteredMap, err := struccy.StructToMapFieldsWithReadXS(sensor, roles)
	if err != nil {
		return nil, errors.NewInternalError("failed to filter sensor fields", err)
	}

	filtered := &models.Sensor{}
	_, err = struccy.MergeMapStringFieldsToStruct(filtered, filteredMap, roles)
	if err != nil {
		return nil, errors.NewInternalError("failed to map filtered fields", err)
	}

	return filtered, nil
}

// RecordSensorReading handles new sensor readings with validation and anomaly detection
func (s *Service) RecordSensorReading(ctx context.Context, sensorID string, value float64, timestamp time.Time) error {
	sensor, err := s.sensors.Get(ctx, sensorID)
	if err != nil {
		return err
	}

	// Validate reading value against sensor limits
	if err := s.validateReading(sensor, value); err != nil {
		return err
	}

	// Apply calibration if configured
	calibratedValue, err := s.applySensorCalibration(sensor, value)
	if err != nil {
		nuts.L.Warnf("[SensorService] Calibration failed for sensor %s: %v", sensorID, err)
		// Continue with uncalibrated value
		calibratedValue = value
	}

	// Record the reading
	err = s.sensorData.InsertReading(ctx, sensorID, calibratedValue, timestamp)
	if err != nil {
		return err
	}

	// Update sensor's last value
	sensor.LastValue = calibratedValue
	sensor.LastValueTime = timestamp
	err = s.sensors.UpdateLastValue(ctx, sensorID, calibratedValue, timestamp)
	if err != nil {
		nuts.L.Warnf("[SensorService] Failed to update sensor last value: %v", err)
	}

	// Check for anomalies and adjust data collection if needed
	go s.handleAnomalyDetection(ctx, sensor, calibratedValue)

	return nil
}

// GetSensorReadings retrieves sensor readings with aggregation based on the time interval
func (s *Service) GetSensorReadings(ctx context.Context, sensorID string, start, end time.Time, interval string) ([]models.SensorAggregate, error) {
	if end.Before(start) {
		return nil, errors.NewValidationError("end time must be after start time", nil)
	}

	// Validate interval and adjust if necessary based on time range
	interval = s.determineAppropriateSensorReadingInterval(start, end, interval)

	return s.sensorData.GetAggregates(ctx, sensorID, start, end, interval)
}

// CalibrateSensor updates sensor calibration information
func (s *Service) CalibrateSensor(ctx context.Context, sensorID string, calibration models.CalibrationInfo) error {
	sensor, err := s.sensors.Get(ctx, sensorID)
	if err != nil {
		return err
	}

	// Validate calibration data
	if err := s.validateCalibration(calibration); err != nil {
		return err
	}

	// Update calibration info
	sensor.Calibration = calibration
	sensor.Calibration.LastCalibration = time.Now()

	nuts.L.Infof("[SensorService] Updating calibration for sensor %s using method %s",
		sensorID, calibration.Method)

	return s.sensors.Update(ctx, sensor)
}

// SetHighResolutionMode enables high-frequency data collection for a specified duration
func (s *Service) SetHighResolutionMode(ctx context.Context, sensorID string, duration time.Duration) error {
	if duration > 30*time.Minute {
		return errors.NewValidationError("high resolution mode limited to 30 minutes", nil)
	}

	// Implementation would involve setting up a temporary configuration
	// for increased data collection frequency
	nuts.L.Infof("[SensorService] Enabling high resolution mode for sensor %s for %v",
		sensorID, duration)

	// Schedule return to normal mode
	time.AfterFunc(duration, func() {
		if err := s.disableHighResolutionMode(context.Background(), sensorID); err != nil {
			nuts.L.Errorf("[SensorService] Failed to disable high resolution mode: %v", err)
		}
	})

	return nil
}

// Helper functions

func (s *Service) validateSensor(sensor *models.Sensor) error {
	if sensor.Name == "" {
		return errors.NewValidationError("sensor name is required", nil)
	}
	if sensor.Type == "" {
		return errors.NewValidationError("sensor type is required", nil)
	}
	if !isValidSensorType(sensor.Type) {
		return errors.NewValidationError("invalid sensor type", nil)
	}
	return nil
}

func (s *Service) validateReading(sensor *models.Sensor, value float64) error {
	if value < sensor.MinValue || value > sensor.MaxValue {
		return errors.NewValidationError(
			fmt.Sprintf("value %f outside sensor range [%f, %f]",
				value, sensor.MinValue, sensor.MaxValue),
			nil,
		)
	}
	return nil
}

func (s *Service) applySensorCalibration(sensor *models.Sensor, value float64) (float64, error) {
	// the real calibration will be done on the edge device.
	// here, we only store it.
	if sensor.Calibration.Method == "" {
		return value, errors.NewValidationError("calibration method is required", nil)
	}
	return value, nil
	// switch sensor.Calibration.Method {
	// case models.Linear:
	// 	return s.applyLinearCalibration(sensor.Calibration, value)
	// case models.Polynomial:
	// 	return s.applyPolynomialCalibration(sensor.Calibration, value)
	// case models.Offset:
	// 	return value + sensor.Calibration.Offset, nil
	// case models.Scale:
	// 	return value * sensor.Calibration.Scale, nil
	// default:
	// 	return value, nil
	// }
}

func (s *Service) validateCalibration(calibration models.CalibrationInfo) error {
	if calibration.Method == "" {
		return errors.NewValidationError("calibration method is required", nil)
	}
	// Add validation for specific calibration methods as needed
	return nil
}

func (s *Service) disableHighResolutionMode(ctx context.Context, sensorID string) error {
	// TODO: determine how we will implement the endabledisable High-Resolution-Mode feature
	nuts.L.Infof("[SensorService] Disabling high resolution mode for sensor %s", sensorID)
	return nil
}

func (s *Service) verifyHiveAccess(ctx context.Context, hiveID string) error {
	// TODO: implement hive access verification
	return nil
}

func (s *Service) handleAnomalyDetection(ctx context.Context, sensor *models.Sensor, value float64) {
	if sensor.Type == models.Temperature {
		s.handleTemperatureAnomaly(ctx, sensor, value)
	}
	// Add other anomaly detection handlers as needed
}

func (s *Service) handleTemperatureAnomaly(ctx context.Context, sensor *models.Sensor, value float64) {
	const tempSpikeThreshold = 5.0 // °C
	lastValue := sensor.LastValue

	if abs(value-lastValue) > tempSpikeThreshold {
		nuts.L.Warnf("[SensorService] Temperature spike detected on sensor %s: %f -> %f",
			sensor.ID, lastValue, value)
		// Trigger high-resolution mode for an hour
		s.SetHighResolutionMode(ctx, sensor.ID, time.Hour)
	}
}

func (s *Service) determineAppropriateSensorReadingInterval(start, end time.Time, requestedInterval string) string {
	// if the interval is smaller than min or larger than max, adjust it - otherwise, return it as is
	duration := end.Sub(start)
	switch {
	case duration <= 30*time.Hour:
		if requestedInterval < "1min" || requestedInterval > "1day" {
			return "1min"
		} else {
			return requestedInterval
		}
	case duration <= 70*24*time.Hour:
		if requestedInterval < "20min" || requestedInterval > "1day" {
			return "20min"
		} else {
			return requestedInterval
		}
	case duration <= 13*30*24*time.Hour:
		if requestedInterval < "1hour" || requestedInterval > "1day" {
			return "6hour"
		} else {
			return requestedInterval
		}
	default:
		return "1day"
	}
}

func isValidSensorType(t models.SensorType) bool {
	validTypes := map[models.SensorType]bool{
		models.Temperature: true,
		models.Humidity:    true,
		models.Weight:      true,
		models.Sound:       true,
		models.Image:       true,
		models.Pressure:    true,
		models.Light:       true,
		models.Motion:      true,
		models.Gas:         true,
		models.Vibration:   true,
	}
	return validTypes[t]
}

func abs(x float64) float64 {
	if x < 0 {
		return -x
	}
	return x
}
