#!/bin/bash
# setup.sh - Setup script for hive_config_manager development environment

# Exit on error
set -e

# Configuration
VENV_NAME=".venv"
PYTHON="python3"
MIN_PYTHON_VERSION="3.8"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_python_version() {
    local version
    version=$($PYTHON --version 2>&1 | cut -d' ' -f2)
    if ! $PYTHON -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
        log_error "Python version must be $MIN_PYTHON_VERSION or higher (found $version)"
        exit 1
    fi
}

create_venv() {
    if [ ! -d "$VENV_NAME" ]; then
        log_info "Creating virtual environment..."
        $PYTHON -m venv "$VENV_NAME"
    else
        log_warn "Virtual environment already exists"
    fi
}

install_requirements() {
    log_info "Installing dependencies..."
    source "$VENV_NAME/bin/activate"
    pip install --upgrade pip
    pip install -r ./requirements/requirements.txt
    
    if [ "$1" = "--dev" ]; then
        log_info "Installing development dependencies..."
        pip install -r ./requirements/requirements-dev.txt
    fi
}

setup_git_hooks() {
    if [ -d ".git" ]; then
        log_info "Setting up git hooks..."
        source "$VENV_NAME/bin/activate"
        pre-commit install
    fi
}

create_directories() {
    log_info "Creating project directories..."
    mkdir -p hives
    mkdir -p logs
}

main() {
    # Check Python version
    check_python_version

    # Create virtual environment
    create_venv

    # Install dependencies
    if [ "$1" = "--dev" ]; then
        install_requirements --dev
        setup_git_hooks
    else
        install_requirements
    fi

    # Create necessary directories
    create_directories

    log_info "Setup complete! Activate the virtual environment with: source $VENV_NAME/bin/activate"
}

# Parse command line arguments
case "$1" in
    --dev)
        main --dev
        ;;
    --help)
        echo "Usage: $0 [--dev|--help]"
        echo "  --dev   Install development dependencies"
        echo "  --help  Show this help message"
        exit 0
        ;;
    *)
        main
        ;;
esac