package postgres

import (
	"github.com/itsatony/w4b_v3/server/hub/internal/repository"
	"github.com/jmoiron/sqlx"
)

type HiveRepo struct {
	db *sqlx.DB
}

// NewHiveRepository creates a new PostgreSQL-backed hive repository
func NewHiveRepository(db *sqlx.DB) repository.HiveRepository {
	return &HiveRepo{
		db: db,
	}
}

// Implement other HiveRepository interface methods...
