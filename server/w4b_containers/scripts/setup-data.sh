#!/bin/bash

# Define base directory
BASE_DIR="/home/itsatony/code/w4b_v3/server/w4b_containers"
DATA_DIR="$BASE_DIR/data"

# Data directories to create with correct w4b_ prefix
DIRS=(
    "w4b_timescaledb"
    "w4b_postgres_app"
    "w4b_postgres_keycloak"
    "w4b_redis"
    "w4b_prometheus"
    "w4b_grafana"
    "w4b_loki"
    "w4b_loki/wal"
    "w4b_vector"
)

# Parse arguments
FORCE=0
while [[ $# -gt 0 ]]; do
    case $1 in
        --force)
            FORCE=1
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check if directories should be wiped
if [ "$FORCE" -eq 1 ]; then
    echo "Warning: --force flag detected. This will delete all existing data!"
    read -p "Are you sure you want to continue? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Removing existing data directories..."
        rm -rf "$DATA_DIR"/*
    else
        echo "Operation cancelled."
        exit 1
    fi
fi

# Create directories
echo "Creating data directories..."
for dir in "${DIRS[@]}"; do
    mkdir -p "$DATA_DIR/$dir"
    echo "Created $DATA_DIR/$dir"
done

# Set permissions for postgres directories (UID 999 for postgres user)
echo "Setting specific permissions..."
for dir in w4b_postgres_* w4b_timescaledb; do
    chown -R 999:999 "$DATA_DIR/$dir"
    chmod -R 700 "$DATA_DIR/$dir"
    echo "Set postgres permissions for $dir"
done

# Set permissions for other services (UID 1000)
for dir in w4b_redis w4b_prometheus w4b_grafana w4b_vector; do
    chown -R 1000:1000 "$DATA_DIR/$dir"
    chmod -R 755 "$DATA_DIR/$dir"
    echo "Set standard permissions for $dir"
done

# Special permissions for Loki
chown -R 1000:1000 "$DATA_DIR/w4b_loki"
chmod -R 777 "$DATA_DIR/w4b_loki"
echo "Set special permissions for Loki"

echo "Data directories setup complete!"
echo "Location: $DATA_DIR"
ls -la "$DATA_DIR"

# Create necessary config directories if they don't exist
CONFIG_DIR="$BASE_DIR/config"
mkdir -p "$CONFIG_DIR"/{postgres_keycloak,timescaledb,postgres_app,redis,prometheus,grafana,loki,vector}
echo "Config directories created at $CONFIG_DIR"
