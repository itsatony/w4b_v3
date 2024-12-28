// hive-coordinator/main.go
package main

import (
	"encoding/json"
	"log"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	_ "github.com/lib/pq"
)

type HiveMetadata struct {
	ID            string    `json:"id"`
	Name          string    `json:"name"`
	Location      string    `json:"location"`
	ContactName   string    `json:"contact_name"`
	ContactPhone  string    `json:"contact_phone"`
	ContactEmail  string    `json:"contact_email"`
	SystemVersion string    `json:"system_version"`
	Timezone      string    `json:"timezone"`
	CreatedAt     time.Time `json:"created_at"`
	UpdatedAt     time.Time `json:"updated_at"`
	SSHPublicKey  string    `json:"ssh_public_key"`
	VPNConfig     string    `json:"vpn_config"`
}

type ImageConfig struct {
	HiveID      string            `json:"hive_id"`
	Services    map[string]bool   `json:"services"`
	Networks    map[string]string `json:"networks"`
	Credentials map[string]string `json:"credentials"`
}

func main() {
	r := chi.NewRouter()
	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)

	// API Routes
	r.Route("/api/v1", func(r chi.Router) {
		r.Post("/hives", createHive)
		r.Get("/hives", listHives)
		r.Get("/hives/{hiveID}", getHive)
		r.Put("/hives/{hiveID}", updateHive)
		r.Delete("/hives/{hiveID}", deleteHive)
		r.Post("/hives/{hiveID}/generate-image", generateImage)
	})

	log.Fatal(http.ListenAndServe(":3000", r))
}

func createHive(w http.ResponseWriter, r *http.Request) {
	var hive HiveMetadata
	if err := json.NewDecoder(r.Body).Decode(&hive); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	// Generate unique ID if not provided
	if hive.ID == "" {
		hive.ID = "hive_" + generateUniqueID()
	}

	// Validate and store hive metadata
	if err := validateAndStoreHive(&hive); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	// Generate SSH keys
	if err := generateSSHKeys(hive.ID); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	// Generate WireGuard config
	if err := generateWireGuardConfig(hive.ID); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(hive)
}

func generateImage(w http.ResponseWriter, r *http.Request) {
	hiveID := chi.URLParam(r, "hiveID")

	// Get hive metadata
	hive, err := getHiveMetadata(hiveID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}

	// Generate image configuration
	config := ImageConfig{
		HiveID: hiveID,
		Services: map[string]bool{
			"wireguard":   true,
			"ssh":         true,
			"timescaledb": true,
		},
		Networks: map[string]string{
			"vpn_address": generateVPNAddress(hiveID),
		},
		Credentials: map[string]string{
			"db_password": generateSecurePassword(),
			"ssh_key":     hive.SSHPublicKey,
		},
	}

	// Generate the image
	imagePath, err := generateRaspberryPiImage(config)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	// Return image download URL
	response := map[string]string{"image_url": "/download/" + imagePath}
	json.NewEncoder(w).Encode(response)
}

// Additional helper functions would be implemented here...
