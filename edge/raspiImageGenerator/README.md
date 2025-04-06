# Raspberry Pi Image Generator for W4B

## Overview

The Raspberry Pi Image Generator is a critical component of the W4B (we4bee) platform. It creates customized, production-ready Raspberry Pi OS images for edge devices that come pre-configured with all necessary software, security settings, and connectivity options.

## Purpose

This system provides a reproducible, automated way to generate standardized Raspberry Pi images that:

1. Work consistently across the hive monitoring network
2. Include all required security configurations
3. Come pre-installed with sensor management software
4. Support automatic connection to the central hub
5. Include monitoring and diagnostic capabilities
6. Are reproducible and version-tracked

## Key Features

- Declarative configuration through YAML files
- Comprehensive environment variable support
- Multi-stage build process with validation
- Support for multiple Raspberry Pi hardware versions
- Pre-configured security settings including WireGuard VPN
- TimescaleDB and data collection tools pre-installed
- System monitoring and diagnostics
- Automated deployment to download servers
- Verification and testing capabilities

## Architecture

The image generator follows a multi-stage pipeline:

1. **Configuration** - Parse and validate input parameters
2. **Base Image** - Download and prepare base OS image
3. **OS Configuration** - Apply basic system settings
4. **Software Installation** - Install required packages and dependencies
5. **Security Setup** - Configure SSH, VPN, firewall, and encryption
6. **Service Configuration** - Set up systemd services and startup scripts
7. **W4B Software Installation** - Install and configure all W4B components
8. **Customization** - Apply hive-specific configurations
9. **Validation** - Verify the generated image meets requirements
10. **Compression & Distribution** - Prepare for distribution

## Usage

### Basic Usage

```bash
python image_generator.py --hive-id <HIVE_ID> --output-dir /path/to/output
```

### Configuration Options

The generator supports both command-line arguments and environment variables:

| Option | Environment Variable | Description |
|--------|---------------------|-------------|
| --hive-id | W4B_HIVE_ID | ID of the hive to generate an image for |
| --output-dir | W4B_IMAGE_OUTPUT_DIR | Directory to store generated images |
| --raspios-version | W4B_RASPIOS_VERSION | Version of Raspberry Pi OS to use |
| --pi-model | W4B_PI_MODEL | Raspberry Pi model (3, 4, or 5) |
| --timezone | W4B_TIMEZONE | Default timezone |
| --download-server | W4B_DOWNLOAD_SERVER | Server URL for downloads |
| --vpn-server | W4B_VPN_SERVER | WireGuard VPN server endpoint |
| --config-file | W4B_CONFIG_FILE | Path to YAML configuration file |

### Advanced Configuration

For more detailed configuration, a YAML file can be provided:

```yaml
# Example configuration
base_image:
  version: "2023-12-05"
  model: "pi4"
  checksum: "sha256:abcdef1234567890"

system:
  hostname_prefix: "hive"
  timezone: "Europe/Berlin"
  locale: "en_US.UTF-8"
  keyboard: "us"
  ssh:
    enabled: true
    password_auth: false
    port: 22

security:
  firewall:
    enabled: true
    allow_ports: [22, 51820, 9100]
  vpn:
    type: "wireguard"
    server: "vpn.example.com:51820"
    subnet: "10.10.0.0/24"

services:
  sensor_manager:
    enabled: true
    auto_start: true
  monitoring:
    enabled: true
    metrics_port: 9100
  database:
    type: "timescaledb"
    version: "latest"
    retention_days: 30
    auto_backup: true

software:
  packages:
    - postgresql-14
    - postgresql-14-timescaledb-2
    - wireguard
    - python3-pip
    - python3-venv
  python_requirements:
    file: "requirements.txt"
```

## Integration Points

The Image Generator integrates with other W4B components:

- **Hive Configuration Manager**: Sources hive-specific configurations
- **Security Framework**: Obtains SSH keys and VPN credentials
- **Sensor Management System**: Installs the latest sensor collection software
- **Monitoring System**: Configures metrics collection and reporting
- **VPN Management**: Sets up secure connections to the hub

## Development Guide

### Requirements

- Python 3.9+
- Required Python packages:
  - pybuild
  - pyyaml
  - jinja2
  - cryptography
  - paramiko

### Setup Development Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### Running Tests

```bash
# Run all tests
pytest

# Run a specific test
pytest tests/test_image_builder.py
```

### Building Documentation

```bash
# Generate documentation
sphinx-build -b html docs/source docs/build
```

## Troubleshooting

Common issues and solutions:

- **Permission Errors**: Ensure you have sufficient privileges to mount loop devices
- **Network Issues**: Check connectivity if image download fails
- **Space Issues**: At least 10GB free space is required for image generation
- **Validation Failures**: See logs in the output directory for detailed errors

