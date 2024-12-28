#!/bin/bash
# /server/deployment/hivectl/setup.sh

set -e

# Configuration
VENV_DIR=".venv"
PYTHON="python3"
MIN_PYTHON_VERSION="3.8"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Logging
log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Check Python version
check_python_version() {
    if ! $PYTHON -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
        error "Python 3.8 or higher is required"
    fi
}

# Create virtual environment
create_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        log "Creating virtual environment..."
        $PYTHON -m venv "$VENV_DIR"
    else
        warn "Virtual environment already exists"
    fi
}

# Install dependencies
install_deps() {
    log "Installing dependencies..."
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip
    pip install -r requirements.txt
}

# Create CLI symlink
create_symlink() {
    log "Creating hivectl symlink..."
    SYMLINK_PATH="/usr/local/bin/hivectl"
    SCRIPT_PATH="$(pwd)/hivectl.py"
    WRAPPER_SCRIPT="${VENV_DIR}/bin/hivectl"

    # Create wrapper script
    cat > "$WRAPPER_SCRIPT" << EOL
#!/bin/bash
source "$(pwd)/${VENV_DIR}/bin/activate"
exec python "${SCRIPT_PATH}" "\$@"
EOL

    chmod +x "$WRAPPER_SCRIPT"
    
    # Create system-wide symlink (requires sudo)
    if [ -L "$SYMLINK_PATH" ]; then
        sudo rm "$SYMLINK_PATH"
    fi
    sudo ln -s "$WRAPPER_SCRIPT" "$SYMLINK_PATH"
}

# Main setup
main() {
    check_python_version
    create_venv
    install_deps
    create_symlink
    
    log "Setup complete! You can now use 'hivectl' command"
}

main "$@"