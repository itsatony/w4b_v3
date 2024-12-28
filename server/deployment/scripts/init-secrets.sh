#!/bin/bash

SECRETS_DIR="../secrets"
mkdir -p $SECRETS_DIR

# Database users and passwords
echo "timescaledb" > $SECRETS_DIR/timescaledb_user.txt
echo "timescaledbpass" > $SECRETS_DIR/timescaledb_password.txt
echo "postgres_app" > $SECRETS_DIR/postgres_app_user.txt
echo "postgres_app_pass" > $SECRETS_DIR/postgres_app_password.txt
echo "keycloak_db" > $SECRETS_DIR/postgres_keycloak_user.txt
echo "keycloak_db_pass" > $SECRETS_DIR/postgres_keycloak_password.txt

# Keycloak admin credentials
echo "admin" > $SECRETS_DIR/keycloak_admin_user.txt
echo "admin_pass" > $SECRETS_DIR/keycloak_admin_password.txt
echo "keycloak_db" > $SECRETS_DIR/keycloak_db_user.txt
echo "keycloak_db_pass" > $SECRETS_DIR/keycloak_db_password.txt

# Grafana credentials
echo "admin" > $SECRETS_DIR/grafana_admin_user.txt
echo "admin_pass" > $SECRETS_DIR/grafana_admin_password.txt
echo "grafana_secret" > $SECRETS_DIR/grafana_oauth_secret.txt

chmod 600 $SECRETS_DIR/*
