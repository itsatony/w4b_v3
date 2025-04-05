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
HIVE_CONFIG_DIR="${REPO_ROOT}/w4b_v3/hive_config_manager/hives"

# Default locations for image storage
IMAGE_DESTINATION="${W4B_RASPI_IMAGE_DESTINATION:-/home/itsatony/srv}"
DOWNLOAD_DOMAIN="${W4B_RASPI_IMAGE_DOWNLOAD_DOMAIN:-https://queenb.vaudience.io/files}"

# Cleanup status flag to prevent running cleanup twice
CLEANUP_DONE=false

# Required environment variables or command-line parameters
# - HIVE_ID: The ID of the hive to configure (must exist in hive_config_manager)
# - or path to YAML config file

# Show detailed help information
show_help() {
    cat << EOF
Raspberry Pi Image Generator for Hive System
Version: 1.0.0

USAGE:
    $(basename "$0") <hive_id_or_config_path>

DESCRIPTION:
    Generates a customized Raspberry Pi image for a specific hive based on its
    configuration. The configuration can be specified by providing either a hive ID
    or a path to a YAML configuration file.

PARAMETERS:
    <hive_id_or_config_path>  Either a hive ID (which will be looked up in the
                              hive_config_manager directory) or a direct path to a
                              YAML configuration file.

ENVIRONMENT VARIABLES:
    The following environment variables can be set to customize the script behavior:

    W4B_RASPI_IMAGE_DESTINATION  
        The directory where the generated image will be saved after compression.
        Default: /home/itsatony/srv

    W4B_RASPI_IMAGE_DOWNLOAD_DOMAIN  
        The base URL where the image will be accessible for download.
        Default: https://queenb.vaudience.io/files

EXAMPLES:
    # Generate an image for hive_0Bpfj4cT using the config in hive_config_manager
    $(basename "$0") hive_0Bpfj4cT

    # Generate an image using a specific configuration file
    $(basename "$0") /path/to/my_hive_config.yaml

    # Generate with custom destination and download domain
    W4B_RASPI_IMAGE_DESTINATION=/mnt/storage \\
    W4B_RASPI_IMAGE_DOWNLOAD_DOMAIN=https://files.example.com \\
    $(basename "$0") hive_0Bpfj4cT

EOF
}

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "${WORK_DIR}/generator.log"
}

error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $*" | tee -a "${WORK_DIR}/generator.log" >&2
    exit 1
}

