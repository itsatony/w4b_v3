#!/bin/bash

# Stop and remove existing container
docker-compose down w4b_postgres_keycloak
docker volume rm w4b_containers_w4b_postgres_keycloak_data

# Create data directory with correct permissions
mkdir -p ./data/postgres_keycloak
chown -R 999:999 ./data/postgres_keycloak
chmod 700 ./data/postgres_keycloak

# Create config directory if it doesn't exist
mkdir -p ./config/postgres_keycloak
chmod 755 ./config/postgres_keycloak

# Start the container
docker-compose up -d w4b_postgres_keycloak

# Wait for container to be ready
echo "Waiting for PostgreSQL to start..."
sleep 10

# Check logs
docker-compose logs w4b_postgres_keycloak
