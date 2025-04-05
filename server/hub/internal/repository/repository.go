// FilePath: server/hub/internal/repository/repository.go
package repository

import (
	"context"
	"errors"
	"io"
	"mime/multipart"
	"time"

	"github.com/itsatony/w4b_v3/server/hub/internal/database"
	"github.com/itsatony/w4b_v3/server/hub/internal/models"
)

var (
	// ErrNotFound indicates that a requested resource was not found
	ErrNotFound = errors.New("resource not found")
	// ErrDuplicate indicates that a resource already exists
	ErrDuplicate = errors.New("resource already exists")
	// ErrInvalidInput indicates that the input data is invalid
	ErrInvalidInput = errors.New("invalid input")
)

// HiveRepository defines the interface for hive data operations
type HiveRepository interface {
	database.Repository
	Create(ctx context.Context, hive *models.Hive) error
	Get(ctx context.Context, id string) (*models.Hive, error)
	Update(ctx context.Context, hive *models.Hive) error
	Delete(ctx context.Context, id string) error
	List(ctx context.Context, offset, limit int) ([]*models.Hive, error)
	UpdateLastSeen(ctx context.Context, id string, lastSeen time.Time) error
	UpdateLastSensorDataReceived(ctx context.Context, id string, lastReceived time.Time) error
	DeleteWithChildren(ctx context.Context, id string, tx database.Transaction) error
}

// SensorRepository defines the interface for sensor data operations
type SensorRepository interface {
	database.Repository
	Create(ctx context.Context, sensor *models.Sensor) error
	Get(ctx context.Context, id string) (*models.Sensor, error)
	Update(ctx context.Context, sensor *models.Sensor) error
	Delete(ctx context.Context, id string) error
	ListByHive(ctx context.Context, hiveID string) ([]*models.Sensor, error)
	UpdateLastValue(ctx context.Context, id string, value float64, timestamp time.Time) error
	DeleteWithData(ctx context.Context, id string, tx database.Transaction) error
	List(ctx context.Context, filters models.SensorFilters, page, limit int) (int64, []*models.Sensor, error)
}

// SensorDataRepository defines the interface for sensor measurements
type SensorDataRepository interface {
	database.Repository
	InsertReading(ctx context.Context, sensorID string, value float64, timestamp time.Time) error
	GetReadings(ctx context.Context, sensorID string, start, end time.Time) ([]models.SensorReading, error)
	GetAggregates(ctx context.Context, sensorID string, start, end time.Time, interval string) ([]models.SensorAggregate, error)
	DeleteOldData(ctx context.Context, before time.Time) error
	GetLatestReadingsBySensor(ctx context.Context, sensorID string) (*models.SensorReading, error)
	GetLatestReadingsByHiveID(ctx context.Context, hiveID string) (map[string]*models.SensorReading, error)
	DeleteBySensorID(ctx context.Context, sensorID string) error
	DeleteBySensorIDs(ctx context.Context, sensorIDs []string, tx database.Transaction) error
	DeleteByHiveID(ctx context.Context, hiveID string, tx database.Transaction) error
}

// FileRepository defines the interface for file storage operations
type FileRepository interface {
	Store(ctx context.Context, file *models.SensorFile, fileData *multipart.FileHeader) error
	Get(ctx context.Context, id string) (*models.SensorFile, error)
	Delete(ctx context.Context, id string) error
	ListByHive(ctx context.Context, hiveID string, fileType string) ([]*models.SensorFile, error)
	DeleteOldFiles(ctx context.Context, before time.Time) error
	GetLatestFiles(ctx context.Context, hiveID, sensorID string, fileTypes []string) ([]*models.SensorFile, error)
	StreamFile(ctx context.Context, file *models.SensorFile, w io.Writer) error
	DeleteByHiveID(ctx context.Context, hiveID string, tx database.Transaction) error
	DeleteBySensorID(ctx context.Context, sensorID string) error
	DeleteBySensorIDs(ctx context.Context, sensorIDs []string, tx database.Transaction) error
}

type HiveCommentRepository interface {
	database.Repository
	Create(ctx context.Context, comment *models.HiveComment) error
	Get(ctx context.Context, id string) (*models.HiveComment, error)
	List(ctx context.Context, hiveID string, offset, limit int) ([]*models.HiveComment, error)
	Delete(ctx context.Context, id string) error
	DeleteByHive(ctx context.Context, hiveID string) error
}
