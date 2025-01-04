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
	nuts "github.com/vaudience/go-nuts"
)

// Server represents our HTTP server
type Server struct {
	router *mux.Router
	config *config.Config
	srv    *http.Server
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
