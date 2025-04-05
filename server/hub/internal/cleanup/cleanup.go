package cleanup

import (
	"context"
	"fmt"

	"github.com/itsatony/w4b_v3/server/hub/internal/repository"
	nuts "github.com/vaudience/go-nuts"
)

// CleanupService coordinates deletion of hierarchical data
type CleanupService struct {
	hives        repository.HiveRepository
	sensors      repository.SensorRepository
	sensorData   repository.SensorDataRepository
	files        repository.FileRepository
	hiveComments repository.HiveCommentRepository
	events       *nuts.EventEmitter
}

// New creates a new CleanupService
func New(
	hives repository.HiveRepository,
	sensors repository.SensorRepository,
	sensorData repository.SensorDataRepository,
	files repository.FileRepository,
	hiveComments repository.HiveCommentRepository,
) *CleanupService {
	return &CleanupService{
		hives:        hives,
		sensors:      sensors,
		sensorData:   sensorData,
		files:        files,
		hiveComments: hiveComments,
		events:       nuts.NewEventEmitter(),
	}
}

// DeleteHive deletes a hive and all its associated data
func (s *CleanupService) DeleteHive(ctx context.Context, hiveID string) error {
	// Start transaction
	tx, err := s.hives.BeginTx(ctx)
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback() // Will be ignored if transaction is committed

	// Get all sensors for the hive
	sensors, err := s.sensors.ListByHive(ctx, hiveID)
	if err != nil {
		return fmt.Errorf("failed to list sensors: %w", err)
	}

	// Delete sensor data for each sensor
	for _, sensor := range sensors {
		if err := s.sensorData.DeleteBySensorID(ctx, sensor.ID); err != nil {
			return fmt.Errorf("failed to delete sensor data: %w", err)
		}
		s.events.Emit("sensor.deleted", sensor.ID)
	}

	// Delete all files
	files, err := s.files.ListByHive(ctx, hiveID, "")
	if err != nil {
		return fmt.Errorf("failed to list files: %w", err)
	}
	for _, file := range files {
		if err := s.files.Delete(ctx, file.ID); err != nil {
			return fmt.Errorf("failed to delete file: %w", err)
		}
		s.events.Emit("file.deleted", file.ID)
	}

	// Delete all comments
	if err := s.hiveComments.DeleteByHive(ctx, hiveID); err != nil {
		return fmt.Errorf("failed to delete comments: %w", err)
	}
	s.events.Emit("comments.deleted", hiveID)

	// Delete all sensors
	for _, sensor := range sensors {
		if err := s.sensors.Delete(ctx, sensor.ID); err != nil {
			return fmt.Errorf("failed to delete sensor: %w", err)
		}
	}

	// Finally, delete the hive
	if err := s.hives.Delete(ctx, hiveID); err != nil {
		return fmt.Errorf("failed to delete hive: %w", err)
	}

	// Commit transaction
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	// Emit event after successful deletion
	s.events.Emit("hive.deleted", hiveID)
	return nil
}

// DeleteSensor deletes a sensor and all its associated data
func (s *CleanupService) DeleteSensor(ctx context.Context, sensorID string) error {
	// Start transaction
	tx, err := s.sensors.BeginTx(ctx)
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	// Delete sensor data
	if err := s.sensorData.DeleteBySensorID(ctx, sensorID); err != nil {
		return fmt.Errorf("failed to delete sensor data: %w", err)
	}

	// Delete the sensor
	if err := s.sensors.Delete(ctx, sensorID); err != nil {
		return fmt.Errorf("failed to delete sensor: %w", err)
	}

	// Commit transaction
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	// Emit event after successful deletion
	s.events.Emit("sensor.deleted", sensorID)
	return nil
}

// OnCleanup registers a callback for cleanup events
func (s *CleanupService) OnCleanup(event string, handler func(id string)) {
	s.events.On(event, "cleanup_handler", func(args ...interface{}) {
		if len(args) > 0 {
			if id, ok := args[0].(string); ok {
				handler(id)
			}
		}
	})
}
