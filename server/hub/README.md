# W4B Hub Server

## Overview

The W4B Hub Server is the central component of the we4bee version3 (w4b) beehive monitoring system. It provides a secure, scalable API service for managing beehives, sensors, and their data.

## Architecture Decisions

### Core Technology Stack

- **Language**: Go 1.21+
- **Framework**: Standard library with selected packages
- **API Style**: RESTful with OpenAPI documentation
- **Authentication**: Keycloak (OIDC/OAuth2)
- **Databases**:
  - TimescaleDB for sensor data
  - PostgreSQL for application data
  - Redis for caching and rate limiting

### Key Dependencies

- `github.com/gorilla/mux` - HTTP routing
- `github.com/spf13/viper` - Configuration management
- `github.com/vaudience/go-nuts` - Utility functions and logging
- `github.com/jmoiron/sqlx` - Database operations
- `github.com/redis/go-redis/v9` - Redis client
- `github.com/swaggo/swag` - OpenAPI documentation

### Configuration Management

- Environment variables for sensitive data
- YAML configuration files for general settings
- Layered priority: ENV > config file > defaults
- Strict configuration validation at startup

### Database Design

- **TimescaleDB**:
  - Partitioning based on time ranges
  - Automated data retention policies
  - Optimized indexes for time-series queries
  - Compression for older data

### Authentication & Authorization

- Keycloak for identity management
- Role-based access control (RBAC)
- Service accounts for edge devices
- Defined roles:
  - superadmin
  - edgeadmin
  - edgedevice
  - user
  - guest

### File Storage

- Local storage with abstraction layer
- Organized directory structure
- Retention policies based on data age
- Future-ready for S3 migration

### Data Retention

- Time-based retention policies
- Automated data aggregation
- Dynamic sampling rate adjustment
- Anomaly-based retention rules

### Monitoring & Observability

- Prometheus metrics
- Custom health checks
- Loki log aggregation
- Vector log processing

### Error Handling

- Custom error package
- Consistent error responses
- Detailed logging
- Rate limiting with headers

## API Versioning

- URL path versioning (e.g., /v1/...)
- Single version support initially

## Project Structure

```tree
hub/
├── api/              # API implementation
├── cmd/              # Command-line entrypoints
├── config/           # Configuration files
├── internal/         # Private application code
│   ├── models/       # Data models
│   ├── errors/       # Custom error types
│   ├── repository/   # Database operations
│   ├── service/      # Business logic
│   ├── server/       # HTTP server
└── pkg/             # Public libraries
```

## Configuration

Configuration is managed through:

1. Environment variables
2. config.yaml file
3. Default values

Required environment variables:

```env
W4B__POSTGRES_APP_HOST=localhost
W4B__POSTGRES_APP_PORT=5432
W4B__POSTGRES_APP_USER=w4b
W4B__POSTGRES_APP_PASSWORD=secret
W4B__POSTGRES_APP_DBNAME=w4b

W4B__TIMESCALEDB_HOST=localhost
W4B__TIMESCALEDB_PORT=5432
W4B__TIMESCALEDB_USER=w4b
W4B__TIMESCALEDB_PASSWORD=secret
W4B__TIMESCALEDB_DBNAME=w4b

W4B__KEYCLOAK_URL=http://localhost:30080
W4B__KEYCLOAK_REALM=w4b
W4B__KEYCLOAK_CLIENT_ID=w4b-api
W4B__KEYCLOAK_CLIENT_SECRET=secret
```
