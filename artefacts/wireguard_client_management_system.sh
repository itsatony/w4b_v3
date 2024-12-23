#!/bin/bash
# wg-manage: WireGuard Client Management Script
# Version: 1.0.0
# Last Updated: 2024-12-23
# Description: Manages WireGuard VPN clients for hub-and-spoke topology
# Usage: wg-manage {add <client_name>|list|remove <client_name>}

set -e

# Set WG_DIR from environment or use default
WG_DIR="${WG_DIR:-/etc/wireguard}"

# Configuration
WG_DIR="/etc/wireguard"
CLIENT_DIR="${WG_DIR}/clients"
PEER_MAP="${WG_DIR}/peer_mapping.txt"
BASE_IP="10.10.0"
CONFIG_VERSION="1.0.0"
LOG_FILE="/var/log/wg-manage.log"

# Logging function
log() {
    local level=$1
    shift
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [$level] $*" >> "$LOG_FILE"
    if [ "$level" = "ERROR" ]; then
        echo "ERROR: $*" >&2
    else
        echo "$*"
    fi
}

# Validate environment
check_environment() {
    if [ ! -d "$WG_DIR" ]; then
        log "ERROR" "WireGuard directory not found"
        exit 1
    fi
    if [ ! -f "${WG_DIR}/server_public.key" ]; then
        log "ERROR" "Server public key not found"
        exit 1
    fi
    # Check for qrencode
    if ! command -v qrencode >/dev/null 2>&1; then
        log "ERROR" "qrencode not found. Install with: sudo apt install qrencode"
        exit 1
    fi
    # if ! command -v viu >/dev/null 2>&1; then
    #     log "ERROR" "viu not found. Install with: cargo install viu"
    #     exit 1
    # fi
}

generate_client() {
    local client_name=$1
    local client_number=$2
    
    log "INFO" "Generating configuration for client: ${client_name}"
    
    # Generate client keys
    local private_key=$(wg genkey)
    local public_key=$(echo "$private_key" | wg pubkey)
    
    # Save peer mapping
    echo "${public_key} ${client_name}" >> "${PEER_MAP}"
    
    # Create client config directory
    mkdir -p "${CLIENT_DIR}/${client_name}"
    
    # Create client config content
    local config_content="[Interface]
PrivateKey = ${private_key}
Address = ${BASE_IP}.${client_number}/24
DNS = 1.1.1.1

[Peer]
PublicKey = $(cat ${WG_DIR}/server_public.key)
Endpoint = $(if ip addr show enp0s31f6 2>/dev/null | grep -q "inet "; then
    ip addr show enp0s31f6 | grep "inet " | awk '{print $2}' | cut -d/ -f1
else
    read -p "Please enter the server's public IP address: " server_ip
    echo "$server_ip"
fi):51820
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25"

    # Save client config
    echo "# WireGuard Client Configuration
# Generated: $(date)
# Version: ${CONFIG_VERSION}
# Client: ${client_name}

${config_content}" > "${CLIENT_DIR}/${client_name}/wg0.conf"
    
    # Generate QR code
    echo "${config_content}" | qrencode -o "${CLIENT_DIR}/${client_name}/config.png"
    
    # Add client to server config
    cat >> "${WG_DIR}/wg0.conf" <<EOL

# ${client_name} (added: $(date))
[Peer]
PublicKey = ${public_key}
AllowedIPs = ${BASE_IP}.${client_number}/32
EOL

    log "INFO" "Generated config for ${client_name} with IP ${BASE_IP}.${client_number}"
    log "INFO" "QR code saved to ${CLIENT_DIR}/${client_name}/config.png"
}

list_clients() {
    log "INFO" "Listing active connections and registered clients"
    echo "=== Active WireGuard Connections ==="
    
    # Create temporary file for wg show output
    local wg_output=$(wg show wg0)
    
    # Process and display with peer names
    echo "$wg_output" | while IFS= read -r line; do
        if [[ $line =~ ^peer ]]; then
            peer_id=$(echo "$line" | cut -d' ' -f2)
            peer_name=$(grep "$peer_id" "${PEER_MAP}" 2>/dev/null | cut -d' ' -f2)
            if [ -n "$peer_name" ]; then
                echo "$line (Name: $peer_name)"
            else
                echo "$line"
            fi
        else
            echo "$line"
        fi
    done

    echo -e "\n=== Registered Clients ==="
    ls -1 ${CLIENT_DIR}
}

remove_client() {
    local client_name=$1
    
    if [ ! -d "${CLIENT_DIR}/${client_name}" ]; then
        log "ERROR" "Client ${client_name} not found"
        exit 1
    fi
    
    log "INFO" "Removing client: ${client_name}"
    
    # Remove client directory
    rm -rf "${CLIENT_DIR}/${client_name}"
    
    # Remove from server config
    sed -i "/# ${client_name}/,+3d" "${WG_DIR}/wg0.conf"
    
    # Remove from peer mapping
    local public_key=$(grep -l "${client_name}$" "${PEER_MAP}")
    if [ -n "$public_key" ]; then
        sed -i "/${client_name}$/d" "${PEER_MAP}"
    fi
    
    log "INFO" "Removed client ${client_name}"
}

# Main execution
main() {
    check_environment

    case "$1" in
        "add")
            if [ -z "$2" ]; then
                log "ERROR" "Usage: $0 add <client_name>"
                exit 1
            fi
            # Find next available number
            next_num=2
            while [ -d "${CLIENT_DIR}/${2}" ]; do
                ((next_num++))
                if [ $next_num -gt 254 ]; then
                    log "ERROR" "No available IPs!"
                    exit 1
                fi
            done
            generate_client "$2" $next_num
            systemctl restart wg-quick@wg0
            ;;
        "list")
            list_clients
            ;;
        "remove")
            if [ -z "$2" ]; then
                log "ERROR" "Usage: $0 remove <client_name>"
                exit 1
            fi
            remove_client "$2"
            systemctl restart wg-quick@wg0
            ;;
        *)
            log "ERROR" "Usage: $0 {add <client_name>|list|remove <client_name>}"
            exit 1
            ;;
    esac
}

main "$@"