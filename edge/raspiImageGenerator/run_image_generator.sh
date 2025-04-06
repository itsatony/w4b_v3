#!/bin/bash

# Helper script to ensure dependencies are installed before running image generator

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "This script must be run as root (with sudo)"
  exit 1
fi

# Directory of the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Parse arguments
CONFIG_FILE=""
OUTPUT_DIR=""
VERBOSE=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --config-file)
      CONFIG_FILE="$2"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --verbose)
      VERBOSE="--verbose"
      shift
      ;;
    *)
      echo "Unknown argument: $1"
      shift
      ;;
  esac
done

# Check required arguments
if [ -z "$CONFIG_FILE" ]; then
  echo "Error: --config-file is required"
  echo "Usage: sudo ./run_image_generator.sh --config-file <config_file> --output-dir <output_dir> [--verbose]"
  exit 1
fi

if [ -z "$OUTPUT_DIR" ]; then
  echo "Error: --output-dir is required"
  echo "Usage: sudo ./run_image_generator.sh --config-file <config_file> --output-dir <output_dir> [--verbose]"
  exit 1
fi

# Run the image generator
echo "Running image generator with config: $CONFIG_FILE, output: $OUTPUT_DIR"
python image_generator.py --config-file "$CONFIG_FILE" --output-dir "$OUTPUT_DIR" $VERBOSE
