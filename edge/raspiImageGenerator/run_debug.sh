#!/bin/bash
# Debug script for the Raspberry Pi image generator

set -e

# Clear the screen for better readability
clear

# Force cleanup any potential stale mounts
echo "=== Cleaning up any stale mounts ==="
sudo umount -f /tmp/w4b_mnt_* 2>/dev/null || true
sudo losetup -D 2>/dev/null || true
echo ""

# Print diagnostic info
echo "=== System Information ==="
uname -a
echo "Python version: $(python3 --version)"
echo "Available disk space: $(df -h /tmp | tail -1 | awk '{print $4}')"
echo ""

# Check for required dependencies
echo "=== Checking Dependencies ==="
DEPS=("losetup" "mount" "umount" "partprobe" "kpartx" "xz")
for dep in "${DEPS[@]}"; do
    if command -v $dep > /dev/null; then
        echo "✓ $dep found: $(which $dep)"
    else
        echo "✗ $dep not found"
    fi
done
echo ""

# Check Python modules
echo "=== Checking Python Modules ==="
MODULES=("yaml" "aiohttp" "pathlib")
for module in "${MODULES[@]}"; do
    if python3 -c "import $module" 2>/dev/null; then
        echo "✓ $module installed"
    else
        echo "✗ $module not installed"
    fi
done
echo ""

# Set up environment with debug logging
echo "=== Running Image Generator with Debug Logging ==="
export W4B_LOG_LEVEL=DEBUG

# Run the image generator with specified config
python3 image_generator.py --config $(dirname "$0")/sample_config.yaml --hive-id test_hive_01 --debug

echo ""
echo "Debug run completed"