## Real-World Image Generation Example

This section walks through generating a Raspberry Pi image using a real hive configuration from the hive configuration manager.

### Prerequisites

1. Access to the hive configuration from the hive configuration manager
2. Sufficient disk space (~8GB for working files)
3. Required permissions to run loop devices (root or sudo access)
4. Python environment with all dependencies installed

### Step 1: Prepare the Configuration

First, convert the hive configuration into a format suitable for the image generator:

```bash
# Create a directory for your configurations if it doesn't exist
mkdir -p configs

# Use the built-in conversion utility (alternative to manually creating the config file)
python -m utils.config_converter --hive-config /path/to/hive_config.yaml --output configs/hive_image_config.yaml --pi-model 3
```

Alternatively, you can manually create the configuration file as shown in the example below.

### Step 2: Verify the Configuration

Review the configuration file to ensure all required settings are present:

```bash
# Display and check the configuration
cat configs/hive_image_config.yaml
```

Ensure that security credentials (SSH keys, VPN keys, passwords) are correctly included in the configuration.

### Step 3: Run the Image Generator

Generate the image using the configuration file:

```bash
# Generate the image
sudo python image_generator.py --config-file configs/hive_0Bpfj4cT_pi3.yaml --verbose
```

The image generator will:

1. Download the appropriate Raspberry Pi OS base image
2. Mount and modify the image with custom settings
3. Install required software packages
4. Configure security settings (SSH, VPN, firewall)
5. Set up the sensor management system
6. Validate the generated image
7. Compress and prepare the final image

The output will be stored in the directory specified in the configuration file.

### Step 4: Verify the Generated Image

Verify the generated image:

```bash
# Check the image integrity
python image_generator.py --verify --image-file /tmp/generated_images/w4b_pi3_hive_0Bpfj4cT_20230615_120000.img.xz
```

### Step 5: Deploy the Image

The image can now be written to an SD card using standard tools:

```bash
# Write the image to an SD card (Linux example)
xzcat /tmp/generated_images/w4b_pi3_hive_0Bpfj4cT_20230615_120000.img.xz | sudo dd of=/dev/sdX bs=4M status=progress
```

### Example: Generating an Image for Raspberry Pi 3 Using Hive Configuration

Here's a complete example using a real hive configuration to generate a Raspberry Pi 3 image:

```bash
# Clone the repository if you haven't already
git clone https://github.com/itsatony/w4b_v3.git
cd w4b_v3/edge/raspiImageGenerator

# Make sure your environment is set up
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Generate the image (using a pre-prepared configuration)
sudo python image_generator.py --config-file configs/hive_0Bpfj4cT_pi3.yaml --output-dir /tmp/generated_images

# After generation, the image will be at:
# /tmp/generated_images/w4b_pi3_hive_0Bpfj4cT_20230615_120000.img.xz

# Write the image to an SD card
sudo dd if=/tmp/generated_images/w4b_pi3_hive_0Bpfj4cT_20230615_120000.img of=/dev/sdX bs=4M status=progress
```

### Troubleshooting Common Issues

1. **Insufficient Disk Space**: Ensure at least 8GB free space for working files
2. **Permission Errors**: Run with sudo to access loop devices
3. **Network Issues**: Check your internet connection if base image download fails
4. **Mount Failures**: Ensure loop devices are available on your system
5. **SSH Key Format**: Ensure SSH keys are properly formatted in the configuration
6. **WireGuard Configuration**: Check WireGuard endpoint and key formats

### Advanced: Automating Image Generation

For automated generation of multiple images, create a script:

```python
import subprocess
import glob
import os

HIVE_CONFIG_DIR = "/path/to/hive_configs"
OUTPUT_DIR = "/path/to/output"

# Find all hive configs
hive_configs = glob.glob(f"{HIVE_CONFIG_DIR}/*.yaml")

for config_file in hive_configs:
    hive_id = os.path.basename(config_file).replace(".yaml", "")
    output_file = f"{OUTPUT_DIR}/{hive_id}_pi3.img.xz"
    
    # Generate Raspberry Pi 3 compatible configuration
    subprocess.run([
        "python", "-m", "utils.config_converter",
        "--hive-config", config_file,
        "--output", f"/tmp/{hive_id}_pi3_config.yaml",
        "--pi-model", "3"
    ])
    
    # Generate the image
    subprocess.run([
        "sudo", "python", "image_generator.py",
        "--config-file", f"/tmp/{hive_id}_pi3_config.yaml",
        "--output-dir", OUTPUT_DIR,
        "--verbose"
    ])
    
    print(f"Generated image for {hive_id}: {output_file}")
```

This script will automatically convert configurations and generate images for multiple hives.

