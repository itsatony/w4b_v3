// FilePath: server/hub/internal/models/models.composite.go
package models

import "time"

// LatestSensorData combines the latest sensor reading with its most recent files
type LatestSensorData struct {
	Reading   *SensorReading `json:"reading"`
	ImageFile *SensorFile    `json:"image_file,omitempty"`
	SoundFile *SensorFile    `json:"sound_file,omitempty"`
	UpdatedAt time.Time      `json:"updated_at"`
}

// HiveLatestData represents the latest data for all sensors in a hive
type HiveLatestData struct {
	HiveID    string                      `json:"hive_id"`
	Sensors   map[string]LatestSensorData `json:"sensors"`
	UpdatedAt time.Time                   `json:"updated_at"`
}
