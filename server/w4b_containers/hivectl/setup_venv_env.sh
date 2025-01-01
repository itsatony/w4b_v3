#!/bin/bash

set -e

if [ -z "$VENV_DIR" ]; then
    echo "Error: VENV_DIR environment variable is not set"
    exit 1
fi

HIVECTL_VENV="$VENV_DIR/hivectl"
ACTIVATE_SCRIPT="$HIVECTL_VENV/bin/activate.d/environment.sh"
DEACTIVATE_SCRIPT="$HIVECTL_VENV/bin/deactivate.d/environment_deactivate.sh"

# Create activation.d directory if it doesn't exist
mkdir -p "$HIVECTL_VENV/bin/activate.d"
# Create deactivation.d directory if it doesn't exist
mkdir -p "$HIVECTL_VENV/bin/deactivate.d"

# Create activation script
echo "#!/bin/bash" > "$ACTIVATE_SCRIPT"
echo "echo --> Setting VENV-specific ENV vars..." > "$ACTIVATE_SCRIPT"

# Create deactivation script
echo "#!/bin/bash" > "$DEACTIVATE_SCRIPT"
echo "echo --> UN-Setting VENV-specific ENV vars..." > "$DEACTIVATE_SCRIPT"

# Process .env file and create both scripts
while IFS='=' read -r key value; do
    # Skip empty lines and comments
    [[ -z "$key" || "$key" =~ ^# ]] && continue
    
    # Remove quotes from value if present
    value=$(echo "$value" | sed -e 's/^"//' -e 's/"$//')
    
    # Add export to activation script
    echo "export $key='$value'" >> "$ACTIVATE_SCRIPT"
    
    # Add unset to deactivation script
    echo "unset $key" >> "$DEACTIVATE_SCRIPT"
done < .env

# Make both scripts executable
chmod +x "$ACTIVATE_SCRIPT"
chmod +x "$DEACTIVATE_SCRIPT"

# Link deactivation script to be called on deactivate
DEACTIVATE_HOOK="$HIVECTL_VENV/bin/deactivate.d"
mkdir -p "$DEACTIVATE_HOOK"
ln -sf "$DEACTIVATE_SCRIPT" "$DEACTIVATE_HOOK/environment_deactivate.sh"

echo "Environment variables configured in venv activation and deactivation scripts"
