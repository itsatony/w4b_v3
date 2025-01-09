package resources

import (
	"encoding/json"
	"net/http"
	"strconv"
	"time"

	"github.com/gorilla/mux"
	"github.com/itsatony/w4b_v3/server/hub/internal/errors"
	"github.com/itsatony/w4b_v3/server/hub/internal/hubservice"
	"github.com/itsatony/w4b_v3/server/hub/internal/models"
	nuts "github.com/vaudience/go-nuts"
)

// SensorHandlers encapsulates the sensor-related HTTP handlers
type SensorHandlers struct {
	hubservice *hubservice.HubService
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
	err := h.hubservice.CreateSensor(r.Context(), &sensor)
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

	readings, err := h.hubservice.GetSensorReadings(r.Context(), id, timeRange.start, timeRange.end, interval)
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
		err := h.hubservice.RecordSensorReading(r.Context(), reading.SensorID, reading.Value, reading.Timestamp)
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

	err := h.hubservice.CalibrateSensor(r.Context(), id, calibration)
	if err != nil {
		respondWithError(w, errors.NewInternalError("failed to calibrate sensor", err).WithRequestID(requestID))
		return
	}

	// Get updated sensor
	sensor, err := h.hubservice.GetSensor(r.Context(), id)
	if err != nil {
		respondWithError(w, errors.NewInternalError("failed to get updated sensor", err).WithRequestID(requestID))
		return
	}

	respondWithJSON(w, http.StatusOK, sensor)
}

// @Summary List sensors
// @Description Get a paginated list of sensors with optional filtering
// @Tags sensors
// @Produce json
// @Param hiveId query string false "Filter by hive ID"
// @Param type query string false "Filter by sensor type"
// @Param page query integer false "Page number (default: 1)"
// @Param limit query integer false "Items per page (default: 20, max: 100)"
// @Success 200 {object} PaginatedResponse[models.Sensor]
// @Failure 400 {object} errors.APIError
// @Router /sensors [get]
// @Security BearerAuth
func (h *SensorHandlers) ListSensors(w http.ResponseWriter, r *http.Request) {
	requestID := nuts.NID("req", 12)
	query := r.URL.Query()

	// Parse pagination parameters
	page, limit := parsePaginationParams(query)
	if limit > 100 {
		limit = 100
	}

	// Parse filters
	filters := models.SensorFilters{
		HiveID: getQueryParam(query, "hiveId"),
		Type:   models.SensorType(getQueryParam(query, "type")),
	}

	// Get total count and sensors
	total, sensors, err := h.hubservice.ListSensors(r.Context(), filters, page, limit)
	if err != nil {
		respondWithError(w, errors.NewInternalError("failed to list sensors", err).WithRequestID(requestID))
		return
	}

	totalPages := (total + int64(limit) - 1) / int64(limit)
	response := PaginatedResponse[models.Sensor]{
		Data:       convertSensorPointersToValues(sensors),
		Page:       page,
		Limit:      limit,
		TotalItems: total,
		TotalPages: totalPages,
	}

	respondWithJSON(w, http.StatusOK, response)
}

// @Summary Get a sensor
// @Description Get detailed information about a specific sensor
// @Tags sensors
// @Produce json
// @Param id path string true "Sensor ID"
// @Success 200 {object} models.Sensor
// @Failure 404 {object} errors.APIError
// @Router /sensors/{id} [get]
// @Security BearerAuth
func (h *SensorHandlers) GetSensor(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]
	requestID := nuts.NID("req", 12)

	sensor, err := h.hubservice.GetSensor(r.Context(), id)
	if err != nil {
		if errors.IsNotFound(err) {
			respondWithError(w, errors.NewNotFoundError("sensor not found", err).WithRequestID(requestID))
			return
		}
		respondWithError(w, errors.NewInternalError("failed to get sensor", err).WithRequestID(requestID))
		return
	}

	respondWithJSON(w, http.StatusOK, sensor)
}

