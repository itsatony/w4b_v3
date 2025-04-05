// FilePath: server/hub/internal/repository/postgres/postgres.sensor.go
package postgres

import (
	"context"
	"database/sql"
	"time"

	"github.com/itsatony/w4b_v3/server/hub/internal/database"
	"github.com/itsatony/w4b_v3/server/hub/internal/errors"
	"github.com/itsatony/w4b_v3/server/hub/internal/models"
	nuts "github.com/vaudience/go-nuts"
)

type SensorRepo struct {
	PostgresBaseRepo
}

func NewSensorRepository(db database.DB) *SensorRepo {
	repo := &PostgresBaseRepo{db: db}
	return &SensorRepo{PostgresBaseRepo: *repo}
}

func (r *SensorRepo) Create(ctx context.Context, sensor *models.Sensor) error {
	query := `
		INSERT INTO sensors (
			id, hive_id, name, description, type, model,
			interface, unit, precision, min_value, max_value,
			last_value, last_value_time, status, error_message,
			calibration, metadata, created_at, updated_at
		) VALUES (
			:id, :hive_id, :name, :description, :type, :model,
			:interface, :unit, :precision, :min_value, :max_value,
			:last_value, :last_value_time, :status, :error_message,
			:calibration, :metadata, :created_at, :updated_at
		)`

	_, err := r.db.GetDB().NamedExecContext(ctx, query, sensor)
	if err != nil {
		return errors.NewDatabaseError("failed to create sensor", err)
	}
	return nil
}

func (r *SensorRepo) Get(ctx context.Context, id string) (*models.Sensor, error) {
	sensor := &models.Sensor{}
	query := `SELECT * FROM sensors WHERE id = $1`

	err := r.db.GetDB().GetContext(ctx, sensor, query, id)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, errors.NewNotFoundError("sensor not found", err)
		}
		return nil, errors.NewDatabaseError("failed to get sensor", err)
	}
	return sensor, nil
}

func (r *SensorRepo) ListByHive(ctx context.Context, hiveID string) ([]*models.Sensor, error) {
	sensors := []*models.Sensor{}
	query := `SELECT * FROM sensors WHERE hive_id = $1 ORDER BY created_at DESC`

	err := r.db.GetDB().SelectContext(ctx, &sensors, query, hiveID)
	if err != nil {
		return nil, errors.NewDatabaseError("failed to list sensors", err)
	}

	return sensors, nil
}

