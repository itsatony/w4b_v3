// FilePath: server/hub/internal/database/database.go
package database

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/itsatony/w4b_v3/server/hub/internal/config"
	"github.com/jmoiron/sqlx"
	_ "github.com/lib/pq"
	nuts "github.com/vaudience/go-nuts"
)

// DB is an interface that both PostgreSQL and TimescaleDB must implement
type DB interface {
	Close() error
	Ping(ctx context.Context) error
	GetDB() *sqlx.DB
}

// PostgresDB represents a PostgreSQL database connection
type PostgresDB struct {
	db *sqlx.DB
}

// TimescaleDB represents a TimescaleDB database connection
type TimescaleDB struct {
	db *sqlx.DB
}

// Transaction represents a database transaction
type Transaction interface {
	Commit() error
	Rollback() error
	ExecContext(ctx context.Context, query string, args ...interface{}) (sql.Result, error)
}

// Repository represents common repository operations
type Repository interface {
	BeginTx(ctx context.Context) (Transaction, error)
}

// NewPostgresDB creates a new PostgreSQL database connection
func NewPostgresDB(cfg config.PostgresConfig) (DB, error) {
	dsn := fmt.Sprintf(
		"host=%s port=%d user=%s password=%s dbname=%s sslmode=%s",
		cfg.Host, cfg.Port, cfg.User, cfg.Password, cfg.DBName, cfg.SSLMode,
	)

	db, err := sqlx.Connect("postgres", dsn)
	if err != nil {
		return nil, fmt.Errorf("error connecting to PostgreSQL: %w", err)
	}

	nuts.L.Infof("[PostgresDB] Connected to %s:%d/%s", cfg.Host, cfg.Port, cfg.DBName)
	return &PostgresDB{db: db}, nil
}

// NewTimescaleDB creates a new TimescaleDB database connection
func NewTimescaleDB(cfg config.PostgresConfig) (DB, error) {
	dsn := fmt.Sprintf(
		"host=%s port=%d user=%s password=%s dbname=%s sslmode=%s",
		cfg.Host, cfg.Port, cfg.User, cfg.Password, cfg.DBName, cfg.SSLMode,
	)

	db, err := sqlx.Connect("postgres", dsn)
	if err != nil {
		return nil, fmt.Errorf("error connecting to TimescaleDB: %w", err)
	}

	// Verify TimescaleDB extension
	var hasTimescaleDB bool
	err = db.Get(&hasTimescaleDB, "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb')")
	if err != nil || !hasTimescaleDB {
		return nil, fmt.Errorf("TimescaleDB extension not available")
	}

	nuts.L.Infof("[TimescaleDB] Connected to %s:%d/%s", cfg.Host, cfg.Port, cfg.DBName)
	return &TimescaleDB{db: db}, nil
}

// Implementation of DB interface for PostgresDB
func (p *PostgresDB) Close() error {
	return p.db.Close()
}

func (p *PostgresDB) Ping(ctx context.Context) error {
	return p.db.PingContext(ctx)
}

func (p *PostgresDB) GetDB() *sqlx.DB {
	return p.db
}

// Implementation of DB interface for TimescaleDB
func (t *TimescaleDB) Close() error {
	return t.db.Close()
}

func (t *TimescaleDB) Ping(ctx context.Context) error {
	return t.db.PingContext(ctx)
}

func (t *TimescaleDB) GetDB() *sqlx.DB {
	return t.db
}
