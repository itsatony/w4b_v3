package hubservice

import (
	"github.com/itsatony/w4b_v3/server/hub/internal/cleanup"
	"github.com/itsatony/w4b_v3/server/hub/internal/errors"
	"github.com/itsatony/w4b_v3/server/hub/internal/repository"
)

// HubService contains all repositories and service-wide dependencies
type HubService struct {
	Hives        repository.HiveRepository
	Sensors      repository.SensorRepository
	SensorData   repository.SensorDataRepository
	Files        repository.FileRepository
	HiveComments repository.HiveCommentRepository
	Cleanup      *cleanup.CleanupService
}

// New creates a new HubService instance
func New(
	hives repository.HiveRepository,
	sensors repository.SensorRepository,
	sensorData repository.SensorDataRepository,
	files repository.FileRepository,
	comments repository.HiveCommentRepository,
) *HubService {
	svc := &HubService{
		Hives:        hives,
		Sensors:      sensors,
		SensorData:   sensorData,
		Files:        files,
		HiveComments: comments,
	}
	svc.Cleanup = cleanup.New(hives, sensors, sensorData, files, comments)
	return svc
}

// Validate checks if all required repositories are initialized
func (s *HubService) Validate() error {
	if s.Hives == nil {
		return ErrMissingRepository("hives")
	}
	if s.Sensors == nil {
		return ErrMissingRepository("sensors")
	}
	if s.SensorData == nil {
		return ErrMissingRepository("sensorData")
	}
	if s.Files == nil {
		return ErrMissingRepository("files")
	}
	if s.HiveComments == nil {
		return ErrMissingRepository("hiveComments")
	}
	return nil
}

func ErrMissingRepository(name string) error {
	return errors.NewInternalError("missing repository: "+name, nil)
}
