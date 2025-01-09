// FilePath: server/hub/api/resources/resources.go
package resources

import (
	"net/http"

	"github.com/itsatony/w4b_v3/server/hub/internal/hubservice"
)

// Resources holds all HTTP resource handlers
type Resources struct {
	Hives       *HiveHandlers
	Sensors     *SensorHandlers
	Files       *FileHandlers
	HealthCheck func(w http.ResponseWriter, r *http.Request)
	Metrics     func(w http.ResponseWriter, r *http.Request)
}

// NewResources creates a new Resources instance
func NewResources(svc *hubservice.HubService) *Resources {
	return &Resources{
		Hives:   &HiveHandlers{hubservice: svc},
		Sensors: &SensorHandlers{hubservice: svc},
		Files:   &FileHandlers{hubservice: svc},
	}
}

// SetHealthCheck sets the health check handler
func (r *Resources) SetHealthCheck(h func(w http.ResponseWriter, r *http.Request)) {
	r.HealthCheck = h
}

// SetMetrics sets the metrics handler
func (r *Resources) SetMetrics(h func(w http.ResponseWriter, r *http.Request)) {
	r.Metrics = h
}
