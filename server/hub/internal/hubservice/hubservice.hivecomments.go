package hubservice

import (
	"context"
	"time"

	"github.com/itsatony/w4b_v3/server/hub/internal/errors"
	"github.com/itsatony/w4b_v3/server/hub/internal/models"
	nuts "github.com/vaudience/go-nuts"
)

// HiveCommentService defines the interface for comment-related operations
type HiveCommentService interface {
	CreateComment(ctx context.Context, hiveID string, comment *models.HiveComment) error
	GetComment(ctx context.Context, id string) (*models.HiveComment, error)
	ListComments(ctx context.Context, hiveID string, offset, limit int) ([]*models.HiveComment, error)
	DeleteComment(ctx context.Context, id string) error
	DeleteHiveComments(ctx context.Context, hiveID string) error
}

// CreateComment creates a new comment for a hive with proper validation
func (s *HubService) CreateComment(ctx context.Context, hiveID string, comment *models.HiveComment) error {
	// Verify hive exists
	_, err := s.Hives.Get(ctx, hiveID)
	if err != nil {
		return errors.NewNotFoundError("hive not found", err)
	}

	// Get user info from context
	userID := getUserIDFromContext(ctx)
	if userID == "" {
		return errors.NewAuthorizationError("user not authenticated", nil)
	}

	// Validate comment
	if comment.Text == "" {
		return errors.NewValidationError("comment text is required", nil)
	}

	// Set metadata
	comment.ID = nuts.NID("cmt", 12)
	comment.HiveID = hiveID
	comment.UserID = userID
	now := time.Now()
	comment.CreatedAt = now
	comment.UpdatedAt = now

	nuts.L.Infof("[HiveCommentService] Creating comment %s for hive %s by user %s", comment.ID, hiveID, userID)
	return s.HiveComments.Create(ctx, comment)
}

// GetComment retrieves a single comment by ID
func (s *HubService) GetComment(ctx context.Context, id string) (*models.HiveComment, error) {
	comment, err := s.HiveComments.Get(ctx, id)
	if err != nil {
		nuts.L.Errorf("[HiveCommentService] Failed to get comment %s: %v", id, err)
		return nil, errors.NewNotFoundError("comment not found", err)
	}

	return comment, nil
}

// ListComments retrieves a paginated list of comments for a hive
func (s *HubService) ListComments(ctx context.Context, hiveID string, offset, limit int) ([]*models.HiveComment, error) {
	// Verify hive exists
	_, err := s.Hives.Get(ctx, hiveID)
	if err != nil {
		return nil, errors.NewNotFoundError("hive not found", err)
	}

	// Validate pagination
	if limit <= 0 || limit > 100 {
		limit = 50 // Default limit
	}
	if offset < 0 {
		offset = 0
	}

	comments, err := s.HiveComments.List(ctx, hiveID, offset, limit)
	if err != nil {
		nuts.L.Errorf("[HiveCommentService] Failed to list comments for hive %s: %v", hiveID, err)
		return nil, errors.NewInternalError("failed to list comments", err)
	}

	return comments, nil
}

// DeleteComment deletes a comment with proper authorization
func (s *HubService) DeleteComment(ctx context.Context, id string) error {
	// Get the comment first to check ownership
	comment, err := s.HiveComments.Get(ctx, id)
	if err != nil {
		return errors.NewNotFoundError("comment not found", err)
	}

	// Check authorization
	userID := getUserIDFromContext(ctx)
	roles := GetUserRoles(ctx)
	if !canDeleteComment(comment, userID, roles) {
		return errors.NewAuthorizationError("not authorized to delete this comment", nil)
	}

	nuts.L.Infof("[HiveCommentService] Deleting comment %s by user %s", id, userID)
	return s.HiveComments.Delete(ctx, id)
}

// DeleteHiveComments deletes all comments for a hive (admin only)
func (s *HubService) DeleteHiveComments(ctx context.Context, hiveID string) error {
	// Verify hive exists
	_, err := s.Hives.Get(ctx, hiveID)
	if err != nil {
		return errors.NewNotFoundError("hive not found", err)
	}

	// Check admin authorization
	roles := GetUserRoles(ctx)
	if !hasAdminRole(roles) {
		return errors.NewAuthorizationError("admin access required", nil)
	}

	nuts.L.Infof("[HiveCommentService] Deleting all comments for hive %s", hiveID)
	return s.HiveComments.DeleteByHive(ctx, hiveID)
}

// Helper functions

func getUserIDFromContext(ctx context.Context) string {
	if userID := ctx.Value("user_id"); userID != nil {
		if id, ok := userID.(string); ok {
			return id
		}
	}
	return ""
}

func canDeleteComment(comment *models.HiveComment, userID string, roles []string) bool {
	// Allow deletion if user is the comment author
	if comment.UserID == userID {
		return true
	}

	// Allow deletion if user has admin role
	return hasAdminRole(roles)
}

func hasAdminRole(roles []string) bool {
	for _, role := range roles {
		if role == "superadmin" || role == "hiveadmin" {
			return true
		}
	}
	return false
}
