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
	FileName  string    `json:"file_name" db:"file_name"`
	FileType  string    `json:"file_type" db:"file_type"` // "image" or "sound"
	FileSize  int64     `json:"file_size" db:"file_size"` // File size in bytes
	FilePath  string    `json:"file_path" db:"file_path"` // Relative path in storage
	MimeType  string    `json:"mime_type" db:"mime_type"`
	Timestamp time.Time `json:"timestamp" db:"timestamp"`
	CreatedAt time.Time `json:"created_at" db:"created_at"`
}
