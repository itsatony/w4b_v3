#!/bin/bash

# Activate the virtual environment
source "$(dirname "$0")/.venv/bin/activate"

# Enable the hivectl command
export PATH="$(dirname "$0")/.venv/bin:$PATH"

echo "Virtual environment activated and hivectl command enabled."