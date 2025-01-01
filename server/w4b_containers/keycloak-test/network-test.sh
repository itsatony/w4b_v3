#!/bin/bash

echo "Testing network configuration..."

echo "Current networks:"
podman network ls

echo -e "\nNetwork inspection of test_network:"
podman network inspect test_network

echo -e "\nContainer details:"
for container in postgres_keycloak_test db_test; do
    echo -e "\n$container details:"
    podman inspect $container | grep -A 2 "\"Networks\""
    echo "IP Address:"
    podman inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $container
done

echo -e "\nTesting DNS resolution from db_test container:"
podman exec db_test nslookup postgres_keycloak_test

echo -e "\nTesting ping from db_test container:"
podman exec db_test ping -c 1 postgres_keycloak_test || true

echo -e "\nChecking hosts file in db_test:"
podman exec db_test cat /etc/hosts

echo -e "\nChecking resolv.conf in db_test:"
podman exec db_test cat /etc/resolv.conf

echo -e "\nChecking PostgreSQL container logs:"
podman logs postgres_keycloak_test | tail -n 5
