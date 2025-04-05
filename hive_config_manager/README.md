# Hive Configuration Manager

A robust configuration management system for distributed beehive monitoring networks. This tool manages the configuration lifecycle of edge devices (Raspberry Pis) in a secure and maintainable way.

## Features

- 🔧 Interactive CLI interface for configuration management
- 🔒 Comprehensive security credential management (SSH, WireGuard, Database)
- 🖥️ Integrated Raspberry Pi image generation for edge devices
- 🔄 Version control and backup management
- 📝 YAML-based configuration format
- 🚦 Real-time configuration validation
- 🔍 Configuration search and filtering
- 💾 Automatic backup generation
- 🛡️ Role-based access control integration
- 📡 VPN and network security management

## Installation

### Prerequisites

- Python 3.8 or higher
- Git (for development)
- Linux/Unix environment
- PyYAML, Inquirer, and other dependencies

### Quick Start

1. Clone the repository:

```bash
git clone https://github.com/itsatony/w4b_v3.git
cd w4b_v3
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the configuration manager:

```bash
python -m hive_config_manager.hive_config_manager
```

## Usage

### CLI Interface

Launch the interactive configuration manager:

```bash
python -m hive_config_manager.hive_config_manager
```

### Command-Line Options

```bash
# Generate a Raspberry Pi image for a specific hive
python -m hive_config_manager.hive_config_manager --generate-image HIVE_ID
```

### Interactive Menu

The main menu provides the following options:

- **List hives**: Display all configured hives
- **Add new hive**: Create a new hive configuration with guided setup
- **Edit hive**: Modify an existing hive configuration
- **Remove hive**: Delete a hive configuration
- **Validate hive**: Check configuration for errors
- **Generate image**: Create a Raspberry Pi image for a hive (when integrated UI is available)

### Keyboard Shortcuts

- `n`: Create new hive configuration
- `e`: Edit selected configuration
- `d`: Delete selected configuration
- `v`: Validate selected configuration
- `g`: Generate Raspberry Pi image for selected hive
- `Tab`: Switch between panels
- `Ctrl+C` or `Ctrl+Q`: Quit

## Security Configuration

The configuration manager handles all security credentials required for a secure edge device:

### SSH Access

- Generates SSH key pairs for secure remote access
- Configures authorized keys and authentication settings
- Manages SSH port and access restrictions

### WireGuard VPN

- Creates secure WireGuard configurations for edge-to-hub communication
- Manages private/public key pairs and client IPs
- Configures endpoint, allowed IPs, and persistent keepalive settings

### Local Access

- Manages local admin accounts with secure password generation
- Configures sudo access and permissions

### Database Credentials

- Generates and manages database credentials for local data storage
- Configures database users, passwords, and access controls

## Image Generation

The hive configuration manager integrates with a Raspberry Pi image generator to create pre-configured SD card images:

```bash
# Generate image via CLI option
python -m hive_config_manager.hive_config_manager --generate-image my_hive_id

# Or use the interactive interface and press 'g' on a selected hive
```

The image generator:

1. Validates the hive configuration for completeness
2. Applies all security credentials and network settings
3. Creates a custom Raspberry Pi OS image with TimescaleDB and other requirements
4. Configures SSH, WireGuard VPN, firewall, and other security features
5. Sets up first-boot initialization for final configuration

## Configuration Format

Example hive configuration including security settings:

```yaml
hive_id: hive_x7k9m2p4
version: "1.0.0"
metadata:
  name: "Test Hive 1"
  location:
    address: "123 Bee Street"
    latitude: 48.123456
    longitude: 11.123456
    timezone: "Europe/Berlin"
  notes: "Main monitoring hive"

network:
  primary: "wifi"
  wifi:
    - ssid: "Network1"
      password: "pass1"
      priority: 1

administrators:
  - name: "John Doe"
    email: "john@example.com"
    username: "john_doe"
    phone: "+1234567890"
    role: "hive_admin"

sensors:
  - id: "temp_01"
    type: "dht22"
    name: "Temperature Sensor 1"
    enabled: true
    interface:
      type: "gpio"
      pin: 4

security:
  wireguard:
    private_key: "<encrypted-private-key>"
    public_key: "<public-key>"
    endpoint: "vpn.server.example.com:51820"
    allowed_ips: "10.10.0.0/24"
    client_ip: "10.10.0.X/32"
  
  ssh:
    private_key: "<encrypted-private-key>"
    public_key: "<public-key>"
    enable_password_auth: false
    allow_root: false
    port: 22
  
  database:
    username: "hiveuser"
    password: "<generated-password>"
    host: "localhost"
    port: 5432
    database: "hivedb"
  
  local_access:
    username: "hiveadmin"
    password: "<generated-password>"
    sudo_without_password: false
```

## Validation

The system validates all aspects of the configuration:

- Required fields and data types
- Network settings and connectivity options
- Security credential formats and requirements
- Sensor configurations and interfaces
- Geographic coordinates and timezones
- Administrator settings and permissions

## Troubleshooting

### Common Issues

1. **Missing Security Credentials**

If you receive errors about missing security credentials when generating an image:
