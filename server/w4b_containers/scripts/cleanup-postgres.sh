#!/bin/bash

# Stop all containers
docker-compose down

# Force remove the container
docker rm -f w4b_postgres_keycloak

# Force remove the volume
docker volume rm -f w4b_containers_w4b_postgres_keycloak_data

# Remove any related networks
docker network prune -f

# Clean up data directory
rm -rf ./data/postgres_keycloak/*
