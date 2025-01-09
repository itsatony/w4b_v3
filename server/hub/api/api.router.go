package api

import (
	"net/http"

	"github.com/gorilla/mux"
	"github.com/itsatony/w4b_v3/server/hub/api/middleware"
	"github.com/itsatony/w4b_v3/server/hub/api/resources"
	"github.com/itsatony/w4b_v3/server/hub/internal/hubservice"
)

type Router struct {
	router    *mux.Router
	auth      *middleware.KeycloakMiddleware
	resources *resources.Resources
}

func NewRouter(svc *hubservice.HubService, keycloakConfig middleware.KeycloakConfig) *Router {
	r := &Router{
		router:    mux.NewRouter(),
		auth:      middleware.NewKeycloakMiddleware(keycloakConfig),
		resources: resources.NewResources(svc),
	}

	r.setupRoutes()
	return r
}

func (r *Router) setupRoutes() {
	// API version prefix
	api := r.router.PathPrefix("/api/v1").Subrouter()

	// Public routes
	api.HandleFunc("/health", r.resources.HealthCheck).Methods(http.MethodGet)
	api.HandleFunc("/metrics", r.resources.Metrics).Methods(http.MethodGet)

	// Protected routes
	protected := api.PathPrefix("").Subrouter()
	protected.Use(r.auth.Authenticate)

	// Hives
	hives := protected.PathPrefix("/hives").Subrouter()
	hives.HandleFunc("", r.resources.Hives.ListHives).Methods(http.MethodGet)
	hives.HandleFunc("", r.resources.Hives.CreateHive).Methods(http.MethodPost)
	hives.HandleFunc("/{id}", r.resources.Hives.GetHive).Methods(http.MethodGet)
	hives.HandleFunc("/{id}", r.resources.Hives.UpdateHive).Methods(http.MethodPut)
	hives.HandleFunc("/{id}", r.resources.Hives.DeleteHive).Methods(http.MethodDelete)
	hives.HandleFunc("/{id}/status", r.resources.Hives.GetHiveStatus).Methods(http.MethodGet)
	hives.HandleFunc("/{id}/comments", r.resources.Hives.ListHiveComments).Methods(http.MethodGet)
	hives.HandleFunc("/{id}/comments", r.resources.Hives.CreateHiveComment).Methods(http.MethodPost)

	// Sensors
	sensors := protected.PathPrefix("/sensors").Subrouter()
	sensors.HandleFunc("", r.resources.Sensors.ListSensors).Methods(http.MethodGet)
	sensors.HandleFunc("", r.resources.Sensors.CreateSensor).Methods(http.MethodPost)
	sensors.HandleFunc("/{id}", r.resources.Sensors.GetSensor).Methods(http.MethodGet)
	sensors.HandleFunc("/{id}", r.resources.Sensors.UpdateSensor).Methods(http.MethodPut)
	sensors.HandleFunc("/{id}", r.resources.Sensors.DeleteSensor).Methods(http.MethodDelete)
	sensors.HandleFunc("/{id}/readings", r.resources.Sensors.GetSensorReadings).Methods(http.MethodGet)
	sensors.HandleFunc("/{id}/calibration", r.resources.Sensors.CalibrateSensor).Methods(http.MethodPost)

	// Files
	files := protected.PathPrefix("/files").Subrouter()
	files.HandleFunc("", r.resources.Files.UploadFile).Methods(http.MethodPost)
	files.HandleFunc("/{id}", r.resources.Files.GetFile).Methods(http.MethodGet)
	files.HandleFunc("/{id}", r.resources.Files.DeleteFile).Methods(http.MethodDelete)
}

func (r *Router) ServeHTTP(w http.ResponseWriter, req *http.Request) {
	r.router.ServeHTTP(w, req)
}
