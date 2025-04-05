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

# Check Python version
if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
    error "Python 3.8 or higher is required"
fi

# Check if python symlink exists, create if needed
if ! command -v python &> /dev/null; then
    log "Python command not found, creating symlink from python3"
    PYTHON3_PATH=$(which python3)
    if [ -z "$PYTHON3_PATH" ]; then
        error "Could not find python3 executable"
    fi
    
    # Create a local symlink in the virtual environment bin directory
    mkdir -p .venv/bin
    ln -sf "$PYTHON3_PATH" .venv/bin/python
    export PATH="$(pwd)/.venv/bin:$PATH"
    
    log "Created local python symlink"
fi

# Configure Poetry to use Python 3 explicitly
export POETRY_PYTHON=$(which python3)
log "Set Poetry to use Python 3 at: $POETRY_PYTHON"

# Check for Poetry and install or update
if ! command -v poetry &> /dev/null; then
    log "Poetry is not installed. Installing latest Poetry (2.x)..."
    curl -sSL https://install.python-poetry.org | python3 -
    
    # Add Poetry to PATH for current session
    export PATH="$HOME/.local/bin:$PATH"
    
    # Check if PATH needs to be updated in shell config
    if ! echo $PATH | grep -q "$HOME/.local/bin"; then
        warn "Please add '$HOME/.local/bin' to your PATH in your shell configuration file."
        warn "For example, add the following line to your ~/.bashrc or ~/.zshrc:"
        warn "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi
    
    if ! command -v poetry &> /dev/null; then
        error "Failed to install Poetry. Please install it manually: https://python-poetry.org/docs/#installation"
    fi
else
    # Check if we need to update
    current_version=$(poetry --version | awk '{print $3}')
    log "Poetry is already installed. Current version: $current_version"
    
    # Extract major version
    major_version=$(echo $current_version | cut -d. -f1)
    
    if [ "$major_version" -lt "2" ]; then
        log "Updating Poetry to latest version (2.x)..."
        poetry self update --preview
        updated_version=$(poetry --version | awk '{print $3}')
        log "Updated to Poetry version: $updated_version"
    else
        log "Poetry version 2.x already installed."
    fi
fi

# Create Poetry configuration directory if it doesn't exist
mkdir -p ~/.config/pypoetry

# Configure Poetry to use python3 explicitly
log "Configuring Poetry to use Python 3..."
poetry config virtualenvs.prefer-active-python true

# Generate .env file if it doesn't exist
if [ ! -f ".env" ]; then
    log "Generating .env file..."
    ../scripts/generate_env_containerpasswords.sh
fi

# Install dependencies with Poetry
log "Installing dependencies with Poetry..."
POETRY_PYTHON="$(which python3)" poetry install

# Create a shell script wrapper for hivectl
WRAPPER_SCRIPT="/usr/local/bin/hivectl"
log "Creating hivectl wrapper script at $WRAPPER_SCRIPT..."

cat > /tmp/hivectl_wrapper << EOL
#!/bin/bash
# Wrapper script for hivectl using Poetry
cd $(pwd) && POETRY_PYTHON="$(which python3)" poetry run hivectl "\$@"
EOL

# Install the wrapper script (requires sudo)
sudo mv /tmp/hivectl_wrapper "$WRAPPER_SCRIPT"
sudo chmod +x "$WRAPPER_SCRIPT"

log "Setup complete! You can now use 'hivectl' command globally"
log "Run 'hivectl --help' to see available commands"