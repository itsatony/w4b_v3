package hubservice

import (
	"context"
	"time"

	"github.com/itsatony/struccy"
	"github.com/itsatony/w4b_v3/server/hub/internal/errors"
	"github.com/itsatony/w4b_v3/server/hub/internal/models"
	nuts "github.com/vaudience/go-nuts"
)

// HiveService handles hive-related business logic
type HiveService interface {
	CreateHive(ctx context.Context, hive *models.Hive) error
	GetHive(ctx context.Context, id string) (*models.Hive, error)
	UpdateHive(ctx context.Context, hive *models.Hive) error
	DeleteHive(ctx context.Context, id string) error
	ListHives(ctx context.Context, offset, limit int) ([]*models.Hive, error)
	GetHiveStatus(ctx context.Context, id string) (*HiveStatus, error)
	CreateHiveComment(ctx context.Context, hiveID string, comment *models.HiveComment) error
	ListHiveComments(ctx context.Context, hiveID string, offset, limit int) ([]*models.HiveComment, error)
	DeleteHiveComment(ctx context.Context, hiveID, commentID string) error
}

type HiveStatus struct {
	Hive         *models.Hive                     `json:"hive"`
	LastReadings map[string]*models.SensorReading `json:"last_readings"`
	LastFiles    []*models.SensorFile             `json:"last_files"`
	OnlineStatus string                           `json:"online_status"`
	LastActivity time.Time                        `json:"last_activity"`
}

// CreateHive creates a new hive with proper validation and initialization
func (s *HubService) CreateHive(ctx context.Context, hive *models.Hive) error {
	// Validate required fields
	if hive.Name == "" {
		return errors.NewValidationError("hive name is required", nil)
	}

	// Generate new ID if not provided
	if hive.ID == "" {
		hive.ID = nuts.NID("hv", 12)
	}

	// Set timestamps
	now := time.Now()
	hive.CreatedAt = now
	hive.UpdatedAt = now
	hive.LastSeen = now

	// Initialize optional fields with defaults
	if hive.Timezone == "" {
		hive.Timezone = "UTC"
	}
	if hive.SystemVersion == "" {
		hive.SystemVersion = "1.0.0"
	}

	nuts.L.Infof("[HiveService] Creating new hive: %s (%s)", hive.Name, hive.ID)
	return s.Hives.Create(ctx, hive)
}

// UpdateHive updates an existing hive with role-based access control
func (s *HubService) UpdateHive(ctx context.Context, hive *models.Hive) error {
	// Get existing hive to verify existence and compare changes
	existing, err := s.Hives.Get(ctx, hive.ID)
	if err != nil {
		return err
	}

	// Get user roles from context
	roles := GetUserRoles(ctx)

	// Use struccy to update fields based on role access
	updatedFields, _, err := struccy.UpdateStructFields(existing, hive, roles, true, true)
	if err != nil {
		return errors.NewAuthorizationError("unauthorized field update", err)
	}

	hive.UpdatedAt = time.Now()

	nuts.L.Infof("[HiveService] Updating hive %s, fields changed: %v", hive.ID, updatedFields)
	return s.Hives.Update(ctx, hive)
}

// GetHive retrieves a hive with role-based field filtering
func (s *HubService) GetHive(ctx context.Context, id string) (*models.Hive, error) {
	hive, err := s.Hives.Get(ctx, id)
	if err != nil {
		return nil, err
	}

	// Get user roles from context
	roles := GetUserRoles(ctx)

	// Filter fields based on read access
	filteredMap, err := struccy.StructToMapFieldsWithReadXS(hive, roles)
	if err != nil {
		return nil, errors.NewInternalError("failed to filter hive fields", err)
	}
	filtered := &models.Hive{}
	_, err = struccy.MergeMapStringFieldsToStruct(filtered, filteredMap, roles)
	if err != nil {
		return nil, errors.NewInternalError("failed to map filtered fields to hive struct", err)
	}

	return filtered, nil
}

