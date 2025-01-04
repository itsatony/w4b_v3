// FilePath: server/hub/internal/models/models.sensor_data.go
package models

import "time"

// SensorReading represents a single sensor measurement
type SensorReading struct {
	ID        string    `json:"id" db:"id"`
	SensorID  string    `json:"sensor_id" db:"sensor_id"`
	Value     float64   `json:"value" db:"value"`
	Timestamp time.Time `json:"timestamp" db:"timestamp"`
}

// SensorAggregate represents aggregated sensor data
type SensorAggregate struct {
	SensorID  string    `json:"sensor_id" db:"sensor_id"`
	Min       float64   `json:"min" db:"min"`
	Max       float64   `json:"max" db:"max"`
	Avg       float64   `json:"avg" db:"avg"`
	Count     int       `json:"count" db:"count"`
	StartTime time.Time `json:"start_time" db:"start_time"`
	EndTime   time.Time `json:"end_time" db:"end_time"`
}

// SensorFile represents a file (image/sound) associated with a sensor
type SensorFile struct {
	ID        string    `json:"id" db:"id"`
	HiveID    string    `json:"hive_id" db:"hive_id"`
	SensorID  string    `json:"sensor_id" db:"sensor_id"`
	Type      string    `json:"type" db:"type"` // "image" or "sound"
	Path      string    `json:"path" db:"path"` // Relative path in storage
	Size      int64     `json:"size" db:"size"` // File size in bytes
	MimeType  string    `json:"mime_type" db:"mime_type"`
	Timestamp time.Time `json:"timestamp" db:"timestamp"`
	CreatedAt time.Time `json:"created_at" db:"created_at"`
}
