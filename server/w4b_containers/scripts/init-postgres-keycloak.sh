#!/bin/bash

# Create required directories
mkdir -p ../data/postgres_keycloak
mkdir -p ../config/postgres_keycloak

# Set correct permissions for data directory
chown -R 999:999 ../data/postgres_keycloak
chmod -R 700 ../data/postgres_keycloak

# Set correct permissions for config files
chmod 644 ../config/postgres_keycloak/*.conf
