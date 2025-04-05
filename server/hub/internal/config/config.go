package config

import (
	"fmt"
	"strings"
	"time"

	"github.com/spf13/viper"
)

// Config holds all configuration for the service
type Config struct {
	Server     ServerConfig
	Database   DatabaseConfig
	Keycloak   KeycloakConfig
	Redis      RedisConfig
	Monitoring MonitoringConfig
	FileStore  FileStoreConfig
}

type ServerConfig struct {
	Port            int           `mapstructure:"port"`
	Host            string        `mapstructure:"host"`
	ReadTimeout     time.Duration `mapstructure:"read_timeout"`
	WriteTimeout    time.Duration `mapstructure:"write_timeout"`
	ShutdownTimeout time.Duration `mapstructure:"shutdown_timeout"`
}

type DatabaseConfig struct {
	TimescaleDB PostgresConfig `mapstructure:"timescaledb"`
	AppDB       PostgresConfig `mapstructure:"postgres_app"`
}

type PostgresConfig struct {
	Host     string `mapstructure:"host"`
	Port     int    `mapstructure:"port"`
	User     string `mapstructure:"user"`
	Password string `mapstructure:"password"`
	DBName   string `mapstructure:"dbname"`
	SSLMode  string `mapstructure:"sslmode"`
}

type KeycloakConfig struct {
	URL          string `mapstructure:"url"`
	Realm        string `mapstructure:"realm"`
	ClientID     string `mapstructure:"client_id"`
	ClientSecret string `mapstructure:"client_secret"`
}

type RedisConfig struct {
	Host     string `mapstructure:"host"`
	Port     int    `mapstructure:"port"`
	Password string `mapstructure:"password"`
	DB       int    `mapstructure:"db"`
}

type MonitoringConfig struct {
	PrometheusPort     int    `mapstructure:"prometheus_port"`
	LogLevel           string `mapstructure:"log_level"`
	PrometheusEndpoint string `mapstructure:"prometheus_endpoint"`
	LokiEndpoint       string `mapstructure:"loki_endpoint"`
}

type FileStoreConfig struct {
	BasePath         string   `mapstructure:"base_path"`
	MaxFileSize      int64    `mapstructure:"max_file_size"`
	AllowedMimeTypes []string `mapstructure:"allowed_mime_types"`
}

// Load initializes configuration from environment variables and config file
func Load() (*Config, error) {
	viper.SetEnvPrefix("W4B")
	viper.SetEnvKeyReplacer(strings.NewReplacer(".", "__"))
	viper.AutomaticEnv()

	// Set defaults
	setDefaults()

	// Load config file if exists
	viper.SetConfigName("config")
	viper.SetConfigType("yaml")
	viper.AddConfigPath("./config")
	if err := viper.ReadInConfig(); err != nil {
		if _, ok := err.(viper.ConfigFileNotFoundError); !ok {
			return nil, fmt.Errorf("error reading config file: %w", err)
		}
	}

	var config Config
	if err := viper.Unmarshal(&config); err != nil {
		return nil, fmt.Errorf("error unmarshaling config: %w", err)
	}

	if err := validateConfig(&config); err != nil {
		return nil, fmt.Errorf("config validation error: %w", err)
	}

	return &config, nil
}

func setDefaults() {
	// Server defaults
	viper.SetDefault("server.port", 8080)
	viper.SetDefault("server.host", "0.0.0.0")
	viper.SetDefault("server.read_timeout", "15s")
	viper.SetDefault("server.write_timeout", "15s")
	viper.SetDefault("server.shutdown_timeout", "30s")

	// Database defaults
	viper.SetDefault("database.timescaledb.sslmode", "disable")
	viper.SetDefault("database.postgres_app.sslmode", "disable")

	// Redis defaults
	viper.SetDefault("redis.db", 0)

	// Monitoring defaults
	viper.SetDefault("monitoring.prometheus_port", 9090)
	viper.SetDefault("monitoring.log_level", "info")
	viper.SetDefault("monitoring.prometheus_endpoint", "http://localhost:9090")
	viper.SetDefault("monitoring.loki_endpoint", "http://localhost:3100")

	// FileStore defaults
	viper.SetDefault("filestore.max_file_size", 10*1024*1024) // 10MB
}

func validateConfig(config *Config) error {
	// Add validation logic here
	// For now, just check required fields are not empty
	if config.Database.TimescaleDB.Host == "" {
		return fmt.Errorf("timescaledb host is required")
	}
	if config.Database.AppDB.Host == "" {
		return fmt.Errorf("postgres app host is required")
	}
	if config.Keycloak.URL == "" {
		return fmt.Errorf("keycloak URL is required")
	}
	return nil
}
