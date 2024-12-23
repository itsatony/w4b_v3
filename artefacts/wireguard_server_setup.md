# WireGuard VPN Hub Server Setup

Version: 1.0.0
Last Updated: 2024-12-23

## Overview

This document describes the setup and configuration of a WireGuard VPN hub server designed to handle up to 200 Raspberry Pi clients in a hub-and-spoke topology.

## System Requirements

- Ubuntu Server 22.04 LTS
- Fixed IP address with DNS entry
- Minimum 1GB RAM
- 20GB storage
- Open UDP port 51820

## Installation Steps

### 1. Base System Setup

```bash
# Update system and install required packages
sudo apt update
sudo apt install -y wireguard

# Enable IP forwarding
echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# Create WireGuard directory structure
sudo mkdir -p /etc/wireguard/clients
sudo chmod 700 /etc/wireguard/clients
```

### 2. Generate Server Keys

```bash
cd /etc/wireguard
umask 077
wg genkey | tee server_private.key | wg pubkey > server_public.key
```

### 3. Server Configuration

Create `/etc/wireguard/wg0.conf`:

```ini
[Interface]
PrivateKey = <server_private_key>
Address = 10.10.0.1/24
ListenPort = 51820
SaveConfig = false

PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE
```

### 4. Start WireGuard Service

```bash
sudo systemctl enable wg-quick@wg0
sudo systemctl start wg-quick@wg0
```

## Verification

```bash
# Check service status
sudo systemctl status wg-quick@wg0

# Verify interface
sudo wg show

# Check listening port
sudo ss -lnpu | grep 51820
```

## Maintenance

- Backup `/etc/wireguard` directory regularly
- Monitor system logs: `journalctl -u wg-quick@wg0`
- Check server load periodically

## Security Considerations

- Keep private keys secure
- Regularly update system
- Monitor for unauthorized connection attempts
- Use strong firewall rules

## Troubleshooting

1. Connection Issues
   - Check firewall settings
   - Verify port forwarding
   - Confirm correct key permissions

2. Performance Issues
   - Monitor system resources
   - Check network bandwidth
   - Verify client configurations

## Version History

- 1.0.0 (2024-12-23): Initial release
  - Basic server setup
  - Security configurations
  - Monitoring setup