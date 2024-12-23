# Hive Configuration Manager

A robust configuration management system for distributed hive monitoring networks. This tool manages the configuration lifecycle of edge devices (Raspberry Pis) in a secure and maintainable way.

## Features

- 🔧 Interactive CLI interface for configuration management
- 🔒 Secure configuration storage with validation
- 🔄 Version control and backup management
- 📝 YAML-based configuration format
- 🚦 Real-time configuration validation
- 🔍 Configuration search and filtering
- 💾 Automatic backup generation
- 🛡️ Role-based access control integration

## Installation

### Prerequisites

- Python 3.8 or higher
- Git (for development)
- Linux/Unix environment

### Quick Start

1. Clone the repository:

```bash
git clone https://github.com/itsatony/w4b_v3.git
cd hive_config_manager
```

2. Run the setup script:

```bash
# For production
./setup.sh

# For development
./setup.sh --dev
```

3. Activate the virtual environment:

```bash
source .venv/bin/activate
```

## Usage

### CLI Interface

Launch the interactive configuration manager:

```bash
python -m hive_config_manager
```

### Keyboard Shortcuts

- `n`: Create new hive configuration
- `e`: Edit selected configuration
- `d`: Delete selected configuration
- `v`: Validate selected configuration
- `Tab`: Switch between panels
- `Ctrl+C` or `Ctrl+Q`: Quit

### Configuration Format

Example hive configuration:

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
```

## Development

### Project Structure

```skeleton
hive_config_manager/
├── core/
│   ├── manager.py       # Core management functionality
│   ├── validator.py     # Configuration validation
│   ├── schemas.py       # Configuration schemas
│   └── exceptions.py    # Custom exceptions
├── cli/
│   ├── interface.py     # CLI interface
│   └── prompts.py       # User interaction prompts
├── utils/
│   ├── file_operations.py
│   └── id_generator.py
├── tests/
│   ├── test_manager.py
│   ├── test_validator.py
│   └── fixtures/
└── requirements/
    ├── requirements.txt
    └── requirements-dev.txt
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=hive_config_manager

# Run specific test file
pytest tests/test_manager.py
```

### Code Style

The project uses:

- Black for code formatting
- isort for import sorting
- flake8 for linting
- mypy for type checking

Run style checks:

```bash
# Format code
black .

# Sort imports
isort .

# Run linter
flake8

# Type checking
mypy .
```

### Pre-commit Hooks

Install pre-commit hooks:

```bash
pre-commit install
```

## Configuration Validation

The system validates:

- Required fields presence
- Data types and formats
- Value ranges and constraints
- Network configurations
- Security settings
- Sensor configurations

## Error Handling

Common error scenarios:

- Invalid configuration format
- Missing required fields
- Invalid data types
- Network configuration errors
- Permission issues
- File system errors

## Security Considerations

- All configurations are stored with secure permissions
- Sensitive data (passwords, keys) are handled securely
- File operations use atomic writes
- Backup files are created before modifications
- Lock files prevent concurrent modifications

## Troubleshooting

### Common Issues

1. Permission Errors

```bash
sudo chown -R $(whoami) hives/
chmod 700 hives/
```

2. Lock File Issues

```bash
# Remove stale lock files
find hives/ -name "*.lock" -delete
```

3. Virtual Environment Issues

```bash
# Recreate virtual environment
rm -rf .venv
./setup.sh --dev
```
