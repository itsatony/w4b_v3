# W4B Raspberry Pi Image Generator

A tool for generating customized Raspberry Pi OS images for W4B hive monitoring systems.

## Overview

The W4B Raspberry Pi Image Generator creates customized Raspberry Pi OS images with pre-configured settings, software, and security for beehive monitoring systems. The generator downloads a base Raspberry Pi OS image, modifies it with configuration settings, and prepares firstboot scripts that will complete the setup when the Raspberry Pi boots for the first time.

## Key Features

- **Declarative Configuration**: Define image properties in YAML format
- **Firstboot Auto-Installation**: Packages and software are installed on first boot
- **Configuration Inheritance**: Use template configurations for multiple hives
- **WireGuard VPN Support**: Automatic VPN configuration for secure connections
- **Security Hardening**: SSH hardening, firewall configuration, and secure defaults
- **Sensor Manager Integration**: Automatic setup of the W4B sensor management system

## Architecture

The image generator uses a firstboot script approach rather than trying to emulate ARM architecture during image creation. This provides several advantages:

- More reliable image generation
- Better compatibility across different Raspberry Pi models
- Smaller initial images
- Native installation on target hardware

### Pipeline Stages

1. **Configuration**: Parse and validate configuration files
2. **Download**: Acquire and verify base Raspberry Pi OS image
3. **Mount**: Mount image partitions for modification
4. **System Configuration**: Configure basic system settings (hostname, locale, etc.)
5. **Security Configuration**: Set up SSH keys, WireGuard VPN, firewall
6. **Software Installation Scripts**: Prepare firstboot scripts for package installation
7. **W4B Software Setup**: Configure W4B-specific software and services
8. **Validation**: Verify image modifications
9. **Compression**: Prepare final image for distribution

## Requirements

- Linux host system (with losetup, mount, etc.)
- Python 3.9+
- Required packages: xz-utils, kpartx, parted
- Internet connection for downloading base images and packages

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourorg/w4b_v3.git
   cd w4b_v3/edge/raspiImageGenerator
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Ensure system dependencies are installed:
   ```
   sudo apt update
   sudo apt install xz-utils kpartx parted
   ```

## Usage

### Basic Usage

```bash
python image_generator.py --config configs/sample_config.yaml --hive-id hive1
```

### Detailed Debugging

For detailed logging and debugging:

```bash
clear && python image_generator.py --config configs/hive_0Bpfj4cT_pi3.yaml --hive-id hive_0Bpfj4cT --verbose
```

## Debugging Tools

The following tools are available to help diagnose and troubleshoot issues with the image generation process.

### Using run_debug.sh

The `run_debug.sh` script performs comprehensive system checks before running the image generator:

```bash
./run_debug.sh
```

Example output:
```
=== System Information ===
Linux hostname 5.15.0-92-generic #102-Ubuntu SMP Wed Jan 10 10:37:04 UTC 2024 x86_64 x86_64 x86_64 GNU/Linux
Python version: Python 3.10.12
Available disk space: 35G

=== Checking Dependencies ===
✓ losetup found: /usr/sbin/losetup
✓ mount found: /usr/bin/mount
✓ umount found: /usr/bin/umount
✓ partprobe found: /usr/sbin/partprobe
✓ kpartx found: /usr/sbin/kpartx
✓ xz found: /usr/bin/xz

=== Checking Python Modules ===
✓ yaml installed
✓ aiohttp installed
✓ pathlib installed

=== Running Image Generator with Debug Logging ===
...
```

This script:

1. Checks system information and available disk space
2. Verifies all required system binaries are installed
3. Confirms Python dependencies are available
4. Runs the image generator with DEBUG logging level

### Stage-by-Stage Debugging

To debug specific stages of the pipeline, you can use the verbose flag and filter the logs:

```bash
python image_generator.py --config configs/sample_config.yaml --hive-id test_hive --verbose 2>&1 | grep "stage\."
```

This will show only the stage-related log messages, helping you identify which stage might be failing.

### Configuration Options

Create a YAML configuration file like this:

```yaml
base_image:
  version: "2023-12-05-raspios-bullseye-arm64-lite"
  model: "pi4"

system:
  hostname_prefix: "hive"
  timezone: "Europe/Berlin"
  locale: "en_US.UTF-8"
  keyboard: "us"

security:
  ssh:
    enabled: true
    password_auth: false
    public_key: "ssh-rsa AAAA..."
  vpn:
    type: "wireguard"
    server: "vpn.example.com"
    config: |
      [Interface]
      PrivateKey = ...
      Address = 10.10.0.2/24
      
      [Peer]
      PublicKey = ...
      Endpoint = vpn.example.com:51820
      AllowedIPs = 10.10.0.0/24
  firewall:
    enabled: true
    allow_ports: [22, 51820, 9100]

services:
  sensor_manager:
    enabled: true
    auto_start: true
  monitoring:
    enabled: true
    metrics_port: 9100
  database:
    type: "timescaledb"
    retention_days: 30

software:
  packages:
    - "postgresql-14"
    - "postgresql-14-timescaledb-2"
    - "wireguard"
    - "python3-pip"
    - "prometheus-node-exporter"
  python_packages:
    - "asyncpg"
    - "prometheus-client"
    - "pyyaml"
```

### Environment Variables

You can override configuration settings with environment variables:

- `W4B_HIVE_ID`: ID of the hive to configure
- `W4B_IMAGE_OUTPUT_DIR`: Directory for the output image
- `W4B_RASPIOS_VERSION`: Version of Raspberry Pi OS to use
- `W4B_PI_MODEL`: Raspberry Pi model to target
- `W4B_TIMEZONE`: System timezone
- `W4B_VPN_SERVER`: VPN server address

## First Boot Process

When the generated image boots on a Raspberry Pi for the first time, it will:

1. Run the firstboot script from the boot partition
2. Install all required packages
3. Configure the system according to specifications
4. Set up the W4B sensor manager and services
5. Enable secure communications via WireGuard VPN
6. Configure monitoring and databases
7. Remove the firstboot script to prevent re-execution

## Troubleshooting

### Image Generation Fails

- Check disk space (at least 8GB required)
- Ensure all dependencies are installed
- Check network connectivity for downloads

### First Boot Issues

- Enable debug logging in firstboot scripts
- Check `/boot/firstboot.log` on the Raspberry Pi
- Ensure the Raspberry Pi has internet access during first boot

## Development

### Adding a New Stage

1. Create a new class in `core/stages/` inheriting from `BuildStage`
2. Implement the `execute()` method
3. Add the stage to the pipeline in `core/pipeline.py`

### Testing

Run basic validation tests:

```bash
python -m unittest discover tests
```

## License

MIT