func (r *SensorRepo) Update(ctx context.Context, sensor *models.Sensor) error {
	query := `
		UPDATE sensors SET 
			name = :name,
			description = :description,
			type = :type,
			model = :model,
			interface = :interface,
			unit = :unit,
			precision = :precision,
			min_value = :min_value,
			max_value = :max_value,
			status = :status,
			error_message = :error_message,
			calibration = :calibration,
			metadata = :metadata,
			updated_at = :updated_at
		WHERE id = :id`

	result, err := r.db.GetDB().NamedExecContext(ctx, query, sensor)
	if err != nil {
		return errors.NewDatabaseError("failed to update sensor", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return errors.NewDatabaseError("failed to get rows affected", err)
	}

	if rows == 0 {
		return errors.NewNotFoundError("sensor not found", nil)
	}

	return nil
}

func (r *SensorRepo) UpdateLastValue(ctx context.Context, id string, value float64, timestamp time.Time) error {
	query := `
		UPDATE sensors SET 
			last_value = $1,
			last_value_time = $2,
			updated_at = $2
		WHERE id = $3`

	result, err := r.db.GetDB().ExecContext(ctx, query, value, timestamp, id)
	if err != nil {
		return errors.NewDatabaseError("failed to update last value", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return errors.NewDatabaseError("failed to get rows affected", err)
	}

	if rows == 0 {
		return errors.NewNotFoundError("sensor not found", nil)
	}

	return nil
}

func (r *SensorRepo) Delete(ctx context.Context, id string) error {
	query := `DELETE FROM sensors WHERE id = $1`

	result, err := r.db.GetDB().ExecContext(ctx, query, id)
	if err != nil {
		return errors.NewDatabaseError("failed to delete sensor", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return errors.NewDatabaseError("failed to get rows affected", err)
	}

	if rows == 0 {
		return errors.NewNotFoundError("sensor not found", nil)
	}

	return nil
}

func (r *SensorRepo) DeleteWithData(ctx context.Context, id string, tx database.Transaction) error {
	query := `DELETE FROM sensors WHERE id = $1`

	result, err := tx.ExecContext(ctx, query, id)
	if err != nil {
		return errors.NewDatabaseError("failed to delete sensor", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return errors.NewDatabaseError("failed to get rows affected", err)
	}

	if rows == 0 {
		return errors.NewNotFoundError("sensor not found", nil)
	}

	return nil
}

func (r *SensorRepo) DeleteByHive(ctx context.Context, hiveID string) error {
	query := `DELETE FROM sensors WHERE hive_id = $1`

	result, err := r.db.GetDB().ExecContext(ctx, query, hiveID)
	if err != nil {
		return errors.NewDatabaseError("failed to delete sensors", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return errors.NewDatabaseError("failed to get rows affected", err)
	}

	nuts.L.Infof("[SensorRepo] Deleted %d sensors for hive %s", rows, hiveID)
	return nil
}
func (r *SensorRepo) DeleteOldSensors(ctx context.Context, before time.Time) error {
	query := `DELETE FROM sensors WHERE last_value_time < $1`

	result, err := r.db.GetDB().ExecContext(ctx, query, before)
	if err != nil {
		return errors.NewDatabaseError("failed to delete old sensors", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return errors.NewDatabaseError("failed to get rows affected", err)
	}

	nuts.L.Infof("[SensorRepo] Deleted %d sensors older than %v", rows, before)
	return nil
}
func (r *SensorRepo) DeleteOldSensorData(ctx context.Context, before time.Time) error {
	query := `DELETE FROM sensor_data WHERE timestamp < $1`

	result, err := r.db.GetDB().ExecContext(ctx, query, before)
	if err != nil {
		return errors.NewDatabaseError("failed to delete old sensor data", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return errors.NewDatabaseError("failed to get rows affected", err)
	}

	nuts.L.Infof("[SensorRepo] Deleted %d sensor data older than %v", rows, before)
	return nil
}
func (r *SensorRepo) DeleteOldSensorFiles(ctx context.Context, before time.Time) error {
	query := `DELETE FROM sensor_files WHERE timestamp < $1`

	result, err := r.db.GetDB().ExecContext(ctx, query, before)
	if err != nil {
		return errors.NewDatabaseError("failed to delete old sensor files", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return errors.NewDatabaseError("failed to get rows affected", err)
	}

	nuts.L.Infof("[SensorRepo] Deleted %d sensor files older than %v", rows, before)
	return nil
}
func (r *SensorRepo) DeleteOldSensorDataByHive(ctx context.Context, hiveID string, before time.Time) error {
	query := `DELETE FROM sensor_data WHERE hive_id = $1 AND timestamp < $2`

	result, err := r.db.GetDB().ExecContext(ctx, query, hiveID, before)
	if err != nil {
		return errors.NewDatabaseError("failed to delete old sensor data", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return errors.NewDatabaseError("failed to get rows affected", err)
	}

	nuts.L.Infof("[SensorRepo] Deleted %d sensor data older than %v for hive %s", rows, before, hiveID)
	return nil
}
func (r *SensorRepo) DeleteOldSensorFilesByHive(ctx context.Context, hiveID string, before time.Time) error {
	query := `DELETE FROM sensor_files WHERE hive_id = $1 AND timestamp < $2`

	result, err := r.db.GetDB().ExecContext(ctx, query, hiveID, before)
	if err != nil {
		return errors.NewDatabaseError("failed to delete old sensor files", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return errors.NewDatabaseError("failed to get rows affected", err)
	}

	nuts.L.Infof("[SensorRepo] Deleted %d sensor files older than %v for hive %s", rows, before, hiveID)
	return nil
}

func (r *SensorRepo) List(ctx context.Context, filters models.SensorFilters, page, limit int) (int64, []*models.Sensor, error) {
	query := `
		SELECT COUNT(*) OVER(), *
		FROM sensors
		WHERE 1=1
	`

	args := []interface{}{}
	if filters.HiveID != "" {
		query += ` AND hive_id = $1`
		args = append(args, filters.HiveID)
	}
	if filters.Type != "" {
		query += ` AND type = $2`
		args = append(args, filters.Type)
	}
	if filters.Status != "" {
		query += ` AND status = $3`
		args = append(args, filters.Status)
	}

	query += ` ORDER BY created_at DESC LIMIT $4 OFFSET $5`
	args = append(args, limit, (page-1)*limit)

	sensors := []*models.Sensor{}
	count := int64(0)

	err := r.db.GetDB().SelectContext(ctx, &sensors, query, args...)
	if err != nil {
		return 0, nil, errors.NewDatabaseError("failed to list sensors", err)
	}

	count = int64(len(sensors))

	return count, sensors, nil
}