check_requirements() {
    for cmd in udisksctl wget xz python3; do
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
import shlex

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

# Function to quote values for shell
def shell_quote(value):
    """Properly quote a value for safe usage in shell"""
    if value is None:
        return '""'
    return shlex.quote(str(value))

try:
    with open(sys.argv[1], 'r') as f:
        config = yaml.safe_load(f)
    
    # Basic info
    print(f'HIVE_ID={shell_quote(config.get("hive_id", ""))}')
    print(f'HIVE_NAME={shell_quote(get_config_value(config, "metadata.name", ""))}')
    print(f'TIMEZONE={shell_quote(get_config_value(config, "metadata.location.timezone", "UTC"))}')
    
    # Security section
    if "security" in config:
        # SSH
        ssh = get_config_value(config, "security.ssh", {})
        print(f'SSH_PUBLIC_KEY={shell_quote(ssh.get("public_key", ""))}')
        print(f'SSH_PRIVATE_KEY={shell_quote(ssh.get("private_key", ""))}')
        print(f'SSH_PORT={shell_quote(ssh.get("port", "22"))}')
        # Always enable password auth (override config)
        print(f'SSH_PASSWORD_AUTH="true"')
        print(f'SSH_ALLOW_ROOT={shell_quote(ssh.get("allow_root", "false"))}')
        
        # WireGuard
        wg = get_config_value(config, "security.wireguard", {})
        print(f'WG_PRIVATE_KEY={shell_quote(wg.get("private_key", ""))}')
        print(f'WG_PUBLIC_KEY={shell_quote(wg.get("public_key", ""))}')
        print(f'WG_ENDPOINT={shell_quote(wg.get("endpoint", "queenb.vaudience.io:51820"))}')
        
        # Handle multiline config with a temporary variable
        wg_config = wg.get("config", "").replace("\n", "\\n")
        print(f'WG_CONFIG={shell_quote(wg_config)}')
        
        print(f'WG_CLIENT_IP={shell_quote(wg.get("client_ip", "10.10.0.2/32"))}')
        
        # Database
        db = get_config_value(config, "security.database", {})
        print(f'DB_USERNAME={shell_quote(db.get("username", "hiveuser"))}')
        print(f'DB_PASSWORD={shell_quote(db.get("password", ""))}')
        print(f'DB_NAME={shell_quote(db.get("database", "hivedb"))}')
        
        # Local access
        local = get_config_value(config, "security.local_access", {})
        print(f'LOCAL_USER={shell_quote(local.get("username", "hiveadmin"))}')
        print(f'LOCAL_PASSWORD={shell_quote(local.get("password", ""))}')

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
    echo "${HIVE_ID}" | sudo tee "${ROOT_PATH}/etc/hostname" > /dev/null
    
    # Setup TimescaleDB
    log "Configuring TimescaleDB"
    sudo mkdir -p "${ROOT_PATH}/etc/postgresql/13/main"
    cat << EOF | sudo tee "${ROOT_PATH}/etc/postgresql/13/main/postgresql.conf" > /dev/null
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

    # Enable SSH explicitly by creating empty ssh file in boot
    log "Enabling SSH on first boot"
    sudo touch "${BOOT_PATH}/ssh"
    
    # Setup SSH configuration to allow password authentication
    log "Configuring SSH access with password authentication enabled"
    sudo mkdir -p "${ROOT_PATH}/etc/ssh/sshd_config.d"
    cat << EOF | sudo tee "${ROOT_PATH}/etc/ssh/sshd_config.d/10-w4b.conf" > /dev/null
# W4B Custom SSH Configuration
Port ${SSH_PORT:-22}
PasswordAuthentication yes
ChallengeResponseAuthentication no
PermitRootLogin ${SSH_ALLOW_ROOT:-no}
EOF
    
    sudo mkdir -p "${ROOT_PATH}/root/.ssh"
    echo "${SSH_PUBLIC_KEY}" | sudo tee "${ROOT_PATH}/root/.ssh/authorized_keys" > /dev/null
    sudo chmod 700 "${ROOT_PATH}/root/.ssh"
    sudo chmod 600 "${ROOT_PATH}/root/.ssh/authorized_keys"
    
    # Configure SSH daemon
    log "Configuring SSH daemon settings"
    cat << EOF | sudo tee -a "${ROOT_PATH}/etc/ssh/sshd_config.d/10-w4b.conf" > /dev/null
AllowUsers ${LOCAL_USER} root
EOF
    
    # Optionally configure SSH private key (for edge-to-edge communication)
    if [ ! -z "$SSH_PRIVATE_KEY" ]; then
        log "Setting up SSH private key"
        echo "$SSH_PRIVATE_KEY" | sudo tee "${ROOT_PATH}/root/.ssh/id_ed25519" > /dev/null
        sudo chmod 600 "${ROOT_PATH}/root/.ssh/id_ed25519"
    fi

    # Setup WireGuard
    log "Configuring WireGuard VPN"
    sudo mkdir -p "${ROOT_PATH}/etc/wireguard"
    
    # Create a clean WireGuard config, ensuring the Endpoint is set correctly
    cat << EOF | sudo tee "${ROOT_PATH}/etc/wireguard/wg0.conf" > /dev/null
[Interface]
PrivateKey = ${WG_PRIVATE_KEY}
Address = ${WG_CLIENT_IP}
DNS = 1.1.1.1, 8.8.8.8

[Peer]
PublicKey = ${WG_PUBLIC_KEY}
Endpoint = ${WG_ENDPOINT:-queenb.vaudience.io:51820}
AllowedIPs = 10.10.0.0/24
PersistentKeepalive = 25
EOF
    
    sudo chmod 600 "${ROOT_PATH}/etc/wireguard/wg0.conf"

    # Setup firstboot script with improved network configuration
    log "Creating firstboot script"
    cat << EOF | sudo tee "${BOOT_PATH}/firstboot.sh" > /dev/null
#!/bin/bash
set -e

echo "Running first boot setup for hive ${HIVE_ID}..."

# Create local admin user
useradd -m -s /bin/bash -G sudo ${LOCAL_USER}
echo "${LOCAL_USER}:${LOCAL_PASSWORD}" | chpasswd
echo "Local user ${LOCAL_USER} created"

# Setup SSH for local user
mkdir -p /home/${LOCAL_USER}/.ssh
cp /root/.ssh/authorized_keys /home/${LOCAL_USER}/.ssh/
chown -R ${LOCAL_USER}:${LOCAL_USER} /home/${LOCAL_USER}/.ssh
chmod 700 /home/${LOCAL_USER}/.ssh
chmod 600 /home/${LOCAL_USER}/.ssh/authorized_keys

# Enable required services
systemctl enable ssh
systemctl start ssh
systemctl enable wg-quick@wg0

# Install required packages 
apt-get update
apt-get install -y postgresql postgresql-contrib postgresql-13-timescaledb wireguard

# Initialize TimescaleDB
sudo -u postgres psql -c "CREATE ROLE ${DB_USERNAME} WITH LOGIN PASSWORD '${DB_PASSWORD}';"
sudo -u postgres createdb -O ${DB_USERNAME} ${DB_NAME}
sudo -u postgres psql -d ${DB_NAME} -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"

# Setup firewall - Allow SSH from both local network and VPN
ufw allow ${SSH_PORT:-22}/tcp comment 'SSH access'
ufw allow 51820/udp comment 'WireGuard VPN'
ufw allow from 10.10.0.0/24 to any port 5432 comment 'PostgreSQL from VPN'
ufw --force enable

# Network information
echo "======= Network Configuration Info ======="
echo "Local network interfaces:"
ip -4 addr show | grep -v 'lo\|wg'
echo ""
echo "WireGuard VPN interface (after connection):"
echo "IP: ${WG_CLIENT_IP} (VPN internal address)"
echo "WireGuard server: ${WG_ENDPOINT:-queenb.vaudience.io:51820}"
echo "Note: WireGuard network (10.10.0.0/24) is separate from your local network"
echo "==========================================="

# Set timezone
timedatectl set-timezone ${TIMEZONE:-UTC}

# Mark setup as complete and remove firstboot script
touch /boot/setup_complete
systemctl disable firstboot.service
rm /boot/firstboot.sh
EOF

    # Make firstboot script executable
    sudo chmod +x "${BOOT_PATH}/firstboot.sh"
    
    # Create firstboot service
    log "Creating firstboot service"
    cat << EOF | sudo tee "${ROOT_PATH}/etc/systemd/system/firstboot.service" > /dev/null
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
    sudo mkdir -p "${ROOT_PATH}/etc/systemd/system/multi-user.target.wants"
    sudo ln -sf "${ROOT_PATH}/etc/systemd/system/firstboot.service" "${ROOT_PATH}/etc/systemd/system/multi-user.target.wants/firstboot.service"

    # Add hive configuration
    log "Adding hive configuration to image"
    sudo mkdir -p "${ROOT_PATH}/etc/hive"
    sudo cp "$CONFIG_FILE" "${ROOT_PATH}/etc/hive/config.yaml"
    
    log "System configuration complete"
}

