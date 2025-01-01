#!/bin/bash

echo "Stopping all containers..."
podman-compose down -v

# echo "Removing all containers..."
# podman rm -f -a

# echo "Removing all pods..."
# podman pod rm -f -a

echo "Removing all networks..."
podman network rm -f $(podman network ls -q)

echo "Cleaning up CNI configurations..."
sudo rm -f /etc/cni/net.d/*
rm -f $HOME/.config/cni/net.d/*

echo "Resetting Podman..."
podman system reset --force

echo "Done! Please try running ./test.sh start again"
