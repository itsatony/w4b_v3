// FilePath: server/hub/internal/server/server.go
package server

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"

	"github.com/gorilla/mux"
	"github.com/itsatony/w4b_v3/server/hub/internal/config"
	"github.com/itsatony/w4b_v3/server/hub/internal/hubservice"
	"github.com/itsatony/w4b_v3/server/hub/internal/monitoring"
	"github.com/itsatony/w4b_v3/server/hub/internal/repository"
	"github.com/jmoiron/sqlx"
	nuts "github.com/vaudience/go-nuts"
)

// Server represents our HTTP server
type Server struct {
	router     *mux.Router
	config     *config.Config
	srv        *http.Server
	hubservice *hubservice.HubService
	monitoring *monitoring.Service
}

// New creates a new server instance
func New(cfg *config.Config) *Server {
	router := mux.NewRouter()

	srv := &http.Server{
		Addr:         fmt.Sprintf("%s:%d", cfg.Server.Host, cfg.Server.Port),
		Handler:      router,
		ReadTimeout:  cfg.Server.ReadTimeout,
		WriteTimeout: cfg.Server.WriteTimeout,
	}

	return &Server{
		router: router,
		config: cfg,
		srv:    srv,
	}
}

// Start begins listening for requests
func (s *Server) Start() error {
	// Initialize services
	s.hubservice = initializeHubService(s.config)
	s.monitoring = monitoring.NewService(monitoring.Config{
		PrometheusEndpoint: s.config.Monitoring.PrometheusEndpoint,
		LokiEndpoint:       s.config.Monitoring.LokiEndpoint,
	})

	// Set up cleanup event handlers
	s.setupCleanupHandlers()

	// Setup routes
	s.setupRoutes()

	// Start server
	go func() {
		nuts.L.Infof("[Server] Starting server on %s", s.srv.Addr)
		if err := s.srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			nuts.L.Errorf("[Server] Error starting server: %v", err)
			os.Exit(1)
		}
	}()

	return s.waitForShutdown()
}

// waitForShutdown waits for interrupt signal and gracefully shuts down the server
func (s *Server) waitForShutdown() error {
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	nuts.L.Infof("[Server] Shutting down server...")

	ctx, cancel := context.WithTimeout(context.Background(), s.config.Server.ShutdownTimeout)
	defer cancel()

	if err := s.srv.Shutdown(ctx); err != nil {
		return fmt.Errorf("error shutting down server: %w", err)
	}

	nuts.L.Infof("[Server] Server shut down successfully")
	return nil
}

// setupRoutes configures all routes for the server
func (s *Server) setupRoutes() {
	// API version prefix
	v1 := s.router.PathPrefix("/v1").Subrouter()

	// Public routes
	v1.HandleFunc("/health", s.handleHealth()).Methods(http.MethodGet)

	// Protected routes will be added here
}

// handleHealth returns a simple health check handler
func (s *Server) handleHealth() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"ok","version":"` + nuts.GetVersion() + `"}`))
	}
}

func (s *Server) setupCleanupHandlers() {
	// Handle hive deletion events
	s.hubservice.Cleanup.OnCleanup("hive.deleted", func(id string) {
		nuts.L.Infof("[Cleanup] Hive %s and all associated data deleted", id)
		s.monitoring.RecordEvent("hive_deletion", map[string]string{
			"hive_id": id,
		})
	})

	// Handle sensor deletion events
	s.hubservice.Cleanup.OnCleanup("sensor.deleted", func(id string) {
		nuts.L.Infof("[Cleanup] Sensor %s and all associated data deleted", id)
		s.monitoring.RecordEvent("sensor_deletion", map[string]string{
			"sensor_id": id,
		})
	})

	// Handle file deletion events
	s.hubservice.Cleanup.OnCleanup("file.deleted", func(id string) {
		nuts.L.Infof("[Cleanup] File %s deleted", id)
		s.monitoring.RecordEvent("file_deletion", map[string]string{
			"file_id": id,
		})
	})

	// Handle comments deletion events
	s.hubservice.Cleanup.OnCleanup("comments.deleted", func(id string) {
		nuts.L.Infof("[Cleanup] All comments for hive %s deleted", id)
		s.monitoring.RecordEvent("comments_deletion", map[string]string{
			"hive_id": id,
		})
	})
}

// initializeHubService creates and configures the hub service
func initializeHubService(cfg *config.Config) *hubservice.HubService {
	// Initialize database connections
	tsdb := initTimescaleDB(cfg.Database.TimescaleDB)
	appDB := initAppDB(cfg.Database.AppDB)

	// Initialize repositories
	hives := repository.NewHiveRepository(appDB)
	sensors := repository.NewSensorRepository(appDB)
	sensorData := repository.NewSensorDataRepository(tsdb)

	files, err := repository.NewFileRepository(cfg.FileStore)
	if err != nil {
		nuts.L.Fatalf("[Server] Failed to initialize file repository: %v", err)
	}

	comments := repository.NewHiveCommentRepository(appDB)

	// Create and return hub service
	return hubservice.New(hives, sensors, sensorData, files, comments)
}

func initTimescaleDB(cfg config.PostgresConfig) *sqlx.DB {
	connStr := fmt.Sprintf(
		"host=%s port=%d user=%s password=%s dbname=%s sslmode=%s",
		cfg.Host, cfg.Port, cfg.User, cfg.Password, cfg.DBName, cfg.SSLMode,
	)

	db, err := sqlx.Connect("postgres", connStr)
	if err != nil {
		nuts.L.Fatalf("[Server] Failed to connect to TimescaleDB: %v", err)
	}
	return db
}

func initAppDB(cfg config.PostgresConfig) *sqlx.DB {
	connStr := fmt.Sprintf(
		"host=%s port=%d user=%s password=%s dbname=%s sslmode=%s",
		cfg.Host, cfg.Port, cfg.User, cfg.Password, cfg.DBName, cfg.SSLMode,
	)

	db, err := sqlx.Connect("postgres", connStr)
	if err != nil {
		nuts.L.Fatalf("[Server] Failed to connect to Application DB: %v", err)
	}
	return db
}
