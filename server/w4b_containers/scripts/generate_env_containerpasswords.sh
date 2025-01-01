#!/bin/bash

# Function to generate a secure random password
generate_password() {
    openssl rand -base64 24 | tr -d '/+=' | cut -c1-24
}

# Determine target directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -d "../hivectl" ]; then
    TARGET_DIR="../hivectl"
else
    TARGET_DIR=".."
fi

# Create .env file
cat > "$TARGET_DIR/.env" << EOF
# Database Credentials
TIMESCALEDB_USER=timescaledb
TIMESCALEDB_PASSWORD=$(generate_password)
POSTGRES_APP_USER=postgres_app
POSTGRES_APP_PASSWORD=$(generate_password)
POSTGRES_KEYCLOAK_USER=keycloak_db
POSTGRES_KEYCLOAK_PASSWORD=$(generate_password)

# Keycloak Admin Credentials
KEYCLOAK_ADMIN_USER=admin
KEYCLOAK_ADMIN_PASSWORD=$(generate_password)

# Grafana Credentials
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=$(generate_password)
GRAFANA_OAUTH_SECRET=$(generate_password)
EOF

chmod 600 "$TARGET_DIR/.env"
echo "Environment file generated at $TARGET_DIR/.env"
