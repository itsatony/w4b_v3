#!/bin/bash
# Raspberry Pi Image Generator for Hive System
# Version: 1.0.0
# Description: Generates customized Raspberry Pi images for hive nodes

set -e

# Configuration
WORK_DIR="/opt/hive-generator"
RASPIOS_URL="https://downloads.raspberrypi.org/raspios_lite_arm64_latest"
MOUNT_POINT="${WORK_DIR}/mnt"
CACHE_DIR="${WORK_DIR}/cache"

# Required environment variables
# HIVE_ID
# HIVE_NAME
# VPN_CONFIG
# SSH_PUBLIC_KEY
# DB_PASSWORD
# TIMEZONE

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "${WORK_DIR}/generator.log"
}

check_requirements() {
    for cmd in kpartx losetup wget; do
        if ! command -v $cmd &> /dev/null; then
            log "ERROR: Required command '$cmd' not found"
            exit 1
        fi
    done
}

prepare_workspace() {
    mkdir -p "${WORK_DIR}" "${MOUNT_POINT}" "${CACHE_DIR}"
    
    # Download latest Raspberry Pi OS if needed
    if [ ! -f "${CACHE_DIR}/raspios.img" ]; then
        log "Downloading Raspberry Pi OS..."
        wget -qO "${CACHE_DIR}/raspios.img.gz" "${RASPIOS_URL}"
        gunzip -f "${CACHE_DIR}/raspios.img.gz"
    fi
    
    # Create working copy
    cp "${CACHE_DIR}/raspios.img" "${WORK_DIR}/${HIVE_ID}.img"
}

mount_image() {
    local img_path="${WORK_DIR}/${HIVE_ID}.img"
    local loop_device=$(losetup -f)
    
    losetup "$loop_device" "$img_path"
    kpartx -av "$loop_device"
    
    # Mount boot and root partitions
    mount "/dev/mapper/$(basename $loop_device)p1" "${MOUNT_POINT}/boot"
    mount "/dev/mapper/$(basename $loop_device)p2" "${MOUNT_POINT}/root"
}

configure_system() {
    # Base configuration
    cat > "${MOUNT_POINT}/root/etc/hostname" << EOF
${HIVE_ID}
EOF
    
    # Setup TimescaleDB
    cat > "${MOUNT_POINT}/root/etc/postgresql/13/main/postgresql.conf" << EOF
listen_addresses = 'localhost,10.10.0.1'
max_connections = 100
shared_buffers = 128MB
effective_cache_size = 512MB
maintenance_work_mem = 128MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 8MB
min_wal_size = 1GB
max_wal_size = 4GB
EOF

    # Setup SSH
    mkdir -p "${MOUNT_POINT}/root/root/.ssh"
    echo "${SSH_PUBLIC_KEY}" > "${MOUNT_POINT}/root/root/.ssh/authorized_keys"
    chmod 700 "${MOUNT_POINT}/root/root/.ssh"
    chmod 600 "${MOUNT_POINT}/root/root/.ssh/authorized_keys"

    # Setup WireGuard
    mkdir -p "${MOUNT_POINT}/root/etc/wireguard"
    echo "${VPN_CONFIG}" > "${MOUNT_POINT}/root/etc/wireguard/wg0.conf"
    chmod 600 "${MOUNT_POINT}/root/etc/wireguard/wg0.conf"

    # First boot script
    cat > "${MOUNT_POINT}/boot/firstboot.sh" << 'EOF'
#!/bin/bash
set -e

# Enable required services
systemctl enable ssh
systemctl enable postgresql
systemctl enable wg-quick@wg0

# Initialize TimescaleDB
sudo -u postgres createdb hivedb
sudo -u postgres psql -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"

# Setup firewall
ufw allow from 10.10.0.0/24 to any port 22
ufw allow from 10.10.0.0/24 to any port 5432
ufw --force enable

# Remove first boot script
rm /boot/firstboot.sh
EOF

    chmod +x "${MOUNT_POINT}/boot/firstboot.sh"
}

cleanup() {
    umount "${MOUNT_POINT}/boot" "${MOUNT_POINT}/root"
    kpartx -d "/dev/$(basename $loop_device)"
    losetup -d "$loop_device"
}

main() {
    check_requirements
    prepare_workspace
    mount_image
    configure_system
    cleanup
    
    log "Image generation complete: ${WORK_DIR}/${HIVE_ID}.img"
}

main "$@"