// DeleteHive handles hive deletion with cascading cleanup
func (s *HubService) DeleteHive(ctx context.Context, id string) error {
	// Get hive to verify existence
	hive, err := s.Hives.Get(ctx, id)
	if err != nil {
		return err
	}

	// Start cleanup tasks
	if err := s.cleanupHiveData(ctx, hive); err != nil {
		nuts.L.Warnf("[HiveService] Partial cleanup failure for hive %s: %v", id, err)
	}

	nuts.L.Infof("[HiveService] Deleting hive: %s", id)
	return s.Hives.Delete(ctx, id)
}

// ListHives retrieves a paginated list of hives with role-based filtering
func (s *HubService) ListHives(ctx context.Context, offset, limit int) ([]*models.Hive, error) {
	if limit <= 0 || limit > 100 {
		limit = 50 // Default limit
	}
	if offset < 0 {
		offset = 0
	}

	hives, err := s.Hives.List(ctx, offset, limit)
	if err != nil {
		return nil, err
	}

	roles := GetUserRoles(ctx)
	filtered := make([]*models.Hive, 0, len(hives))

	for _, hive := range hives {
		filteredMap, err := struccy.StructToMapFieldsWithReadXS(hive, roles)
		if err != nil {
			nuts.L.Warnf("[HiveService] Failed to filter hive %s: %v", hive.ID, err)
			continue
		}
		filteredHive := &models.Hive{}
		_, err = struccy.MergeMapStringFieldsToStruct(filteredHive, filteredMap, roles)
		if err != nil {
			nuts.L.Warnf("[HiveService] Failed to map filtered fields to hive struct %s: %v", hive.ID, err)
			continue
		}
		filtered = append(filtered, filteredHive)
	}

	return filtered, nil
}

// GetHiveStatus retrieves comprehensive hive status information
func (s *HubService) GetHiveStatus(ctx context.Context, id string) (*HiveStatus, error) {
	hive, err := s.GetHive(ctx, id)
	if err != nil {
		return nil, err
	}

	// Get latest sensor readings
	readings, err := s.SensorData.GetLatestReadingsByHiveID(ctx, id)
	if err != nil {
		nuts.L.Warnf("[HiveService] Failed to get latest readings for hive %s: %v", id, err)
		readings = make(map[string]*models.SensorReading)
	}

	// Get latest files (images and sounds)
	files, err := s.Files.GetLatestFiles(ctx, id, "", []string{"image", "sound"})
	if err != nil {
		nuts.L.Warnf("[HiveService] Failed to get latest files for hive %s: %v", id, err)
		files = []*models.SensorFile{}
	}

	// Determine online status
	status := determineOnlineStatus(hive.LastSeen)

	// Find last activity time
	lastActivity := findLastActivity(hive)

	return &HiveStatus{
		Hive:         hive,
		LastReadings: readings,
		LastFiles:    files,
		OnlineStatus: status,
		LastActivity: lastActivity,
	}, nil
}

// UpdateHiveLastSeen updates the last seen timestamp for a hive
func (s *HubService) UpdateHiveLastSeen(ctx context.Context, id string) error {
	return s.Hives.UpdateLastSeen(ctx, id, time.Now())
}

// Helper functions

func (s *HubService) cleanupHiveData(ctx context.Context, hive *models.Hive) error {
	// Delete sensor data
	if err := s.SensorData.DeleteOldData(ctx, time.Now()); err != nil {
		return err
	}

	// Delete files
	if err := s.Files.DeleteOldFiles(ctx, time.Now()); err != nil {
		return err
	}

	return nil
}

func determineOnlineStatus(lastSeen time.Time) string {
	timeSinceLastSeen := time.Since(lastSeen)

	switch {
	case timeSinceLastSeen < 5*time.Minute:
		return "online"
	case timeSinceLastSeen < 15*time.Minute:
		return "away"
	default:
		return "offline"
	}
}

func findLastActivity(hive *models.Hive) time.Time {
	lastActivity := hive.LastSeen
	if hive.LastSensorDataReceived.After(lastActivity) {
		lastActivity = hive.LastSensorDataReceived
	}
	return lastActivity
}

// GetUserRoles retrieves user roles from context
// This should be implemented based on your authentication system
func GetUserRoles(ctx context.Context) []string {
	// This is a placeholder - implement based on your auth system
	if roles := ctx.Value("user_roles"); roles != nil {
		if r, ok := roles.([]string); ok {
			return r
		}
	}
	return []string{"guest"}
}
