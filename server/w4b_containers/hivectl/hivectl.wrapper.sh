#!/bin/bash
# Wrapper script for hivectl using Poetry

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Set Poetry to use Python 3 explicitly
export POETRY_PYTHON=$(which python3)

# Change to the project directory and run hivectl with Poetry
cd "$SCRIPT_DIR" && POETRY_PYTHON="$POETRY_PYTHON" poetry run hivectl "$@"
