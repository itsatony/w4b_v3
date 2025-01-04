package resources

import (
	"fmt"
	"mime/multipart"
	"net/http"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/gorilla/mux"
	"github.com/itsatony/w4b_v3/server/hub/internal/errors"
	"github.com/itsatony/w4b_v3/server/hub/internal/models"
	"github.com/itsatony/w4b_v3/server/hub/internal/service"
	nuts "github.com/vaudience/go-nuts"
)

// FileHandlers encapsulates the file-related HTTP handlers
type FileHandlers struct {
	service *service.Service
	config  FileConfig
}

type FileConfig struct {
	MaxFileSize    int64    // Maximum file size in bytes
	AllowedTypes   []string // Allowed MIME types
	StoragePath    string   // Base path for file storage
	AllowedFormats []string // Allowed file extensions
}

// @Summary Upload a sensor file
// @Description Upload an image or sound file from a sensor
// @Tags files
// @Accept multipart/form-data
// @Produce json
// @Param hiveId path string true "Hive ID"
// @Param sensorId path string true "Sensor ID"
// @Param file formData file true "File to upload"
// @Success 201 {object} models.SensorFile
// @Failure 400 {object} errors.APIError
// @Failure 413 {object} errors.APIError
// @Router /hives/{hiveId}/sensors/{sensorId}/files [post]
// @Security BearerAuth
func (h *FileHandlers) UploadFile(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	requestID := nuts.NID("req", 12)
	hiveID := vars["hiveId"]
	sensorID := vars["sensorId"]

	// Parse multipart form
	err := r.ParseMultipartForm(h.config.MaxFileSize)
	if err != nil {
		respondWithError(w, errors.NewValidationError("file too large", err).WithRequestID(requestID))
		return
	}

	file, header, err := r.FormFile("file")
	if err != nil {
		respondWithError(w, errors.NewValidationError("invalid file upload", err).WithRequestID(requestID))
		return
	}
	defer file.Close()

	// Validate file
	if err := h.validateFile(header); err != nil {
		respondWithError(w, err.WithRequestID(requestID))
		return
	}

	// Generate file metadata
	fileType := determineFileType(header.Filename)
	fileName := generateFileName(hiveID, sensorID, fileType, filepath.Ext(header.Filename))

	// Create sensor file record
	sensorFile := &models.SensorFile{
		ID:        nuts.NID("sf", 12),
		HiveID:    hiveID,
		SensorID:  sensorID,
		FileName:  fileName,
		FileType:  fileType,
		FileSize:  header.Size,
		MimeType:  header.Header.Get("Content-Type"),
		CreatedAt: time.Now(),
	}

	// Store file
	err = h.service.StoreFile(r.Context(), sensorFile, file)
	if err != nil {
		respondWithError(w, errors.NewInternalError("failed to store file", err).WithRequestID(requestID))
		return
	}

	respondWithJSON(w, http.StatusCreated, sensorFile)
}

// @Summary Get a sensor file
// @Description Download a specific sensor file
// @Tags files
// @Produce application/octet-stream
// @Param id path string true "File ID"
// @Success 200 {file} file
// @Failure 404 {object} errors.APIError
// @Router /files/{id} [get]
func (h *FileHandlers) GetFile(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	requestID := nuts.NID("req", 12)
	fileID := vars["id"]

	file, err := h.service.GetFile(r.Context(), fileID)
	if err != nil {
		respondWithError(w, errors.NewNotFoundError("file not found", err).WithRequestID(requestID))
		return
	}

	// Set appropriate headers
	w.Header().Set("Content-Type", file.MimeType)
	w.Header().Set("Content-Disposition", fmt.Sprintf("attachment; filename=%s", file.FileName))
	w.Header().Set("Content-Length", strconv.FormatInt(file.FileSize, 10))

	// Stream file
	if err := h.service.StreamFile(r.Context(), file, w); err != nil {
		nuts.L.Errorf("[FileHandler] Failed to stream file %s: %v", fileID, err)
		return
	}
}

// @Summary Delete a sensor file
// @Description Delete a specific sensor file
// @Tags files
// @Param id path string true "File ID"
// @Success 204 "No Content"
// @Failure 404 {object} errors.APIError
// @Router /files/{id} [delete]
// @Security BearerAuth
func (h *FileHandlers) DeleteFile(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	requestID := nuts.NID("req", 12)
	fileID := vars["id"]

	err := h.service.DeleteFile(r.Context(), fileID)
	if err != nil {
		respondWithError(w, errors.NewInternalError("failed to delete file", err).WithRequestID(requestID))
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// @Summary List hive files
// @Description Get a list of files for a specific hive
// @Tags files
// @Produce json
// @Param hiveId path string true "Hive ID"
// @Param type query string false "File type filter (image/sound)"
// @Success 200 {array} models.SensorFile
// @Router /hives/{hiveId}/files [get]
func (h *FileHandlers) ListHiveFiles(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	requestID := nuts.NID("req", 12)
	hiveID := vars["hiveId"]
	fileType := r.URL.Query().Get("type")

	files, err := h.service.ListHiveFiles(r.Context(), hiveID, fileType)
	if err != nil {
		respondWithError(w, errors.NewInternalError("failed to list files", err).WithRequestID(requestID))
		return
	}

	respondWithJSON(w, http.StatusOK, files)
}

// Helper functions

func (h *FileHandlers) validateFile(header *multipart.FileHeader) *errors.APIError {
	// Check file size
	if header.Size > h.config.MaxFileSize {
		return errors.NewValidationError(
			fmt.Sprintf("file size exceeds maximum allowed size of %d bytes", h.config.MaxFileSize),
			nil,
		)
	}

	// Check file type
	ext := strings.ToLower(filepath.Ext(header.Filename))
	if !contains(h.config.AllowedFormats, ext) {
		return errors.NewValidationError(
			fmt.Sprintf("file format %s not allowed", ext),
			nil,
		)
	}

	// Check MIME type
	if !contains(h.config.AllowedTypes, header.Header.Get("Content-Type")) {
		return errors.NewValidationError(
			fmt.Sprintf("MIME type %s not allowed", header.Header.Get("Content-Type")),
			nil,
		)
	}

	return nil
}

func determineFileType(filename string) string {
	ext := strings.ToLower(filepath.Ext(filename))
	switch ext {
	case ".jpg", ".jpeg", ".png":
		return "image"
	case ".wav", ".mp3":
		return "sound"
	default:
		return "other"
	}
}

func generateFileName(hiveID, sensorID, fileType, ext string) string {
	timestamp := time.Now().UTC().Format("20060102T150405Z")
	return fmt.Sprintf("%s_%s_%s_%s%s", timestamp, hiveID, sensorID, fileType, ext)
}

func contains(slice []string, item string) bool {
	for _, s := range slice {
		if s == item {
			return true
		}
	}
	return false
}
