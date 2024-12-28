#!/bin/bash

# Define base directory
BASE_DIR="/home/itsatony/code/w4b_v3/server/w4b_containers"
DATA_DIR="$BASE_DIR/data"

# Data directories to create
DIRS=(
    "timescaledb"
    "postgres_app"
    "postgres_keycloak"
    "redis"
    "prometheus"
    "grafana"
    "loki"
    "loki/wal"
    "vector"
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

# Set permissions
echo "Setting permissions..."
chown -R 1000:1000 "$DATA_DIR"
chmod -R 755 "$DATA_DIR"

# Special permissions for specific services
chmod -R 777 "$DATA_DIR/loki"

echo "Data directories setup complete!"
echo "Location: $DATA_DIR"
ls -la "$DATA_DIR"
