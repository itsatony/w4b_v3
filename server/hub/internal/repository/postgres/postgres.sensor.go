// FilePath: server/hub/internal/repository/postgres/postgres.sensor.go
package postgres

import (
	"context"
	"database/sql"
	"time"

	"github.com/itsatony/w4b_v3/server/hub/internal/database"
	"github.com/itsatony/w4b_v3/server/hub/internal/errors"
	"github.com/itsatony/w4b_v3/server/hub/internal/models"
)

type SensorRepo struct {
	db database.DB
}

func NewSensorRepository(db database.DB) *SensorRepo {
	return &SensorRepo{db: db}
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
