// FilePath: server/hub/internal/models/models.sensor.go
package models

import (
	"database/sql/driver"
	"encoding/json"
	"time"
)

// JSON is a wrapper around map[string]interface{} for database storage
type JSON map[string]interface{}

// Value implements the driver.Valuer interface
func (j JSON) Value() (driver.Value, error) {
	return json.Marshal(j)
}

// Scan implements the sql.Scanner interface
func (j *JSON) Scan(value interface{}) error {
	bytes, ok := value.([]byte)
	if !ok {
		return nil
	}
	return json.Unmarshal(bytes, &j)
}

type SensorType string

const (
	Temperature SensorType = "temperature"
	Humidity    SensorType = "humidity"
	Weight      SensorType = "weight"
	Sound       SensorType = "sound"
	Image       SensorType = "image"
	Pressure    SensorType = "pressure"
	Light       SensorType = "light"
	Motion      SensorType = "motion"
	Gas         SensorType = "gas"
	Vibration   SensorType = "vibration"
	Other       SensorType = "other"
)

type CalibrationMethod string

const (
	Linear     CalibrationMethod = "linear"
	Polynomial CalibrationMethod = "polynomial"
	Manual     CalibrationMethod = "manual"
	Offset     CalibrationMethod = "offset"
	Scale      CalibrationMethod = "scale"
)

type Sensor struct {
	ID            string          `json:"id" db:"id"`
	HiveID        string          `json:"hive_id" db:"hive_id"`
	Name          string          `json:"name" db:"name"`
	Description   string          `json:"description" db:"description"`
	Type          SensorType      `json:"type" db:"type"`
	Model         string          `json:"model" db:"model"`
	Interface     string          `json:"interface" db:"interface"`
	Unit          string          `json:"unit" db:"unit"`
	Precision     int             `json:"precision" db:"precision"`
	MinValue      float64         `json:"min_value" db:"min_value"`
	MaxValue      float64         `json:"max_value" db:"max_value"`
	LastValue     float64         `json:"last_value" db:"last_value"`
	LastValueTime time.Time       `json:"last_value_time" db:"last_value_time"`
	Status        string          `json:"status" db:"status"`
	ErrorMessage  string          `json:"error_message,omitempty" db:"error_message"`
	Calibration   CalibrationInfo `json:"calibration" db:"calibration"`
	Metadata      JSON            `json:"metadata" db:"metadata"`
	CreatedAt     time.Time       `json:"created_at" db:"created_at"`
	UpdatedAt     time.Time       `json:"updated_at" db:"updated_at"`
}

type CalibrationInfo struct {
	Method          CalibrationMethod  `json:"method" db:"method"`
	Points          []CalibrationPoint `json:"points,omitempty" db:"points"`
	Coefficients    []float64          `json:"coefficients,omitempty" db:"coefficients"`
	Offset          float64            `json:"offset,omitempty" db:"offset"`
	Scale           float64            `json:"scale,omitempty" db:"scale"`
	ReferenceTemp   float64            `json:"reference_temp,omitempty" db:"reference_temp"`
	TempCoefficient float64            `json:"temp_coefficient,omitempty" db:"temp_coefficient"`
	LastCalibration time.Time          `json:"last_calibration" db:"last_calibration"`
	ValidUntil      time.Time          `json:"valid_until,omitempty" db:"valid_until"`
	Uncertainty     float64            `json:"uncertainty,omitempty" db:"uncertainty"`
	CalibrationLog  []CalibrationLog   `json:"calibration_log,omitempty" db:"calibration_log"`
}

type CalibrationPoint struct {
	Input        float64   `json:"input" db:"input"`
	ReadoutValue float64   `json:"readout_value" db:"readout_value"`
	Temperature  float64   `json:"temperature,omitempty" db:"temperature"`
	Humidity     float64   `json:"humidity,omitempty" db:"humidity"`
	CreatedAt    time.Time `json:"created_at" db:"created_at"`
}

type CalibrationLog struct {
	Timestamp   time.Time `json:"timestamp" db:"timestamp"`
	UserID      string    `json:"user_id" db:"user_id"`
	Description string    `json:"description" db:"description"`
	Changes     JSON      `json:"changes" db:"changes"`
}
