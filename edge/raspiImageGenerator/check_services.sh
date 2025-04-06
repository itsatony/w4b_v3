#!/bin/bash
# Quick diagnostic script to check service files in a mounted image

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 /path/to/root/mount"
    exit 1
fi

ROOT_MOUNT="$1"

echo "Checking service files in $ROOT_MOUNT..."

# Check systemd service directory
SYSTEMD_DIR="$ROOT_MOUNT/etc/systemd/system"
echo -e "\n=== Systemd Services ==="
if [ -d "$SYSTEMD_DIR" ]; then
    find "$SYSTEMD_DIR" -name "*.service" | xargs ls -la
else
    echo "Systemd directory not found!"
fi

# Check w4b directories
W4B_DIR="$ROOT_MOUNT/opt/w4b"
echo -e "\n=== W4B Directory Structure ==="
if [ -d "$W4B_DIR" ]; then
    find "$W4B_DIR" -type f -name "*.service" | xargs ls -la
    echo -e "\nSensor Manager Directory:"
    ls -la "$W4B_DIR/sensorManager/" 2>/dev/null
else
    echo "W4B directory not found!"
fi

# Check firstboot script
FIRSTBOOT="$ROOT_MOUNT/boot/firstboot.sh"
echo -e "\n=== Firstboot Script ==="
if [ -f "$FIRSTBOOT" ]; then
    echo "Firstboot script exists with permissions:"
    ls -la "$FIRSTBOOT"
    echo -e "\nFirstboot script content (service-related lines):"
    grep -i "service\|systemctl" "$FIRSTBOOT"
else
    echo "Firstboot script not found!"
fi

# Check rc.local
RCLOCAL="$ROOT_MOUNT/etc/rc.local"
echo -e "\n=== rc.local File ==="
if [ -f "$RCLOCAL" ]; then
    echo "rc.local exists with permissions:"
    ls -la "$RCLOCAL"
    echo -e "\nrc.local content:"
    cat "$RCLOCAL"
else
    echo "rc.local not found!"
fi

echo -e "\nDiagnostic check completed."
chmod +x check_services.sh
