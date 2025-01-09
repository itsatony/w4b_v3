// FilePath: server/hub/internal/models/models.hive.go
package models

import "time"

type Hive struct {
	ID                     string      `json:"id" db:"id"`
	Name                   string      `json:"name" db:"name"`
	Description            string      `json:"description" db:"description"`
	ProfilePictureUrl      string      `json:"profile_picture_url" db:"profile_picture_url"`
	Location               string      `json:"location" db:"location"`
	Latitude               float64     `json:"latitude" db:"latitude"`
	Longitude              float64     `json:"longitude" db:"longitude"`
	SystemVersion          string      `json:"system_version" db:"system_version"`
	Timezone               string      `json:"timezone" db:"timezone"`
	Networks               []NetConfig `json:"network_config" readxs:"owner,system,superadmin,edgeadmin" writexs:"owner,system,superadmin,edgeadmin"`
	SSHPublicKey           string      `json:"ssh_public_key" readxs:"owner,system,superadmin,edgeadmin" writexs:"owner,system,superadmin,edgeadmin"`
	VPNConfig              string      `json:"vpn_config" readxs:"owner,system,superadmin,edgeadmin" writexs:"owner,system,superadmin,edgeadmin"`
	HiveConfigYaml         string      `json:"hive_config_yaml" readxs:"owner,system,superadmin,edgeadmin" writexs:"owner,system,superadmin,edgeadmin"`
	LastSeen               time.Time   `json:"last_seen" db:"last_seen"`
	LastSensorDataReceived time.Time   `json:"last_sensor_data_received" db:"last_sensor_data_received"`
	CreatedAt              time.Time   `json:"created_at" db:"created_at"`
	UpdatedAt              time.Time   `json:"updated_at" db:"updated_at"`
}

type NetConfig struct {
	ID               string    `json:"id" db:"id"`
	NetworkMode      string    `json:"network_mode" db:"network_mode"`
	NetworkIP        string    `json:"network_ip" db:"network_ip"`
	NetworkGateway   string    `json:"network_gateway" db:"network_gateway"`
	NetworkDNS       string    `json:"network_dns" db:"network_dns"`
	NetworkSubnet    string    `json:"network_subnet" db:"network_subnet"`
	NetworkMAC       string    `json:"network_mac" db:"network_mac"`
	NetworkSignal    string    `json:"network_signal" db:"network_signal"`
	NetworkType      string    `json:"network_type" db:"network_type"`
	NetworkStatus    string    `json:"network_status" db:"network_status"`
	NetworkLastSeen  time.Time `json:"network_last_seen" db:"network_last_seen"`
	NetworkCreatedAt time.Time `json:"network_created_at" db:"network_created_at"`
	NetworkUpdatedAt time.Time `json:"network_updated_at" db:"network_updated_at"`
}

type NetConfigWifi struct {
	NetConfig
	SSID          string `json:"ssid" db:"ssid"`
	Password      string `json:"password" db:"password"`
	Security      string `json:"security" db:"security"`
	Channel       string `json:"channel" db:"channel"`
	SignalQuality string `json:"signal_quality" db:"signal_quality"`
}

type NetConfigSim struct {
	NetConfig
	APN           string `json:"apn" db:"apn"`
	PIN           string `json:"pin" db:"pin"`
	SignalQuality string `json:"signal_quality" db:"signal_quality"`
}

type NetConfigLan struct {
	NetConfig
	MAC           string `json:"mac" db:"mac"`
	Speed         string `json:"speed" db:"speed"`
	Duplex        string `json:"duplex" db:"duplex"`
	SignalQuality string `json:"signal_quality" db:"signal_quality"`
}

type HiveComment struct {
	ID        string    `json:"id" db:"id"`
	HiveID    string    `json:"hive_id" db:"hive_id"`
	UserID    string    `json:"user_id" db:"user_id"`
	Text      string    `json:"text" db:"text"`
	CreatedAt time.Time `json:"created_at" db:"created_at"`
	UpdatedAt time.Time `json:"updated_at" db:"updated_at"`
}
