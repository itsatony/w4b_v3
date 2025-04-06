#!/bin/bash
# Convenience script to run the image generator with dependencies

# Check for root privileges
if [ "$(id -u)" -ne 0 ]; then
  echo "This script must be run as root or with sudo"
  exit 1
fi

# Ensure required packages are installed
REQUIRED_PKGS="xz-utils kpartx parted python3 python3-pip"
MISSING_PKGS=""

for pkg in $REQUIRED_PKGS; do
  if ! dpkg -l "$pkg" | grep -q "^ii"; then
    MISSING_PKGS="$MISSING_PKGS $pkg"
  fi
done

if [ -n "$MISSING_PKGS" ]; then
  echo "Installing required packages:$MISSING_PKGS"
  apt-get update && apt-get install -y $MISSING_PKGS
fi

# Ensure Python dependencies are installed
if [ ! -f "requirements.txt" ]; then
  echo "requirements.txt not found, creating basic dependencies list"
  cat > requirements.txt << EOF
pyyaml>=6.0
aiohttp>=3.8.0
EOF
fi

pip3 install -r requirements.txt

# Run the image generator
echo "Running image generator..."
python3 run_generator.py "$@"
