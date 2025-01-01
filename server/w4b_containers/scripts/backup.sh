#!/bin/bash

BACKUP_DIR="/var/backups/w4b"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="${BACKUP_DIR}/${DATE}"

# Ensure backup directory exists
mkdir -p "$BACKUP_PATH"

# Get list of volumes
VOLUMES=$(podman volume ls -q | grep '^w4b_')

# Backup each volume
for volume in $VOLUMES; do
    echo "Backing up volume: $volume"
    podman run --rm \
        -v "$volume:/source:ro" \
        -v "$BACKUP_PATH:/backup" \
        alpine tar czf "/backup/${volume}.tar.gz" -C /source .
done

# Create backup manifest
echo "Creating backup manifest..."
echo "Backup Date: $DATE" > "$BACKUP_PATH/manifest.txt"
echo "Volumes:" >> "$BACKUP_PATH/manifest.txt"
for volume in $VOLUMES; do
    echo "- $volume" >> "$BACKUP_PATH/manifest.txt"
done

# Cleanup old backups (keep last 7 days)
find "$BACKUP_DIR" -type d -mtime +7 -exec rm -rf {} \;

echo "Backup completed: $BACKUP_PATH"
