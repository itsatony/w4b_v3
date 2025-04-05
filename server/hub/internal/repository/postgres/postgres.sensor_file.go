// FilePath: server/hub/internal/repository/postgres/postgres.sensor_file.go
package postgres

import (
	"context"
	"database/sql"
	"time"

	"github.com/itsatony/w4b_v3/server/hub/internal/database"
	"github.com/itsatony/w4b_v3/server/hub/internal/errors"
	"github.com/itsatony/w4b_v3/server/hub/internal/models"
	"github.com/lib/pq"
	nuts "github.com/vaudience/go-nuts"
)

type SensorFileRepo struct {
	db database.DB
}

func NewSensorFileRepository(db database.DB) *SensorFileRepo {
	repo := &SensorFileRepo{db: db}
	repo.initializeSchema()
	return repo
}

func (r *SensorFileRepo) Create(ctx context.Context, file *models.SensorFile) error {
	query := `
		INSERT INTO sensor_files (
			id, hive_id, sensor_id, type, path,
			size, mime_type, timestamp, created_at
		) VALUES (
			:id, :hive_id, :sensor_id, :type, :path,
			:size, :mime_type, :timestamp, :created_at
		)`

	_, err := r.db.GetDB().NamedExecContext(ctx, query, file)
	if err != nil {
		if pqErr, ok := err.(*pq.Error); ok && pqErr.Code == "23503" {
			return errors.NewValidationError("hive or sensor not found", err)
		}
		return errors.NewDatabaseError("failed to create file record", err)
	}
	return nil
}

func (r *SensorFileRepo) Get(ctx context.Context, id string) (*models.SensorFile, error) {
	file := &models.SensorFile{}
	query := `SELECT * FROM sensor_files WHERE id = $1`

	err := r.db.GetDB().GetContext(ctx, file, query, id)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, errors.NewNotFoundError("file not found", err)
		}
		return nil, errors.NewDatabaseError("failed to get file", err)
	}
	return file, nil
}

func (r *SensorFileRepo) ListByHive(ctx context.Context, hiveID string, fileType string, limit, offset int) ([]*models.SensorFile, error) {
	files := []*models.SensorFile{}
	var query string
	var args []interface{}

	if fileType != "" {
		query = `
			SELECT * FROM sensor_files 
			WHERE hive_id = $1 AND type = $2
			ORDER BY timestamp DESC
			LIMIT $3 OFFSET $4`
		args = []interface{}{hiveID, fileType, limit, offset}
	} else {
		query = `
			SELECT * FROM sensor_files 
			WHERE hive_id = $1
			ORDER BY timestamp DESC
			LIMIT $2 OFFSET $3`
		args = []interface{}{hiveID, limit, offset}
	}

	err := r.db.GetDB().SelectContext(ctx, &files, query, args...)
	if err != nil {
		return nil, errors.NewDatabaseError("failed to list files", err)
	}
	return files, nil
}

func (r *SensorFileRepo) ListBySensor(ctx context.Context, sensorID string, fileType string, limit, offset int) ([]*models.SensorFile, error) {
	files := []*models.SensorFile{}
	var query string
	var args []interface{}

	if fileType != "" {
		query = `
			SELECT * FROM sensor_files 
			WHERE sensor_id = $1 AND type = $2
			ORDER BY timestamp DESC
			LIMIT $3 OFFSET $4`
		args = []interface{}{sensorID, fileType, limit, offset}
	} else {
		query = `
			SELECT * FROM sensor_files 
			WHERE sensor_id = $1
			ORDER BY timestamp DESC
			LIMIT $2 OFFSET $3`
		args = []interface{}{sensorID, limit, offset}
	}

	err := r.db.GetDB().SelectContext(ctx, &files, query, args...)
	if err != nil {
		return nil, errors.NewDatabaseError("failed to list files", err)
	}
	return files, nil
}

func (r *SensorFileRepo) Delete(ctx context.Context, id string) error {
	query := `DELETE FROM sensor_files WHERE id = $1`

	result, err := r.db.GetDB().ExecContext(ctx, query, id)
	if err != nil {
		return errors.NewDatabaseError("failed to delete file", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return errors.NewDatabaseError("failed to get rows affected", err)
	}

	if rows == 0 {
		return errors.NewNotFoundError("file not found", nil)
	}

	return nil
}

func (r *SensorFileRepo) DeleteByHive(ctx context.Context, hiveID string) error {
	query := `DELETE FROM sensor_files WHERE hive_id = $1`

	result, err := r.db.GetDB().ExecContext(ctx, query, hiveID)
	if err != nil {
		return errors.NewDatabaseError("failed to delete files", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return errors.NewDatabaseError("failed to get rows affected", err)
	}

	nuts.L.Infof("[FileRepo] Deleted %d files for hive %s", rows, hiveID)
	return nil
}

func (r *SensorFileRepo) DeleteOldFiles(ctx context.Context, before time.Time) error {
	query := `DELETE FROM sensor_files WHERE timestamp < $1`

	result, err := r.db.GetDB().ExecContext(ctx, query, before)
	if err != nil {
		return errors.NewDatabaseError("failed to delete old files", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return errors.NewDatabaseError("failed to get rows affected", err)
	}

	nuts.L.Infof("[FileRepo] Deleted %d files older than %v", rows, before)
	return nil
}

func (r *SensorFileRepo) GetLatestFiles(ctx context.Context, hiveID, sensorID string, fileTypes []string) ([]*models.SensorFile, error) {
	query := `
        WITH RankedFiles AS (
            SELECT sf.*,
                   ROW_NUMBER() OVER (PARTITION BY sf.type ORDER BY sf.timestamp DESC) as rn
            FROM sensor_files sf
            WHERE sf.hive_id = $1
              AND ($2 = '' OR sf.sensor_id = $2)
              AND sf.type = ANY($3)
        )
        SELECT id, hive_id, sensor_id, type, path, size, mime_type, timestamp, created_at
        FROM RankedFiles
        WHERE rn = 1`

	files := []*models.SensorFile{}
	err := r.db.GetDB().SelectContext(ctx, &files, query, hiveID, sensorID, pq.Array(fileTypes))
	if err != nil {
		return nil, errors.NewDatabaseError("failed to get latest files", err)
	}

	return files, nil
}

// Add index for performance
func (r *SensorFileRepo) initializeSchema() error {
	query := `
        CREATE INDEX IF NOT EXISTS idx_sensor_files_latest 
        ON sensor_files(hive_id, sensor_id, type, timestamp DESC)`

	_, err := r.db.GetDB().Exec(query)
	if err != nil {
		return errors.NewDatabaseError("failed to create index", err)
	}
	return nil
}
