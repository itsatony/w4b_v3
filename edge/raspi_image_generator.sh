#!/bin/bash
# Raspberry Pi Image Generator for Hive System
# Version: 1.0.0
# Description: Generates customized Raspberry Pi images for hive nodes

set -e

# Get script directory for relative paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Configuration
WORK_DIR="/tmp/hive-generator"
RASPIOS_URL="https://downloads.raspberrypi.org/raspios_lite_arm64_latest"
CACHE_DIR="${WORK_DIR}/cache"
HIVE_CONFIG_DIR="${REPO_ROOT}/hive_config_manager/hives"

# Required environment variables or command-line parameters
# - HIVE_ID: The ID of the hive to configure (must exist in hive_config_manager)
# - or path to YAML config file

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "${WORK_DIR}/generator.log"
}

error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $*" | tee -a "${WORK_DIR}/generator.log" >&2
    exit 1
}

check_requirements() {
    for cmd in udisksctl wget xz python3 yaml; do
        if ! command -v $cmd &> /dev/null; then
            error "Required command '$cmd' not found"
        fi
    done
    
    # Check if udisks2 is installed
    if ! dpkg -l | grep -q udisks2; then
        error "udisks2 package is not installed. Please run: sudo apt-get install udisks2"
    fi
    
    # Check if PyYAML is installed
    if ! python3 -c "import yaml" &> /dev/null; then
        error "PyYAML is not installed. Please run: pip3 install PyYAML"
    fi
}

prepare_workspace() {
    mkdir -p "${WORK_DIR}" "${CACHE_DIR}"
    
    # Download latest Raspberry Pi OS if needed
    if [ ! -f "${CACHE_DIR}/raspios.img" ]; then
        log "Downloading Raspberry Pi OS..."
        wget -qO "${CACHE_DIR}/raspios.img.xz" "${RASPIOS_URL}"
        log "Decompressing Raspberry Pi OS image..."
        xz -d "${CACHE_DIR}/raspios.img.xz"
    fi
    
    # Create working copy
    cp "${CACHE_DIR}/raspios.img" "${WORK_DIR}/${HIVE_ID}.img"
}

mount_image() {
    local img_path="${WORK_DIR}/${HIVE_ID}.img"
    
    # Mount the image using udisksctl (no root required)
    log "Setting up loop device for Raspberry Pi OS image..."
    LOOP_DEV_INFO=$(udisksctl loop-setup -f "$img_path")
    LOOP_DEV=$(echo "$LOOP_DEV_INFO" | grep -o '/dev/loop[0-9]*')
    log "Loop device created: $LOOP_DEV"
    
    # Wait a moment for partitions to be detected
    sleep 2
    
    # Mount the boot partition (p1)
    log "Mounting boot partition..."
    BOOT_MOUNT_INFO=$(udisksctl mount -b "${LOOP_DEV}p1")
    BOOT_PATH=$(echo "$BOOT_MOUNT_INFO" | grep -o '/media/[^ ]*')
    log "Boot partition mounted at: $BOOT_PATH"
    
    # Mount the root partition (p2)
    log "Mounting root partition..."
    ROOT_MOUNT_INFO=$(udisksctl mount -b "${LOOP_DEV}p2")
    ROOT_PATH=$(echo "$ROOT_MOUNT_INFO" | grep -o '/media/[^ ]*')
    log "Root partition mounted at: $ROOT_PATH"
}

