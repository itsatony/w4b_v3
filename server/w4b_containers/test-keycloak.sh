#!/bin/bash

echo "=== Starting Keycloak Integration Test ==="

# Function to check if a container is running
check_container_status() {
    local container=$1
    local max_attempts=$2
    local attempt=1
    
    echo "Checking status of $container..."
    while [ $attempt -le $max_attempts ]; do
        status=$(podman inspect --format='{{.State.Status}}' $container 2>/dev/null)
        if [ "$status" = "running" ]; then
            echo "$container is running!"
            return 0
        fi
        echo "Attempt $attempt/$max_attempts: $container status: $status"
        attempt=$((attempt+1))
        sleep 5
    done
    return 1
}

check_keycloak() {
    local max_attempts=36
    local attempt=1

    echo "Checking status of keycloak_test..."
    while [ $attempt -le $max_attempts ]; do
        status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:30080/health/ready | grep -c "200")
        if [ $status -eq 1 ]; then
            echo "Keycloak is running!"
            return 0
        fi
        echo "Attempt $attempt/$max_attempts: Keycloak status: $status"
        attempt=$((attempt+1))
        sleep 5
    done
    return 1
}

# Clean up function
cleanup() {
    echo "Cleaning up containers..."
    podman-compose -f test-keycloak.yaml down -v
    podman volume rm keycloak_db_test keycloak_conf_test 2>/dev/null || true
}

# Trap for cleanup on script exit
trap cleanup EXIT

# Start fresh
cleanup

# Create required directories with proper permissions
mkdir -p config/postgres_keycloak config/keycloak
chmod -R 755 config

# Start the containers
echo "Starting containers..."
podman-compose -f test-keycloak.yaml up -d

# Check PostgreSQL
echo "Checking PostgreSQL..."
if ! check_container_status postgres_keycloak_test 12; then
    echo "PostgreSQL failed to start"
    podman logs postgres_keycloak_test
    exit 1
fi

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
sleep 10

# Test PostgreSQL connection
echo "Testing PostgreSQL connection..."
podman exec postgres_keycloak_test pg_isready -U "$W4B__POSTGRES_KEYCLOAK_USER" -d keycloak
if [ $? -ne 0 ]; then
    echo "Failed to connect to PostgreSQL"
    podman logs postgres_keycloak_test
    exit 1
fi

# Add after PostgreSQL starts
echo "Testing PostgreSQL network connectivity..."
podman exec postgres_keycloak_test bash -c "pg_isready -h localhost -p 5432"
podman exec keycloak_test bash -c "nc -zv postgres_keycloak 5432"

# Add after PostgreSQL starts
echo "Testing network connectivity..."
podman exec postgres_keycloak_test bash -c "nc -zv 10.99.0.10 5432"
podman exec postgres_keycloak_test bash -c "psql -U ${W4B__POSTGRES_KEYCLOAK_USER} -d keycloak -c '\l'"

# Add after PostgreSQL connection test
echo "Checking PostgreSQL logs..."
podman logs postgres_keycloak_test

# Add before starting Keycloak
echo "Verifying database setup..."
podman exec postgres_keycloak_test bash -c "psql -U ${W4B__POSTGRES_KEYCLOAK_USER} -d keycloak -c '\du'"

# Check Keycloak
echo "Checking Keycloak..."
if ! check_keycloak; then
    echo "Keycloak failed to start. Checking logs..."
    podman logs keycloak_test
    exit 1
fi

# Wait for Keycloak to be ready
echo "Waiting for Keycloak to be ready..."
sleep 20

# Add more verbose Keycloak startup
echo "Starting Keycloak with verbose logging..."
podman logs -f keycloak_test &

# Test Keycloak API
echo "Testing Keycloak API..."
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health/ready
if [ $? -ne 0 ]; then
    echo "Failed to connect to Keycloak API"
    podman logs keycloak_test
    exit 1
fi

echo "=== Test Complete ==="
