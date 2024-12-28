#!/bin/bash

# Ensure clean state
docker-compose down w4b_postgres_keycloak
docker rm -f w4b_postgres_keycloak
docker volume rm -f w4b_containers_w4b_postgres_keycloak_data

# Create and set permissions for data directory
mkdir -p ./data/postgres_keycloak
chmod -R 700 ./data/postgres_keycloak
chown -R 999:999 ./data/postgres_keycloak

# Start PostgreSQL
docker-compose up -d w4b_postgres_keycloak

# Wait and check logs
echo "Waiting for PostgreSQL to initialize..."
sleep 5
docker-compose logs w4b_postgres_keycloak
