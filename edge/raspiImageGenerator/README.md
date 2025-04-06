# W4B Raspberry Pi Image Generator

A tool for generating customized Raspberry Pi images for the W4B beehive monitoring system.

## Features

- Automated download and caching of Raspberry Pi OS images
- Customization of system configuration
- Installation of required software packages
- Integration with W4B sensor management system
- Security hardening with WireGuard VPN setup
- Compression and packaging of final images
- Publication of images to a web server with downloadable links

## Prerequisites

- Python 3.6 or higher
- Required system packages: `losetup`, `mount`, `xz-utils`, `kpartx`
- Python packages listed in `requirements.txt`

## Installation

1. Clone the repository:
```bash
git clone https://github.com/itsatony/w4b_v3.git
cd w4b_v3/edge/raspiImageGenerator
```

2. Install required system dependencies:
```bash
sudo apt-get update
sudo apt-get install -y util-linux mount xz-utils kpartx
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
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

## Downloading Generated Images

After generation, images are automatically published to a web server. The download URL will be displayed in the output log:

```
=================================================
Image successfully published!
Download URL: https://queenb.vaudience.io:14800/files/2025-04-06_12-45_hive_0Bpfj4cT_1.0.0_image.xz
For convenient download use:
wget https://queenb.vaudience.io:14800/files/2025-04-06_12-45_hive_0Bpfj4cT_1.0.0_image.xz
=================================================
```

You can customize the download server location using these environment variables:

- `W4B_IMAGE_DOWNLOAD_URL_BASE`: Base URL for downloading images (default: `https://queenb.vaudience.io:14800/files/`)
- `W4B_IMAGE_SERVER_BASEPATH`: Local server path where images are stored (default: `/home/itsatony/srv/`)

## Debugging Tools

The following tools are available to help diagnose and troubleshoot issues with the image generation process.

### Using run_debug.sh

The `run_debug.sh` script performs comprehensive system checks before running the image generator:

```bash
./run_debug.sh
```

This script:
1. Checks system information and available disk space
2. Verifies all required system binaries are installed
3. Confirms Python dependencies are available
4. Runs the image generator with DEBUG logging level

## Configuration

The image generator is configured via YAML files. Example configuration:

```yaml
# Sample configuration
base_image:
  version: "2024-01-12-raspios-bullseye-arm64-lite"
  url_template: "https://downloads.raspberrypi.org/raspios_lite_arm64/images/raspios_lite_arm64-{version}/2024-01-12-raspios-bullseye-arm64-lite.img.xz"
  checksum_type: "sha256"
  model: "pi4"

system:
  hostname_prefix: "hive"
  timezone: "Europe/Berlin"
  locale: "en_US.UTF-8"
  keyboard: "de"
  ssh:
    enabled: true
    password_auth: false
    port: 22

security:
  vpn:
    type: "wireguard"
    server: "vpn.example.com"

software:
  packages:
    - "git"
    - "python3-pip"
    - "wireguard"
    - "postgresql"
    - "prometheus-node-exporter"
  python_packages:
    - "pyyaml"
    - "asyncpg"

# Publishing settings
download_url_base: "https://queenb.vaudience.io:14800/files/" # Can be overridden with W4B_IMAGE_DOWNLOAD_URL_BASE
server_base_path: "/home/itsatony/srv/" # Can be overridden with W4B_IMAGE_SERVER_BASEPATH
```

For more configuration options, see the example files in the `configs` directory.

## Contributing

Please follow the project's coding standards and submit pull requests for review.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
