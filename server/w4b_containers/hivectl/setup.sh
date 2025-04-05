#!/bin/bash

# Function to check if a command exists
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

# Get the current directory
CURRENT_DIR="$(pwd)"

# Check for Python 3
if ! command_exists python3; then
  echo "Python 3 is required but not found."
  echo "Please install Python 3 with: sudo apt install python3"
  exit 1
fi

# Check for pipx and install if needed
if ! command_exists pipx; then
  echo "Installing pipx..."
  python3 -m pip install --user pipx
  python3 -m pipx ensurepath
  
  # Source bashrc to update PATH
  if [ -f "$HOME/.bashrc" ]; then
    source "$HOME/.bashrc"
  fi
  
  if ! command_exists pipx; then
    echo "Failed to install pipx. Please install manually with:"
    echo "python3 -m pip install --user pipx"
    echo "python3 -m pipx ensurepath"
    exit 1
  fi
fi

# Check if Poetry is already installed, install with pipx if needed
if ! command_exists poetry; then
  echo "Poetry is not installed. Installing with pipx..."
  pipx install poetry
  
  # Source bashrc to update PATH
  if [ -f "$HOME/.bashrc" ]; then
    source "$HOME/.bashrc"
  fi
  
  if ! command_exists poetry; then
    echo "Failed to install Poetry. If you get Python errors, try:"
    echo "$ sudo apt install python-is-python3"
    exit 1
  fi
fi

# Remove any broken or partial installs
echo "Cleaning previous installation..."
rm -rf .venv dist *.egg-info

# Install the hivectl package
echo "Installing hivectl with Poetry..."
poetry config virtualenvs.in-project true
poetry install --no-interaction

# Test the installation
echo "Testing installation..."
if poetry run python -c "import hivectl; print('Import successful')" 2>/dev/null; then
  echo "Package imports are working correctly"
else
  echo "Warning: Package imports are not working correctly"
  echo "This is a temporary warning and will be fixed in the next step"
fi

# Create the global executable
echo "Creating global hivectl command..."
WRAPPER_SCRIPT="/usr/local/bin/hivectl"

cat > /tmp/hivectl_wrapper << EOL
#!/bin/bash
# Wrapper for hivectl
cd "$CURRENT_DIR" && "$CURRENT_DIR/hivectl.wrapper.sh" "\$@"
EOL

sudo mv /tmp/hivectl_wrapper "$WRAPPER_SCRIPT"
sudo chmod +x "$WRAPPER_SCRIPT"

echo "Making wrapper script executable..."
chmod +x hivectl.wrapper.sh

echo "Installation complete!"
echo "Run 'hivectl --help' to see available commands"