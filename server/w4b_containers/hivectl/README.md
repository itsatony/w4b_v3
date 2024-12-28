# HiveCtl - We4Bee Server Management Tool

HiveCtl is a command-line tool for managing the We4Bee server infrastructure, providing easy access to common administrative tasks and monitoring capabilities.

## Features

- Service management (start, stop, restart)
- Health monitoring and diagnostics
- Resource usage statistics
- Log management
- VPN connection monitoring
- Network and volume management
- Configuration verification
- System cleanup utilities

## Prerequisites

- Python 3.8 or higher
- Docker and Docker Compose
- Access to We4Bee server infrastructure

## Installation

1. Clone the repository and navigate to the hivectl directory:
   ```bash
   cd /server/w4b_containers/hivectl
   ```

2. Run the setup script:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

The setup script will:
- Create a Python virtual environment
- Install required dependencies
- Create a system-wide `hivectl` command

## Manual Setup

If you prefer manual setup:

1. Create virtual environment:
   ```bash
   python3 -m venv .venv
   ```

2. Activate virtual environment:
   ```bash
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Basic Commands

```bash
# Show service status
hivectl status [--service SERVICE]

# Start services
hivectl start [SERVICES] [--force]

# Stop services
hivectl stop [SERVICES]

# Restart services
hivectl restart [SERVICES]

# View logs
hivectl logs SERVICE [-n LINES] [-f]

# Run health checks
hivectl health

# Update services
hivectl update [--service SERVICE]

# Clean up resources
hivectl cleanup

# Initialize or reset data directories
hivectl init-data [--force]
```

### Monitoring Commands

```bash
# Show resource usage statistics
hivectl stats [--full]

# Show network information
hivectl networks

# List volumes and usage
hivectl volumes

# Show VPN connections
hivectl vpn

# Show configuration status
hivectl config
```

### Advanced Commands

```bash
# Debug service
hivectl debug SERVICE

# Open shell in service
hivectl exec SERVICE
```

## Command Details

### Service Management

- `status`: Shows the current status of all services or a specific service
  ```bash
  hivectl status --service keycloak
  ```

- `start`: Starts one or more services
  ```bash
  hivectl start prometheus grafana
  hivectl start --force  # Recreate containers
  ```

- `stop`: Stops one or more services
  ```bash
  hivectl stop timescaledb
  ```

### Monitoring

- `stats`: Shows resource usage statistics
  ```bash
  hivectl stats --full  # Show detailed statistics
  ```

- `health`: Runs comprehensive health checks
  ```bash
  hivectl health
  ```

- `vpn`: Shows VPN connection status
  ```bash
  hivectl vpn
  ```

### Maintenance

- `update`: Updates services to latest versions
  ```bash
  hivectl update --service redis
  ```

- `cleanup`: Removes unused resources
  ```bash
  hivectl cleanup
  ```

- `volumes`: Shows volume information
  ```bash
  hivectl volumes
  ```

## Logs and Debugging

- View logs:
  ```bash
  hivectl logs keycloak -n 100  # Show last 100 lines
  hivectl logs prometheus -f    # Follow log output
  ```

- Debug service:
  ```bash
  hivectl debug timescaledb
  ```

- Access service shell:
  ```bash
  hivectl exec postgres_app
  ```

## Configuration Status

Check configuration status:
```bash
hivectl config
```

This shows:
- Compose file status
- Configuration directory status
- Data directory status

## Error Handling

- Commands provide colored output for status and errors
- Detailed error messages for troubleshooting
- Non-zero exit codes for failed operations

## Development

To modify or extend HiveCtl:

1. Activate the virtual environment:
   ```bash
   source .venv/bin/activate
   ```

2. Make changes to `hivectl.py`

3. Add new dependencies to `requirements.txt` if needed

4. Run setup script to update installation:
   ```bash
   ./setup.sh
   ```

## Common Issues

1. Permission Denied:
   ```bash
   sudo chown -R $USER:$USER /server/w4b_containers/hivectl
   ```

2. Command Not Found:
   ```bash
   hash -r  # Reset command hash table
   ```

3. Virtual Environment Issues:
   ```bash
   rm -rf .venv
   ./setup.sh  # Recreate environment
   ```

1. Permission Denied on Data Directories:
   ```bash
   hivectl init-data  # Initialize data directories with correct permissions
   ```

2. Docker Socket Permission Issues:
   ```bash
   sudo usermod -aG docker $USER  # Add user to docker group
   ```

## Support

For issues and feature requests, please contact the We4Bee team.