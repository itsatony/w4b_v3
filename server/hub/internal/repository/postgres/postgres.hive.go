// FilePath: server/hub/internal/repository/postgres/postgres.hive.go
package postgres

import (
	"context"
	"database/sql"
	"time"

	"github.com/itsatony/w4b_v3/server/hub/internal/database"
	"github.com/itsatony/w4b_v3/server/hub/internal/errors"
	"github.com/itsatony/w4b_v3/server/hub/internal/models"
)

type HiveRepo struct {
	PostgresBaseRepo
}

func NewHiveRepository(db database.DB) *HiveRepo {
	repo := &PostgresBaseRepo{db: db}
	return &HiveRepo{PostgresBaseRepo: *repo}
}

func (r *HiveRepo) Create(ctx context.Context, hive *models.Hive) error {
	query := `
		INSERT INTO hives (
			id, name, description, profile_picture_url, location, 
			latitude, longitude, system_version, timezone, networks,
			ssh_public_key, vpn_config, hive_config_yaml,
			last_seen, last_sensor_data_received, created_at, updated_at
		) VALUES (
			:id, :name, :description, :profile_picture_url, :location,
			:latitude, :longitude, :system_version, :timezone, :networks,
			:ssh_public_key, :vpn_config, :hive_config_yaml,
			:last_seen, :last_sensor_data_received, :created_at, :updated_at
		)`

	_, err := r.db.GetDB().NamedExecContext(ctx, query, hive)
	if err != nil {
		return errors.NewDatabaseError("failed to create hive", err)
	}
	return nil
}

func (r *HiveRepo) Get(ctx context.Context, id string) (*models.Hive, error) {
	hive := &models.Hive{}
	query := `SELECT * FROM hives WHERE id = $1`

	err := r.db.GetDB().GetContext(ctx, hive, query, id)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, errors.NewNotFoundError("hive not found", err)
		}
		return nil, errors.NewDatabaseError("failed to get hive", err)
	}
	return hive, nil
}

func (r *HiveRepo) Update(ctx context.Context, hive *models.Hive) error {
	query := `
		UPDATE hives SET 
			name = :name,
			description = :description,
			profile_picture_url = :profile_picture_url,
			location = :location,
			latitude = :latitude,
			longitude = :longitude,
			system_version = :system_version,
			timezone = :timezone,
			networks = :networks,
			ssh_public_key = :ssh_public_key,
			vpn_config = :vpn_config,
			hive_config_yaml = :hive_config_yaml,
			updated_at = :updated_at
		WHERE id = :id`

	result, err := r.db.GetDB().NamedExecContext(ctx, query, hive)
	if err != nil {
		return errors.NewDatabaseError("failed to update hive", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return errors.NewDatabaseError("failed to get rows affected", err)
	}

	if rows == 0 {
		return errors.NewNotFoundError("hive not found", nil)
	}

	return nil
}

func (r *HiveRepo) UpdateLastSensorDataReceived(ctx context.Context, id string, lastSensorDataReceived time.Time) error {
	query := `UPDATE hives SET last_sensor_data_received = $1 WHERE id = $2`
	result, err := r.db.GetDB().ExecContext(ctx, query, lastSensorDataReceived, id)
	if err != nil {
		return errors.NewDatabaseError("failed to update last sensor data received", err)
	}
	rows, err := result.RowsAffected()
	if err != nil {
		return errors.NewDatabaseError("failed to get rows affected", err)
	}
	if rows == 0 {
		return errors.NewNotFoundError("hive not found", nil)
	}
	return nil
}

func (r *HiveRepo) UpdateLastSeen(ctx context.Context, id string, lastSeen time.Time) error {
	query := `UPDATE hives SET last_seen = $1 WHERE id = $2`
	result, err := r.db.GetDB().ExecContext(ctx, query, lastSeen, id)
	if err != nil {
		return errors.NewDatabaseError("failed to update last seen", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return errors.NewDatabaseError("failed to get rows affected", err)
	}

	if rows == 0 {
		return errors.NewNotFoundError("hive not found", nil)
	}

	return nil
}

func (r *HiveRepo) List(ctx context.Context, offset, limit int) ([]*models.Hive, error) {
	hives := []*models.Hive{}
	query := `SELECT * FROM hives ORDER BY created_at DESC LIMIT $1 OFFSET $2`

	err := r.db.GetDB().SelectContext(ctx, &hives, query, limit, offset)
	if err != nil {
		return nil, errors.NewDatabaseError("failed to list hives", err)
	}

	return hives, nil
}

func (r *HiveRepo) Delete(ctx context.Context, id string) error {
	query := `DELETE FROM hives WHERE id = $1`

	result, err := r.db.GetDB().ExecContext(ctx, query, id)
	if err != nil {
		return errors.NewDatabaseError("failed to delete hive", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return errors.NewDatabaseError("failed to get rows affected", err)
	}

	if rows == 0 {
		return errors.NewNotFoundError("hive not found", nil)
	}

	return nil
}

func (r *HiveRepo) DeleteWithChildren(ctx context.Context, id string, tx database.Transaction) error {
	// Delete all child entities related to the hive
	// For example, delete sensors, sensor data, etc.
	// This is a placeholder for the actual deletion logic
	// You would typically have a method in the respective repositories to handle this
	// TODO: Implement deletion of child entities
	// Delete the hive itself
	return r.Delete(ctx, id)
}