get_hive_config() {
    # Check if a YAML file was provided
    if [[ -f "$1" ]]; then
        CONFIG_FILE="$1"
        log "Using provided config file: $CONFIG_FILE"
    else
        # Use hive ID to find config file
        CONFIG_FILE="${HIVE_CONFIG_DIR}/${HIVE_ID}.yaml"
        if [[ ! -f "$CONFIG_FILE" ]]; then
            error "Hive configuration not found at $CONFIG_FILE"
        fi
        log "Using hive configuration: $CONFIG_FILE"
    fi
    
    # Extract required values from config using Python
    local config_extractor=$(cat <<'EOF'
import sys
import yaml

def get_config_value(config, path, default=None):
    """Safely get a value from nested dictionary using dot notation path"""
    parts = path.split('.')
    current = config
    
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return default
    
    return current

try:
    with open(sys.argv[1], 'r') as f:
        config = yaml.safe_load(f)
    
    # Basic info
    print(f'HIVE_ID={config.get("hive_id", "")}')
    print(f'HIVE_NAME={get_config_value(config, "metadata.name", "")}')
    print(f'TIMEZONE={get_config_value(config, "metadata.location.timezone", "UTC")}')
    
    # Security section
    if "security" in config:
        # SSH
        ssh = get_config_value(config, "security.ssh", {})
        print(f'SSH_PUBLIC_KEY={ssh.get("public_key", "")}')
        print(f'SSH_PRIVATE_KEY={ssh.get("private_key", "")}')
        print(f'SSH_PORT={ssh.get("port", "22")}')
        
        # WireGuard
        wg = get_config_value(config, "security.wireguard", {})
        print(f'WG_PRIVATE_KEY={wg.get("private_key", "")}')
        print(f'WG_PUBLIC_KEY={wg.get("public_key", "")}')
        print(f'WG_CONFIG={wg.get("config", "").replace("\n", "\\n")}')
        print(f'WG_CLIENT_IP={wg.get("client_ip", "")}')
        
        # Database
        db = get_config_value(config, "security.database", {})
        print(f'DB_USERNAME={db.get("username", "hiveuser")}')
        print(f'DB_PASSWORD={db.get("password", "")}')
        print(f'DB_NAME={db.get("database", "hivedb")}')
        
        # Local access
        local = get_config_value(config, "security.local_access", {})
        print(f'LOCAL_USER={local.get("username", "hiveadmin")}')
        print(f'LOCAL_PASSWORD={local.get("password", "")}')

except Exception as e:
    print(f'ERROR={str(e)}', file=sys.stderr)
    sys.exit(1)
EOF
)

    # Execute the Python script and source its output
    config_values=$(python3 -c "$config_extractor" "$CONFIG_FILE")
    
    if [[ $? -ne 0 ]]; then
        error "Failed to extract configuration values from $CONFIG_FILE"
    fi
    
    # Check for errors in the output
    if echo "$config_values" | grep -q "ERROR="; then
        error "$(echo "$config_values" | grep "ERROR=" | cut -d= -f2-)"
    fi
    
    # Source the configuration values
    eval "$config_values"
    
    # Validate required values
    if [ -z "$HIVE_ID" ]; then
        error "Missing hive_id in configuration"
    fi
    
    if [ -z "$SSH_PUBLIC_KEY" ]; then
        error "Missing SSH public key in configuration"
    fi
    
    if [ -z "$WG_CONFIG" ]; then
        error "Missing WireGuard configuration in configuration"
    fi
    
    if [ -z "$DB_PASSWORD" ]; then
        error "Missing database password in configuration"
    fi
    
    if [ -z "$LOCAL_PASSWORD" ]; then
        error "Missing local user password in configuration"
    fi
    
    log "Successfully loaded configuration for hive: $HIVE_NAME (ID: $HIVE_ID)"
}

