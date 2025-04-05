#!/bin/bash

# Check for Poetry
if ! command -v poetry &> /dev/null; then
    echo "Poetry is not installed. Please run setup.sh first."
    exit 1
fi

# Check Poetry version
poetry_version=$(poetry --version | awk '{print $3}')
echo "Using Poetry version: $poetry_version"

# Set Poetry to use Python 3 explicitly
export POETRY_PYTHON=$(which python3)
echo "Using Python at: $POETRY_PYTHON"

# Configure Poetry to use active Python
poetry config virtualenvs.prefer-active-python true

# Install the package with Poetry in development mode
echo "Installing hivectl in development mode..."
POETRY_PYTHON="$(which python3)" poetry install

# Create the global executable
echo "Creating global hivectl command..."
WRAPPER_SCRIPT="/usr/local/bin/hivectl"

cat > /tmp/hivectl_wrapper << EOL
#!/bin/bash
# Wrapper script for hivectl using Poetry
cd $(pwd) && POETRY_PYTHON="$(which python3)" poetry run hivectl "\$@"
EOL

sudo mv /tmp/hivectl_wrapper "$WRAPPER_SCRIPT"
sudo chmod +x "$WRAPPER_SCRIPT"

echo "Development installation complete!"
echo "Run 'hivectl --help' to see available commands"