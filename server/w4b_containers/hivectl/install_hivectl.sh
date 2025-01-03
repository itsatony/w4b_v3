#!/bin/bash

# Ensure we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Please activate your virtual environment first!"
    exit 1
fi

# Install in development mode
pip install -e .

# Make the script executable
chmod +x hivectl/hivectl.py

# Create symlink if it doesn't exist
if [ ! -L "$VIRTUAL_ENV/bin/hivectl" ]; then
    ln -s "$(pwd)/hivectl/hivectl.py" "$VIRTUAL_ENV/bin/hivectl"
fi

echo "Development installation complete!"