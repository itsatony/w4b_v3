package postgres

import (
	"github.com/itsatony/w4b_v3/server/hub/internal/repository"
	"github.com/jmoiron/sqlx"
)

type SensorDataRepo struct {
	db *sqlx.DB
}

// NewSensorDataRepository creates a new TimescaleDB-backed sensor data repository
func NewSensorDataRepository(db *sqlx.DB) repository.SensorDataRepository {
	return &SensorDataRepo{
		db: db,
	}
}

// Implement other SensorDataRepository interface methods...
