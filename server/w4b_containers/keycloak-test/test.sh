#!/bin/bash

set -e  # Exit on error

function cleanup() {
    echo "Cleaning up..."
    if podman-compose ps &>/dev/null; then
        podman-compose down -v
    fi
    
    if podman network exists test_network &>/dev/null; then
        podman network rm -f test_network
    fi
    
    if [ -d "data" ]; then
        sudo rm -rf data
    fi
}

function setup() {
    echo "Setting up test environment..."
    
    # Create a dedicated network
    echo "Creating network..."
    podman network create test_network \
        --driver bridge \
        --subnet 10.89.0.0/24 \
        --gateway 10.89.0.1 || {
            echo "Failed to create network"
            exit 1
        }
        
    # Wait for network to be ready
    sleep 2
}

function start_test() {
    cleanup
    setup
    echo "Starting test environment..."
    podman-compose up -d
    echo "Waiting for containers to start..."
    sleep 5
    echo "Viewing logs..."
    podman-compose logs -f
}

case "$1" in
    "start")
        start_test
        ;;
    "clean")
        cleanup
        ;;
    *)
        echo "Usage: $0 {start|clean}"
        exit 1
        ;;
esac
