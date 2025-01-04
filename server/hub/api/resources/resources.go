// FilePath: server/hub/api/resources/resources.go
package resources

import "github.com/itsatony/w4b_v3/server/hub/internal/service"

// Resources holds all HTTP resource handlers
type Resources struct {
	Hives   *HiveHandlers
	Sensors *SensorHandlers
	Files   *FileHandlers
}

// NewResources creates a new Resources instance
func NewResources(svc *service.Service) *Resources {
	return &Resources{
		Hives:   &HiveHandlers{service: svc},
		Sensors: &SensorHandlers{service: svc},
		Files:   &FileHandlers{service: svc},
	}
}
