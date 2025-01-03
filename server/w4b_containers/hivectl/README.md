# HiveCtl

Management tool for containerized infrastructure with a focus on monitoring and control.

## Features

- Service management with health monitoring
- Network and volume management
- Resource usage monitoring
- Configuration validation
- Detailed logging and diagnostics

## Requirements

- Python 3.8 or higher
- Podman and podman-compose
- Linux operating system

## Installation

### From Source
```bash
git clone https://github.com/we4bee/hivectl.git
cd hivectl
pip install -e .
```

### Using pip
```bash
pip install hivectl
```

## Usage

HiveCtl requires a valid `compose.yaml` file in the current directory. The compose file should include proper labels for service management.

### Basic Commands

```bash
# Show service status
hivectl status

# Start services
hivectl start [SERVICE...]

# Stop services
hivectl stop [SERVICE...]

# Show health status
hivectl health

# Show logs
hivectl logs SERVICE
```

### Service Labels

HiveCtl uses labels in the compose file to manage services. Required labels:

```yaml
services:
  example_service:
    labels:
      hive.w4b.group: "group_name"
      hive.w4b.type: "service_type"
      hive.w4b.description: "Service description"
      hive.w4b.priority: "10"
```

Optional labels:
```yaml
      hive.w4b.depends_on: "service1,service2"
      hive.w4b.required_by: "service3,service4"
```

## Configuration

HiveCtl uses a hierarchical label structure:
- `hive.` - Tool namespace
- `w4b.` - Project identifier
- `label_name` - Actual label (group, type, etc.)

## Development

### Setup Development Environment
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### Running Tests
```bash
pytest tests/
```
