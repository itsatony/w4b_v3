// FilePath: server/hub/internal/repository/files/files.storage.go
package files

import (
	"context"
	"fmt"
	"io"
	"mime/multipart"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/itsatony/w4b_v3/server/hub/internal/errors"
	"github.com/itsatony/w4b_v3/server/hub/internal/models"
	nuts "github.com/vaudience/go-nuts"
)

const (
	maxFileSize        = 100 * 1024 * 1024 // 100MB
	defaultPermissions = 0755
	soundFileExtension = ".wav"
	imageFileExtension = ".jpg"
	defaultDateFormat  = "20060102_150405"
)

// FileConfig holds configuration for the file storage
type FileConfig struct {
	BasePath    string
	AllowedMime map[string][]string // map[fileType][]allowedMimeTypes
}

// FileRepo implements the FileRepository interface
type FileRepo struct {
	config FileConfig
}

// NewFileRepository creates a new file storage repository
func NewFileRepository(config FileConfig) (*FileRepo, error) {
	if err := createDirectoryIfNotExists(config.BasePath); err != nil {
		return nil, err
	}
	return &FileRepo{config: config}, nil
}

func (r *FileRepo) Store(ctx context.Context, file *models.SensorFile, fileData *multipart.FileHeader) error {
	// Validate file size
	if fileData.Size > maxFileSize {
		return errors.NewValidationError("file size exceeds maximum allowed size", nil)
	}

	// Validate mime type
	if !r.isAllowedMimeType(file.FileType, file.MimeType) {
		return errors.NewValidationError("unsupported file type", nil)
	}

	// Generate file path
	filePath, err := r.generateFilePath(file)
	if err != nil {
		return err
	}
	file.FilePath = filePath

	// Create directory structure
	dirPath := filepath.Dir(filePath)
	if err := createDirectoryIfNotExists(dirPath); err != nil {
		return err
	}

	// Open source file
	src, err := fileData.Open()
	if err != nil {
		return errors.NewInternalError("failed to open source file", err)
	}
	defer src.Close()

	// Create destination file
	dst, err := os.Create(filepath.Join(r.config.BasePath, filePath))
	if err != nil {
		return errors.NewInternalError("failed to create destination file", err)
	}
	defer dst.Close()

	// Copy file
	if _, err = io.Copy(dst, src); err != nil {
		return errors.NewInternalError("failed to copy file", err)
	}

	nuts.L.Infof("[FileRepo] Stored file: %s", filePath)
	return nil
}

func (r *FileRepo) Get(ctx context.Context, id string) (*models.SensorFile, error) {
	// In a real implementation, this would likely query a database
	// to get the file metadata. For now, we'll just check if the file exists
	files, err := r.ListByHive(ctx, "", "")
	if err != nil {
		return nil, err
	}

	for _, file := range files {
		if file.ID == id {
			return file, nil
		}
	}

	return nil, errors.NewNotFoundError("file not found", nil)
}

func (r *FileRepo) ListByHive(ctx context.Context, hiveID string, fileType string) ([]*models.SensorFile, error) {
	var files []*models.SensorFile
	basePath := filepath.Join(r.config.BasePath, hiveID)

	err := filepath.Walk(basePath, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if info.IsDir() {
			return nil
		}

		relPath, err := filepath.Rel(r.config.BasePath, path)
		if err != nil {
			return err
		}

		if fileType != "" && !strings.Contains(path, fileType) {
			return nil
		}

		file := &models.SensorFile{
			ID:        filepath.Base(path),
			HiveID:    hiveID,
			FilePath:  relPath,
			FileSize:  info.Size(),
			FileType:  determineFileType(path),
			Timestamp: info.ModTime(),
			CreatedAt: info.ModTime(),
		}
		files = append(files, file)
		return nil
	})

	if err != nil {
		return nil, errors.NewInternalError("failed to list files", err)
	}

	return files, nil
}

func (r *FileRepo) Delete(ctx context.Context, id string) error {
	file, err := r.Get(ctx, id)
	if err != nil {
		return err
	}

	err = os.Remove(filepath.Join(r.config.BasePath, file.FilePath))
	if err != nil {
		return errors.NewInternalError("failed to delete file", err)
	}

	return nil
}

func (r *FileRepo) DeleteOldFiles(ctx context.Context, before time.Time) error {
	var deletedCount int
	err := filepath.Walk(r.config.BasePath, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if info.IsDir() {
			return nil
		}
		if info.ModTime().Before(before) {
			if err := os.Remove(path); err != nil {
				nuts.L.Errorf("[FileRepo] Failed to delete old file %s: %v", path, err)
				return nil
			}
			deletedCount++
		}
		return nil
	})

	if err != nil {
		return errors.NewInternalError("failed to delete old files", err)
	}

	nuts.L.Infof("[FileRepo] Deleted %d files older than %v", deletedCount, before)
	return nil
}

func (r *FileRepo) generateFilePath(file *models.SensorFile) (string, error) {
	timestamp := file.Timestamp.Format(defaultDateFormat)
	var ext string
	switch file.FileType {
	case "sound":
		ext = soundFileExtension
	case "image":
		ext = imageFileExtension
	default:
		return "", errors.NewValidationError("unsupported file type", nil)
	}

	filename := fmt.Sprintf("%s_%s_%s_%s%s",
		timestamp,
		file.HiveID,
		file.SensorID,
		file.FileType,
		ext,
	)

	return filepath.Join(
		file.HiveID,
		file.SensorID,
		file.FileType,
		filename,
	), nil
}

func (r *FileRepo) isAllowedMimeType(fileType, mimeType string) bool {
	allowedTypes, exists := r.config.AllowedMime[fileType]
	if !exists {
		return false
	}
	for _, allowed := range allowedTypes {
		if allowed == mimeType {
			return true
		}
	}
	return false
}

func determineFileType(path string) string {
	ext := strings.ToLower(filepath.Ext(path))
	switch ext {
	case soundFileExtension:
		return "sound"
	case imageFileExtension:
		return "image"
	default:
		return "unknown"
	}
}

func createDirectoryIfNotExists(path string) error {
	if _, err := os.Stat(path); os.IsNotExist(err) {
		err := os.MkdirAll(path, defaultPermissions)
		if err != nil {
			return errors.NewInternalError("failed to create directory", err)
		}
	}
	return nil
}

// StreamFile implements the streaming of a file to an io.Writer
func (r *FileRepo) StreamFile(ctx context.Context, file *models.SensorFile, w io.Writer) error {
	filePath := filepath.Join(r.config.BasePath, file.FilePath)
	f, err := os.Open(filePath)
	if err != nil {
		return errors.NewInternalError("failed to open file", err)
	}
	defer f.Close()

	_, err = io.Copy(w, f)
	if err != nil {
		return errors.NewInternalError("failed to stream file", err)
	}

	return nil
}
