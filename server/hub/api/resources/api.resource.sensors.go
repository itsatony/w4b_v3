package resources

import (
	"encoding/json"
	"net/http"
	"time"

	"github.com/gorilla/mux"
	"github.com/itsatony/w4b_v3/server/hub/internal/errors"
	"github.com/itsatony/w4b_v3/server/hub/internal/models"
	"github.com/itsatony/w4b_v3/server/hub/internal/service"
	nuts "github.com/vaudience/go-nuts"
)

// SensorHandlers encapsulates the sensor-related HTTP handlers
type SensorHandlers struct {
	service *service.Service
}

// @Summary Create a new sensor
// @Description Create a new sensor for a specific hive
// @Tags sensors
// @Accept json
// @Produce json
// @Param hiveId path string true "Hive ID"
// @Param sensor body models.Sensor true "Sensor details"
// @Success 201 {object} models.Sensor
// @Failure 400 {object} errors.APIError
// @Failure 401 {object} errors.APIError
// @Router /hives/{hiveId}/sensors [post]
// @Security BearerAuth
func (h *SensorHandlers) CreateSensor(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	hiveID := vars["hiveId"]
	requestID := nuts.NID("req", 12)

	var sensor models.Sensor
	if err := json.NewDecoder(r.Body).Decode(&sensor); err != nil {
		respondWithError(w, errors.NewValidationError("invalid request body", err).WithRequestID(requestID))
		return
	}

	sensor.HiveID = hiveID
	err := h.service.CreateSensor(r.Context(), &sensor)
	if err != nil {
		respondWithError(w, errors.NewInternalError("failed to create sensor", err).WithRequestID(requestID))
		return
	}

	respondWithJSON(w, http.StatusCreated, sensor)
}

// @Summary Get sensor readings
// @Description Get readings for a specific sensor with optional time range and aggregation
// @Tags sensors
// @Produce json
// @Param id path string true "Sensor ID"
// @Param start query string false "Start time (RFC3339)"
// @Param end query string false "End time (RFC3339)"
// @Param interval query string false "Aggregation interval (1min, 20min, 6hour, 1day)"
// @Success 200 {array} models.SensorAggregate
// @Router /sensors/{id}/readings [get]
func (h *SensorHandlers) GetSensorReadings(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]
	requestID := nuts.NID("req", 12)

	// Parse time range parameters
	timeRange := parseTimeRange(r)
	interval := r.URL.Query().Get("interval")
	if interval == "" {
		interval = determineDefaultInterval(timeRange.start, timeRange.end)
	}

	readings, err := h.service.GetSensorReadings(r.Context(), id, timeRange.start, timeRange.end, interval)
	if err != nil {
		respondWithError(w, errors.NewInternalError("failed to get sensor readings", err).WithRequestID(requestID))
		return
	}

	respondWithJSON(w, http.StatusOK, readings)
}

// @Summary Record sensor readings
// @Description Record new sensor readings from edge devices
// @Tags sensors
// @Accept json
// @Produce json
// @Param readings body []models.SensorReading true "Array of sensor readings"
// @Success 201 {object} map[string]string
// @Failure 400 {object} errors.APIError
// @Router /edge/readings [post]
// @Security BearerAuth
func (h *SensorHandlers) RecordReadings(w http.ResponseWriter, r *http.Request) {
	requestID := nuts.NID("req", 12)

	var readings []models.SensorReading
	if err := json.NewDecoder(r.Body).Decode(&readings); err != nil {
		respondWithError(w, errors.NewValidationError("invalid request body", err).WithRequestID(requestID))
		return
	}

	// Record each reading
	for _, reading := range readings {
		err := h.service.RecordSensorReading(r.Context(), reading.SensorID, reading.Value, reading.Timestamp)
		if err != nil {
			nuts.L.Warnf("[SensorHandler] Failed to record reading for sensor %s: %v", reading.SensorID, err)
			// Continue with other readings even if one fails
			continue
		}
	}

	respondWithJSON(w, http.StatusCreated, map[string]string{"status": "ok"})
}

// @Summary Calibrate sensor
// @Description Update sensor calibration settings
// @Tags sensors
// @Accept json
// @Produce json
// @Param id path string true "Sensor ID"
// @Param calibration body models.CalibrationInfo true "Calibration information"
// @Success 200 {object} models.Sensor
// @Failure 400 {object} errors.APIError
// @Router /sensors/{id}/calibration [post]
// @Security BearerAuth
func (h *SensorHandlers) CalibrateSensor(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]
	requestID := nuts.NID("req", 12)

	var calibration models.CalibrationInfo
	if err := json.NewDecoder(r.Body).Decode(&calibration); err != nil {
		respondWithError(w, errors.NewValidationError("invalid request body", err).WithRequestID(requestID))
		return
	}

	err := h.service.CalibrateSensor(r.Context(), id, calibration)
	if err != nil {
		respondWithError(w, errors.NewInternalError("failed to calibrate sensor", err).WithRequestID(requestID))
		return
	}

	// Get updated sensor
	sensor, err := h.service.GetSensor(r.Context(), id)
	if err != nil {
		respondWithError(w, errors.NewInternalError("failed to get updated sensor", err).WithRequestID(requestID))
		return
	}

	respondWithJSON(w, http.StatusOK, sensor)
}

// Helper functions and types

type timeRange struct {
	start time.Time
	end   time.Time
}

func parseTimeRange(r *http.Request) timeRange {
	query := r.URL.Query()
	now := time.Now()

	// Parse start time
	start := now.Add(-24 * time.Hour) // Default to last 24 hours
	if startStr := query.Get("start"); startStr != "" {
		if parsed, err := time.Parse(time.RFC3339, startStr); err == nil {
			start = parsed
		}
	}

	// Parse end time
	end := now
	if endStr := query.Get("end"); endStr != "" {
		if parsed, err := time.Parse(time.RFC3339, endStr); err == nil {
			end = parsed
		}
	}

	return timeRange{start: start, end: end}
}

func determineDefaultInterval(start, end time.Time) string {
	duration := end.Sub(start)
	switch {
	case duration <= 30*time.Hour:
		return "1min"
	case duration <= 70*24*time.Hour:
		return "20min"
	case duration <= 13*30*24*time.Hour:
		return "6hour"
	default:
		return "1day"
	}
}
