#!/bin/bash
# Wrapper script for hivectl

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"


# Ensure we're in the project directory
cd "$SCRIPT_DIR"

# Run either the installed version or through poetry
if [ -f "$VIRTUAL_ENV/bin/hivectl" ]; then
    # Run the installed hivectl command directly
    exec "$VIRTUAL_ENV/bin/hivectl" "$@"
else
    # Fall back to running through poetry
    exec poetry run python -m hivectl "$@"
fi
