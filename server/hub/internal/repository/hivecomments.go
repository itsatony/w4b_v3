package repository

import (
	"context"
	"time"

	"github.com/itsatony/w4b_v3/server/hub/internal/models"
	"github.com/jmoiron/sqlx"
	nuts "github.com/vaudience/go-nuts"
)

// HiveCommentRepository defines the interface for hive comment operations
type HiveCommentRepository interface {
	Create(ctx context.Context, comment *models.HiveComment) error
	Get(ctx context.Context, id string) (*models.HiveComment, error)
	List(ctx context.Context, hiveID string, offset, limit int) ([]*models.HiveComment, error)
	Delete(ctx context.Context, id string) error
	DeleteByHive(ctx context.Context, hiveID string) error
}

// PostgresHiveCommentRepository implements HiveCommentRepository
type PostgresHiveCommentRepository struct {
	db *sqlx.DB
}

// NewPostgresHiveCommentRepository creates a new PostgresHiveCommentRepository
func NewPostgresHiveCommentRepository(db *sqlx.DB) *PostgresHiveCommentRepository {
	return &PostgresHiveCommentRepository{db: db}
}

// Create inserts a new hive comment
func (r *PostgresHiveCommentRepository) Create(ctx context.Context, comment *models.HiveComment) error {
	query := `
		INSERT INTO hive_comments (
			id, hive_id, user_id, text, created_at, updated_at
		) VALUES (
			$1, $2, $3, $4, $5, $6
		)`

	now := time.Now()
	if comment.ID == "" {
		comment.ID = nuts.NID("cmt", 12)
	}
	comment.CreatedAt = now
	comment.UpdatedAt = now

	_, err := r.db.ExecContext(ctx, query,
		comment.ID,
		comment.HiveID,
		comment.UserID,
		comment.Text,
		comment.CreatedAt,
		comment.UpdatedAt,
	)

	if err != nil {
		nuts.L.Errorf("[HiveCommentRepository] Failed to create comment: %v", err)
		return err
	}

	return nil
}

// Get retrieves a single hive comment by ID
func (r *PostgresHiveCommentRepository) Get(ctx context.Context, id string) (*models.HiveComment, error) {
	query := `
		SELECT id, hive_id, user_id, text, created_at, updated_at
		FROM hive_comments
		WHERE id = $1`

	comment := &models.HiveComment{}
	err := r.db.GetContext(ctx, comment, query, id)
	if err != nil {
		nuts.L.Errorf("[HiveCommentRepository] Failed to get comment %s: %v", id, err)
		return nil, err
	}

	return comment, nil
}

// List retrieves a paginated list of comments for a specific hive
func (r *PostgresHiveCommentRepository) List(ctx context.Context, hiveID string, offset, limit int) ([]*models.HiveComment, error) {
	query := `
		SELECT id, hive_id, user_id, text, created_at, updated_at
		FROM hive_comments
		WHERE hive_id = $1
		ORDER BY created_at DESC
		LIMIT $2 OFFSET $3`

	comments := []*models.HiveComment{}
	err := r.db.SelectContext(ctx, &comments, query, hiveID, limit, offset)
	if err != nil {
		nuts.L.Errorf("[HiveCommentRepository] Failed to list comments for hive %s: %v", hiveID, err)
		return nil, err
	}

	return comments, nil
}

// Delete removes a hive comment
func (r *PostgresHiveCommentRepository) Delete(ctx context.Context, id string) error {
	query := `DELETE FROM hive_comments WHERE id = $1`

	result, err := r.db.ExecContext(ctx, query, id)
	if err != nil {
		nuts.L.Errorf("[HiveCommentRepository] Failed to delete comment %s: %v", id, err)
		return err
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return err
	}
	if rows == 0 {
		return ErrNotFound
	}

	return nil
}

// DeleteByHive removes all comments for a specific hive
func (r *PostgresHiveCommentRepository) DeleteByHive(ctx context.Context, hiveID string) error {
	query := `DELETE FROM hive_comments WHERE hive_id = $1`

	_, err := r.db.ExecContext(ctx, query, hiveID)
	if err != nil {
		nuts.L.Errorf("[HiveCommentRepository] Failed to delete comments for hive %s: %v", hiveID, err)
		return err
	}

	return nil
}
