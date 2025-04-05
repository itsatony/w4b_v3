package timescale

import (
	"context"
	"database/sql"

	"github.com/itsatony/w4b_v3/server/hub/internal/database"
	"github.com/itsatony/w4b_v3/server/hub/internal/errors"
)

type TimeScaleBaseRepo struct {
	db database.DB
}

func (r *TimeScaleBaseRepo) BeginTx(ctx context.Context) (database.Transaction, error) {
	tx, err := r.db.GetDB().BeginTxx(ctx, nil)
	if err != nil {
		return nil, errors.NewDatabaseError("failed to begin transaction", err)
	}
	return tx, nil
}
func (r *TimeScaleBaseRepo) Commit(tx database.Transaction) error {
	if err := tx.Commit(); err != nil {
		return errors.NewDatabaseError("failed to commit transaction", err)
	}
	return nil
}
func (r *TimeScaleBaseRepo) Rollback(tx database.Transaction) error {
	if err := tx.Rollback(); err != nil {
		return errors.NewDatabaseError("failed to rollback transaction", err)
	}
	return nil
}
func (r *TimeScaleBaseRepo) ExecContext(ctx context.Context, query string, args ...interface{}) (sql.Result, error) {
	result, err := r.db.GetDB().ExecContext(ctx, query, args...)
	if err != nil {
		return nil, errors.NewDatabaseError("failed to execute query", err)
	}
	return result, nil
}
func (r *TimeScaleBaseRepo) QueryContext(ctx context.Context, query string, args ...interface{}) (*sql.Rows, error) {
	rows, err := r.db.GetDB().QueryContext(ctx, query, args...)
	if err != nil {
		return nil, errors.NewDatabaseError("failed to execute query", err)
	}
	return rows, nil
}
func (r *TimeScaleBaseRepo) Ping(ctx context.Context) error {
	if err := r.db.GetDB().PingContext(ctx); err != nil {
		return errors.NewDatabaseError("failed to ping database", err)
	}
	return nil
}
func (r *TimeScaleBaseRepo) Close() error {
	if err := r.db.GetDB().Close(); err != nil {
		return errors.NewDatabaseError("failed to close database", err)
	}
	return nil
}