configure_system() {
    # Base configuration
    log "Setting hostname to $HIVE_ID"
    cat > "${ROOT_PATH}/etc/hostname" << EOF
${HIVE_ID}
EOF
    
    # Setup TimescaleDB
    log "Configuring TimescaleDB"
    mkdir -p "${ROOT_PATH}/etc/postgresql/13/main"
    cat > "${ROOT_PATH}/etc/postgresql/13/main/postgresql.conf" << EOF
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
    log "Configuring SSH access"
    mkdir -p "${ROOT_PATH}/root/.ssh"
    echo "${SSH_PUBLIC_KEY}" > "${ROOT_PATH}/root/.ssh/authorized_keys"
    chmod 700 "${ROOT_PATH}/root/.ssh"
    chmod 600 "${ROOT_PATH}/root/.ssh/authorized_keys"
    
    # Optionally configure SSH private key (for edge-to-edge communication)
    if [ ! -z "$SSH_PRIVATE_KEY" ]; then
        log "Setting up SSH private key"
        echo "$SSH_PRIVATE_KEY" > "${ROOT_PATH}/root/.ssh/id_ed25519"
        chmod 600 "${ROOT_PATH}/root/.ssh/id_ed25519"
    fi

    # Setup WireGuard
    log "Configuring WireGuard VPN"
    mkdir -p "${ROOT_PATH}/etc/wireguard"
    echo "${WG_CONFIG}" > "${ROOT_PATH}/etc/wireguard/wg0.conf"
    chmod 600 "${ROOT_PATH}/etc/wireguard/wg0.conf"

    # Setup firstboot script
    log "Creating firstboot script"
    cat > "${BOOT_PATH}/firstboot.sh" << EOF
#!/bin/bash
set -e

echo "Running first boot setup for hive ${HIVE_ID}..."

# Enable required services
systemctl enable ssh
systemctl enable wg-quick@wg0

# Install required packages 
apt-get update
apt-get install -y postgresql postgresql-contrib postgresql-13-timescaledb

# Create local admin user
useradd -m -s /bin/bash -G sudo ${LOCAL_USER}
echo "${LOCAL_USER}:${LOCAL_PASSWORD}" | chpasswd
echo "Local user ${LOCAL_USER} created"

# Initialize TimescaleDB
sudo -u postgres psql -c "CREATE ROLE ${DB_USERNAME} WITH LOGIN PASSWORD '${DB_PASSWORD}';"
sudo -u postgres createdb -O ${DB_USERNAME} ${DB_NAME}
sudo -u postgres psql -d ${DB_NAME} -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"

# Setup firewall
ufw allow from 10.10.0.0/24 to any port ${SSH_PORT:-22}
ufw allow from 10.10.0.0/24 to any port 5432
ufw --force enable

# Set timezone
timedatectl set-timezone ${TIMEZONE:-UTC}

# Mark setup as complete and remove firstboot script
touch /boot/setup_complete
systemctl disable firstboot.service
rm /boot/firstboot.sh
EOF

    # Make firstboot script executable
    chmod +x "${BOOT_PATH}/firstboot.sh"
    
    # Create firstboot service
    log "Creating firstboot service"
    cat > "${ROOT_PATH}/etc/systemd/system/firstboot.service" << EOF
[Unit]
Description=First Boot Setup for Hive ${HIVE_ID}
After=network.target postgresql.service

[Service]
Type=oneshot
ExecStart=/boot/firstboot.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

    # Enable firstboot service
    ln -sf "${ROOT_PATH}/etc/systemd/system/firstboot.service" "${ROOT_PATH}/etc/systemd/system/multi-user.target.wants/firstboot.service"

    # Add hive configuration
    log "Adding hive configuration to image"
    mkdir -p "${ROOT_PATH}/etc/hive"
    cp "$CONFIG_FILE" "${ROOT_PATH}/etc/hive/config.yaml"
    
    log "System configuration complete"
}

cleanup() {
    log "Unmounting partitions..."
    udisksctl unmount -b "${LOOP_DEV}p1" || true
    udisksctl unmount -b "${LOOP_DEV}p2" || true
    
    log "Detaching loop device..."
    udisksctl loop-delete -b "$LOOP_DEV" || true
}

compress_image() {
    local img_path="${WORK_DIR}/${HIVE_ID}.img"
    local output_path="${WORK_DIR}/${HIVE_ID}_$(date +%Y%m%d).img.xz"
    
    log "Compressing image to $output_path..."
    xz -T0 -9 -c "$img_path" > "$output_path"
    
    log "Compressed image created: $output_path"
    log "You can write this image to an SD card using:"
    log "xzcat $output_path | dd of=/dev/sdX bs=4M status=progress"
}

main() {
    # Check for hive ID argument
    if [ -z "$1" ]; then
        echo "Usage: $0 <hive_id_or_config_path>"
        exit 1
    fi

    # Set HIVE_ID from first argument if it's not a YAML file
    if [[ "$1" != *.yaml ]]; then
        HIVE_ID="$1"
    fi

    check_requirements
    get_hive_config "$1"
    prepare_workspace
    mount_image
    configure_system
    cleanup
    compress_image
    
    log "Image generation complete: ${WORK_DIR}/${HIVE_ID}_$(date +%Y%m%d).img.xz"
}

# Setup trap to ensure cleanup on exit
trap cleanup EXIT INT TERM

main "$@"