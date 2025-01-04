package api

import (
	"net/http"

	"github.com/gorilla/mux"
	"github.com/itsatony/w4b_v3/server/hub/api/middleware"
	"github.com/itsatony/w4b_v3/server/hub/api/resources"
	"github.com/itsatony/w4b_v3/server/hub/internal/service"
)

type Router struct {
	router    *mux.Router
	auth      *middleware.KeycloakMiddleware
	resources *resources.Resources
}

func NewRouter(svc *service.Service, keycloakConfig middleware.KeycloakConfig) *Router {
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
	hives.HandleFunc("", r.resources.ListHives).Methods(http.MethodGet)
	hives.HandleFunc("", r.resources.CreateHive).Methods(http.MethodPost)
	hives.HandleFunc("/{id}", r.resources.GetHive).Methods(http.MethodGet)
	hives.HandleFunc("/{id}", r.resources.UpdateHive).Methods(http.MethodPut)
	hives.HandleFunc("/{id}", r.resources.DeleteHive).Methods(http.MethodDelete)
	hives.HandleFunc("/{id}/status", r.resources.GetHiveStatus).Methods(http.MethodGet)
	hives.HandleFunc("/{id}/comments", r.resources.ListHiveComments).Methods(http.MethodGet)
	hives.HandleFunc("/{id}/comments", r.resources.AddHiveComment).Methods(http.MethodPost)

	// Sensors
	sensors := protected.PathPrefix("/sensors").Subrouter()
	sensors.HandleFunc("", r.resources.ListSensors).Methods(http.MethodGet)
	sensors.HandleFunc("", r.resources.CreateSensor).Methods(http.MethodPost)
	sensors.HandleFunc("/{id}", r.resources.GetSensor).Methods(http.MethodGet)
	sensors.HandleFunc("/{id}", r.resources.UpdateSensor).Methods(http.MethodPut)
	sensors.HandleFunc("/{id}", r.resources.DeleteSensor).Methods(http.MethodDelete)
	sensors.HandleFunc("/{id}/readings", r.resources.GetSensorReadings).Methods(http.MethodGet)
	sensors.HandleFunc("/{id}/calibration", r.resources.CalibrateSensor).Methods(http.MethodPost)

	// Files
	files := protected.PathPrefix("/files").Subrouter()
	files.HandleFunc("", r.resources.UploadFile).Methods(http.MethodPost)
	files.HandleFunc("/{id}", r.resources.GetFile).Methods(http.MethodGet)
	files.HandleFunc("/{id}", r.resources.DeleteFile).Methods(http.MethodDelete)

	// Edge device specific routes (requires edgedevice role)
	edge := protected.PathPrefix("/edge").Subrouter()
	edge.Use(r.auth.RequireRoles([]string{"edgedevice"}))
	edge.HandleFunc("/readings", r.resources.RecordReadings).Methods(http.MethodPost)
	edge.HandleFunc("/status", r.resources.UpdateEdgeStatus).Methods(http.MethodPost)
}

func (r *Router) ServeHTTP(w http.ResponseWriter, req *http.Request) {
	r.router.ServeHTTP(w, req)
}
