package service

import (
	"github.com/itsatony/w4b_v3/server/hub/internal/errors"
	"github.com/itsatony/w4b_v3/server/hub/internal/repository"
)

// Service contains all repositories and service-wide dependencies
type Service struct {
	hives      repository.HiveRepository
	sensors    repository.SensorRepository
	sensorData repository.SensorDataRepository
	files      repository.FileRepository
}

// New creates a new service instance
func New(
	hives repository.HiveRepository,
	sensors repository.SensorRepository,
	sensorData repository.SensorDataRepository,
	files repository.FileRepository,
) *Service {
	return &Service{
		hives:      hives,
		sensors:    sensors,
		sensorData: sensorData,
		files:      files,
	}
}

// Validate checks if all required repositories are initialized
func (s *Service) Validate() error {
	if s.hives == nil {
		return ErrMissingRepository("hives")
	}
	if s.sensors == nil {
		return ErrMissingRepository("sensors")
	}
	if s.sensorData == nil {
		return ErrMissingRepository("sensorData")
	}
	if s.files == nil {
		return ErrMissingRepository("files")
	}
	return nil
}

func ErrMissingRepository(name string) error {
	return errors.NewInternalError("missing repository: "+name, nil)
}
