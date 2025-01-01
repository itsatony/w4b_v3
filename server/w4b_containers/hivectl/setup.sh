#!/bin/bash

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Logging functions
log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Check VENV_DIR environment variable
if [ -z "$VENV_DIR" ]; then
    error "VENV_DIR environment variable is not set. Please set it first."
fi

# Check Python version
if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
    error "Python 3.8 or higher is required"
fi

# Create virtual environment if it doesn't exist
HIVECTL_VENV="$VENV_DIR/hivectl"
if [ ! -d "$HIVECTL_VENV" ]; then
    log "Creating hivectl virtual environment at $HIVECTL_VENV..."
    python3 -m venv "$HIVECTL_VENV"
else
    log "Using existing virtual environment at $HIVECTL_VENV"
fi

# Create activation hooks directory
mkdir -p "$HIVECTL_VENV/bin/activate.d"

# Create deactivation hooks directory
mkdir -p "$HIVECTL_VENV/bin/deactivate.d"

# Install dependencies
log "Installing dependencies..."
source "$HIVECTL_VENV/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt

# Generate .env file if it doesn't exist
if [ ! -f ".env" ]; then
    log "Generating .env file..."
    ../scripts/generate_env_containerpasswords.sh
fi

# Setup environment variables in venv
./setup_venv_env.sh

# Create CLI symlink
log "Creating hivectl symlink..."
SYMLINK_PATH="/usr/local/bin/hivectl"
SCRIPT_PATH="$(pwd)/hivectl.py"
WRAPPER_SCRIPT="${HIVECTL_VENV}/bin/hivectl"

# Create wrapper script
cat > "$WRAPPER_SCRIPT" << EOL
#!/bin/bash
source "${HIVECTL_VENV}/bin/activate"
exec python "${SCRIPT_PATH}" "\$@"
EOL

chmod +x "$WRAPPER_SCRIPT"

# Create system-wide symlink (requires sudo)
if [ -L "$SYMLINK_PATH" ]; then
    sudo rm "$SYMLINK_PATH"
fi
sudo ln -s "$WRAPPER_SCRIPT" "$SYMLINK_PATH"

log "Setup complete! You can now use 'hivectl' command"