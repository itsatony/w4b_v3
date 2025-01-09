// FilePath: server/hub/api/resources/api.resource.hives.go
package resources

import (
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/gorilla/mux"
	"github.com/itsatony/w4b_v3/server/hub/internal/errors"
	"github.com/itsatony/w4b_v3/server/hub/internal/hubservice"
	"github.com/itsatony/w4b_v3/server/hub/internal/models"
	nuts "github.com/vaudience/go-nuts"
)

// HiveHandlers encapsulates the hive-related HTTP handlers
type HiveHandlers struct {
	hubservice *hubservice.HubService
}

// @Summary Create a new hive
// @Description Create a new hive with the provided details
// @Tags hives
// @Accept json
// @Produce json
// @Param hive body models.Hive true "Hive details"
// @Success 201 {object} models.Hive
// @Failure 400 {object} errors.APIError
// @Failure 401 {object} errors.APIError
// @Router /hives [post]
// @Security BearerAuth
func (h *HiveHandlers) CreateHive(w http.ResponseWriter, r *http.Request) {
	var hive models.Hive
	requestID := nuts.NID("req", 12)

	if err := json.NewDecoder(r.Body).Decode(&hive); err != nil {
		respondWithError(w, errors.NewValidationError("invalid request body", err).WithRequestID(requestID))
		return
	}

	err := h.hubservice.CreateHive(r.Context(), &hive)
	if err != nil {
		respondWithError(w, errors.NewInternalError("failed to create hive", err).WithRequestID(requestID))
		return
	}

	respondWithJSON(w, http.StatusCreated, hive)
}

// @Summary Get a hive by ID
// @Description Get detailed information about a specific hive
// @Tags hives
// @Produce json
// @Param id path string true "Hive ID"
// @Success 200 {object} models.Hive
// @Failure 404 {object} errors.APIError
// @Router /hives/{id} [get]
func (h *HiveHandlers) GetHive(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]
	requestID := nuts.NID("req", 12)

	hive, err := h.hubservice.GetHive(r.Context(), id)
	if err != nil {
		respondWithError(w, errors.NewNotFoundError("hive not found", err).WithRequestID(requestID))
		return
	}

	respondWithJSON(w, http.StatusOK, hive)
}

// @Summary List hives
// @Description Get a paginated list of hives
// @Tags hives
// @Produce json
// @Param offset query int false "Offset for pagination"
// @Param limit query int false "Limit for pagination"
// @Success 200 {array} models.Hive
// @Router /hives [get]
func (h *HiveHandlers) ListHives(w http.ResponseWriter, r *http.Request) {
	requestID := nuts.NID("req", 12)
	offset, limit := getPaginationParams(r)

	hives, err := h.hubservice.ListHives(r.Context(), offset, limit)
	if err != nil {
		respondWithError(w, errors.NewInternalError("failed to list hives", err).WithRequestID(requestID))
		return
	}

	respondWithJSON(w, http.StatusOK, hives)
}

// @Summary Update a hive
// @Description Update an existing hive's details
// @Tags hives
// @Accept json
// @Produce json
// @Param id path string true "Hive ID"
// @Param hive body models.Hive true "Updated hive details"
// @Success 200 {object} models.Hive
// @Failure 400 {object} errors.APIError
// @Failure 404 {object} errors.APIError
// @Router /hives/{id} [put]
// @Security BearerAuth
func (h *HiveHandlers) UpdateHive(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]
	requestID := nuts.NID("req", 12)

	var hive models.Hive
	if err := json.NewDecoder(r.Body).Decode(&hive); err != nil {
		respondWithError(w, errors.NewValidationError("invalid request body", err).WithRequestID(requestID))
		return
	}

	hive.ID = id
	err := h.hubservice.UpdateHive(r.Context(), &hive)
	if err != nil {
		respondWithError(w, errors.NewInternalError("failed to update hive", err).WithRequestID(requestID))
		return
	}

	respondWithJSON(w, http.StatusOK, hive)
}

// @Summary Delete a hive
// @Description Delete a specific hive and all its associated data
// @Tags hives
// @Produce json
// @Param id path string true "Hive ID"
// @Success 204 "No Content"
// @Failure 404 {object} errors.APIError
// @Router /hives/{id} [delete]
// @Security BearerAuth
func (h *HiveHandlers) DeleteHive(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]
	requestID := nuts.NID("req", 12)

	err := h.hubservice.DeleteHive(r.Context(), id)
	if err != nil {
		respondWithError(w, errors.NewInternalError("failed to delete hive", err).WithRequestID(requestID))
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// @Summary Get hive status
// @Description Get the current status of a specific hive including sensor readings
// @Tags hives
// @Produce json
// @Param id path string true "Hive ID"
// @Success 200 {object} service.HiveStatus
// @Failure 404 {object} errors.APIError
// @Router /hives/{id}/status [get]
func (h *HiveHandlers) GetHiveStatus(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]
	requestID := nuts.NID("req", 12)

	status, err := h.hubservice.GetHiveStatus(r.Context(), id)
	if err != nil {
		respondWithError(w, errors.NewNotFoundError("hive not found", err).WithRequestID(requestID))
		return
	}

	respondWithJSON(w, http.StatusOK, status)
}

func (h *HiveHandlers) ListHiveComments(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]
	requestID := nuts.NID("req", 12)
	// TODO: Implement pagination
	offset := 0
	limit := 1000

	comments, err := h.hubservice.HiveComments.List(r.Context(), id, offset, limit)
	if err != nil {
		respondWithError(w, errors.NewInternalError("failed to list hive comments", err).WithRequestID(requestID))
		return
	}

	respondWithJSON(w, http.StatusOK, comments)
}

func (h *HiveHandlers) CreateHiveComment(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]
	requestID := nuts.NID("req", 12)

	var comment models.HiveComment
	if err := json.NewDecoder(r.Body).Decode(&comment); err != nil {
		respondWithError(w, errors.NewValidationError("invalid request body", err).WithRequestID(requestID))
		return
	}

	comment.HiveID = id
	err := h.hubservice.HiveComments.Create(r.Context(), &comment)
	if err != nil {
		respondWithError(w, errors.NewInternalError("failed to create hive comment", err).WithRequestID(requestID))
		return
	}

	respondWithJSON(w, http.StatusCreated, comment)
}

func (h *HiveHandlers) DeleteHiveComment(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	requestID := nuts.NID("req", 12)
	commentID := vars["commentId"]

	err := h.hubservice.HiveComments.Delete(r.Context(), commentID)
	if err != nil {
		respondWithError(w, errors.NewInternalError("failed to delete hive comment", err).WithRequestID(requestID))
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// Helper functions

func getPaginationParams(r *http.Request) (offset, limit int) {
	query := r.URL.Query()
	offset, _ = strconv.Atoi(query.Get("offset"))
	limit, _ = strconv.Atoi(query.Get("limit"))

	if limit <= 0 || limit > 100 {
		limit = 50 // Default limit
	}
	if offset < 0 {
		offset = 0
	}

	return offset, limit
}

func respondWithError(w http.ResponseWriter, err *errors.APIError) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(err.Code)
	json.NewEncoder(w).Encode(err)
	nuts.L.Errorf("[API] %s", err.Error())
}

func respondWithJSON(w http.ResponseWriter, code int, payload interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(payload)
}
