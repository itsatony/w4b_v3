package postgres

import (
	"github.com/itsatony/w4b_v3/server/hub/internal/repository"
	"github.com/jmoiron/sqlx"
)

type SensorRepo struct {
	db *sqlx.DB
}

// NewSensorRepository creates a new PostgreSQL-backed sensor repository
func NewSensorRepository(db *sqlx.DB) repository.SensorRepository {
	return &SensorRepo{
		db: db,
	}
}

// Implement other SensorRepository interface methods...
