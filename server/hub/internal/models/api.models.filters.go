package models

import "time"

// SensorFilters defines the available filter options for sensors
type SensorFilters struct {
	HiveID    string     `json:"hive_id"`
	Type      SensorType `json:"type"`
	Status    string     `json:"status"`
	CreatedAt *TimeRange `json:"created_at"`
}

// TimeRange represents a time range filter
type TimeRange struct {
	Start *Time `json:"start"`
	End   *Time `json:"end"`
}

// Time is a wrapper around time.Time for custom JSON marshaling
type Time struct {
	time.Time
}
