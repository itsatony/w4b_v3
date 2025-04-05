package postgres

import (
	"context"
	"database/sql"

	"github.com/itsatony/w4b_v3/server/hub/internal/database"
	"github.com/itsatony/w4b_v3/server/hub/internal/errors"
)

type PostgresBaseRepo struct {
	db database.DB
}

func (r *PostgresBaseRepo) BeginTx(ctx context.Context) (database.Transaction, error) {
	tx, err := r.db.GetDB().BeginTxx(ctx, nil)
	if err != nil {
		return nil, errors.NewDatabaseError("failed to begin transaction", err)
	}
	return tx, nil
}
func (r *PostgresBaseRepo) Commit(tx database.Transaction) error {
	if err := tx.Commit(); err != nil {
		return errors.NewDatabaseError("failed to commit transaction", err)
	}
	return nil
}
func (r *PostgresBaseRepo) Rollback(tx database.Transaction) error {
	if err := tx.Rollback(); err != nil {
		return errors.NewDatabaseError("failed to rollback transaction", err)
	}
	return nil
}
func (r *PostgresBaseRepo) ExecContext(ctx context.Context, query string, args ...interface{}) (sql.Result, error) {
	result, err := r.db.GetDB().ExecContext(ctx, query, args...)
	if err != nil {
		return nil, errors.NewDatabaseError("failed to execute query", err)
	}
	return result, nil
}
func (r *PostgresBaseRepo) QueryContext(ctx context.Context, query string, args ...interface{}) (*sql.Rows, error) {
	rows, err := r.db.GetDB().QueryContext(ctx, query, args...)
	if err != nil {
		return nil, errors.NewDatabaseError("failed to execute query", err)
	}
	return rows, nil
}
func (r *PostgresBaseRepo) Ping(ctx context.Context) error {
	if err := r.db.GetDB().PingContext(ctx); err != nil {
		return errors.NewDatabaseError("failed to ping database", err)
	}
	return nil
}
func (r *PostgresBaseRepo) Close() error {
	if err := r.db.GetDB().Close(); err != nil {
		return errors.NewDatabaseError("failed to close database", err)
	}
	return nil
}
