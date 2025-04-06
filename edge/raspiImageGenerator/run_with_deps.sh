#!/bin/bash
# Helper script to run the image generator with all dependencies

# Exit on any error
set -e

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "This script must be run as root (with sudo)"
  exit 1
fi

# Directory of the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Install dependencies
echo "Installing dependencies..."
pip install aiohttp pyyaml asyncio aiofiles cryptography jinja2 pytest-asyncio

# Parse command line arguments
echo "Running image generator..."
python3 image_generator.py "$@"