// @Summary Update a sensor
// @Description Update sensor details
// @Tags sensors
// @Accept json
// @Produce json
// @Param id path string true "Sensor ID"
// @Param sensor body models.Sensor true "Updated sensor details"
// @Success 200 {object} models.Sensor
// @Failure 400 {object} errors.APIError
// @Failure 404 {object} errors.APIError
// @Router /sensors/{id} [put]
// @Security BearerAuth
func (h *SensorHandlers) UpdateSensor(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]
	requestID := nuts.NID("req", 12)

	// First, get the existing sensor
	existingSensor, err := h.hubservice.GetSensor(r.Context(), id)
	if err != nil {
		if errors.IsNotFound(err) {
			respondWithError(w, errors.NewNotFoundError("sensor not found", err).WithRequestID(requestID))
			return
		}
		respondWithError(w, errors.NewInternalError("failed to get sensor", err).WithRequestID(requestID))
		return
	}

	// Decode the update request
	var updateSensor models.Sensor
	if err := json.NewDecoder(r.Body).Decode(&updateSensor); err != nil {
		respondWithError(w, errors.NewValidationError("invalid request body", err).WithRequestID(requestID))
		return
	}

	// Ensure ID matches
	updateSensor.ID = id
	updateSensor.HiveID = existingSensor.HiveID // Prevent hive ID changes

	// Perform update
	err = h.hubservice.UpdateSensor(r.Context(), &updateSensor)
	if err != nil {
		if errors.IsValidation(err) {
			respondWithError(w, errors.NewValidationError("invalid sensor data", err).WithRequestID(requestID))
			return
		}
		respondWithError(w, errors.NewInternalError("failed to update sensor", err).WithRequestID(requestID))
		return
	}

	// Get the updated sensor
	updatedSensor, err := h.hubservice.GetSensor(r.Context(), id)
	if err != nil {
		respondWithError(w, errors.NewInternalError("failed to get updated sensor", err).WithRequestID(requestID))
		return
	}

	respondWithJSON(w, http.StatusOK, updatedSensor)
}

// @Summary Delete a sensor
// @Description Delete a sensor and its associated data
// @Tags sensors
// @Param id path string true "Sensor ID"
// @Success 204 "No Content"
// @Failure 404 {object} errors.APIError
// @Router /sensors/{id} [delete]
// @Security BearerAuth
func (h *SensorHandlers) DeleteSensor(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]
	requestID := nuts.NID("req", 12)

	// Check if sensor exists before attempting deletion
	_, err := h.hubservice.GetSensor(r.Context(), id)
	if err != nil {
		if errors.IsNotFound(err) {
			respondWithError(w, errors.NewNotFoundError("sensor not found", err).WithRequestID(requestID))
			return
		}
		respondWithError(w, errors.NewInternalError("failed to get sensor", err).WithRequestID(requestID))
		return
	}

	// Perform deletion
	err = h.hubservice.DeleteSensor(r.Context(), id)
	if err != nil {
		respondWithError(w, errors.NewInternalError("failed to delete sensor", err).WithRequestID(requestID))
		return
	}

	// Return 204 No Content for successful deletion
	w.WriteHeader(http.StatusNoContent)
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

// Helper type for paginated responses
type PaginatedResponse[T any] struct {
	Data       []T   `json:"data"`
	Page       int   `json:"page"`
	Limit      int   `json:"limit"`
	TotalItems int64 `json:"totalItems"`
	TotalPages int64 `json:"totalPages"`
}

// Helper function to convert []*models.Sensor to []models.Sensor
func convertSensorPointersToValues(sensorPointers []*models.Sensor) []models.Sensor {
	sensors := make([]models.Sensor, len(sensorPointers))
	for i, sensorPointer := range sensorPointers {
		sensors[i] = *sensorPointer
	}
	return sensors
}

// Helper function to parse pagination parameters
func parsePaginationParams(query map[string][]string) (page, limit int) {
	page = 1
	limit = 20

	if p, ok := query["page"]; ok && len(p) > 0 {
		if parsed, err := strconv.Atoi(p[0]); err == nil && parsed > 0 {
			page = parsed
		}
	}

	if l, ok := query["limit"]; ok && len(l) > 0 {
		if parsed, err := strconv.Atoi(l[0]); err == nil && parsed > 0 {
			limit = parsed
		}
	}

	return page, limit
}

// Helper function to get first value from query params
func getQueryParam(query map[string][]string, key string) string {
	if values, ok := query[key]; ok && len(values) > 0 {
		return values[0]
	}
	return ""
}