cleanup() {
    # Only run cleanup once
    if [ "$CLEANUP_DONE" = true ]; then
        return
    fi

    log "Unmounting partitions..."
    
    # Only try to unmount if the partition exists
    if [ -n "$LOOP_DEV" ] && [ -e "${LOOP_DEV}p1" ]; then
        udisksctl unmount -b "${LOOP_DEV}p1" || log "Failed to unmount ${LOOP_DEV}p1"
    fi
    
    if [ -n "$LOOP_DEV" ] && [ -e "${LOOP_DEV}p2" ]; then
        udisksctl unmount -b "${LOOP_DEV}p2" || log "Failed to unmount ${LOOP_DEV}p2"
    fi
    
    # Only try to detach the loop device if it exists
    if [ -n "$LOOP_DEV" ] && [ -e "$LOOP_DEV" ]; then
        log "Detaching loop device..."
        # Attempt to delete the loop device, but don't fail if it doesn't work
        udisksctl loop-delete -b "$LOOP_DEV" || log "Failed to delete loop device $LOOP_DEV"
    fi
    
    CLEANUP_DONE=true
}

compress_image() {
    local img_path="${WORK_DIR}/${HIVE_ID}.img"
    local timestamp="$(date +%Y-%m-%d-%H-%M)"
    local output_filename="${timestamp}_${HIVE_ID}.img.xz"
    local temp_output_path="${WORK_DIR}/${output_filename}"
    
    log "Compressing image to $temp_output_path..."
    xz -T0 -9 -c "$img_path" > "$temp_output_path"
    
    # Create destination directory if it doesn't exist
    mkdir -p "$IMAGE_DESTINATION"
    
    # Move the compressed image to the destination directory
    local final_output_path="${IMAGE_DESTINATION}/${output_filename}"
    mv "$temp_output_path" "$final_output_path"
    
    log "Compressed image created and moved to: $final_output_path"
    log "You can write this image to an SD card using:"
    log "xzcat $final_output_path | dd of=/dev/sdX bs=4M status=progress"
    
    # Generate download URL
    # Ensure DOWNLOAD_DOMAIN doesn't have trailing slash while we add one
    DOWNLOAD_DOMAIN="${DOWNLOAD_DOMAIN%/}"
    local download_url="${DOWNLOAD_DOMAIN}/${output_filename}"
    
    log "Download URL: $download_url"
    
    # Return the final path and download URL
    FINAL_IMAGE_PATH="$final_output_path"
    DOWNLOAD_URL="$download_url"
}

main() {
    # Check for hive ID argument
    if [ -z "$1" ]; then
        show_help
        exit 1
    fi

    # Set HIVE_ID from first argument if it's not a YAML file
    if [[ "$1" != *.yaml ]]; then
        HIVE_ID="$1"
    fi

    # Create log directory if it doesn't exist
    mkdir -p "${WORK_DIR}"
    
    # Log environment settings
    log "Starting image generation with the following settings:"
    log "  Hive ID/Config: $1"
    log "  Image destination: ${IMAGE_DESTINATION} (from W4B_RASPI_IMAGE_DESTINATION)"
    log "  Download domain: ${DOWNLOAD_DOMAIN} (from W4B_RASPI_IMAGE_DOWNLOAD_DOMAIN)"

    check_requirements
    get_hive_config "$1"
    prepare_workspace
    mount_image
    configure_system
    cleanup
    compress_image
    
    log "Image generation complete!"
    log "Final image path: $FINAL_IMAGE_PATH"
    log "Download URL: $DOWNLOAD_URL"
}

# Setup trap to ensure cleanup on exit
trap cleanup EXIT INT TERM

main "$@"