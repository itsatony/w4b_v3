# HiveCtl

HiveCtl is a management tool for containerized infrastructure that uses podman and podman-compose. It provides a unified interface for managing containers, networks, and volumes through a label-based approach.

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
git clone https://github.com/itsatony/w4b_v3.git
cd w4b_v3/server/w4bcontainers/hivectl
pip install -e .
```

### Using pip

```bash
pip install hivectl
```

## Core Concepts

### Label-Based Management

HiveCtl uses a hierarchical label system to organize and manage containers:

```yaml
services:
  example_service:
    labels:
      hive.w4b.group: "group_name"     # Logical grouping of services
      hive.w4b.type: "service_type"    # Type of service (e.g., database, service, cache)
      hive.w4b.description: "..."      # Human-readable description
      hive.w4b.priority: "10"          # Start/stop priority
      hive.w4b.depends_on: "svc1,svc2" # Service dependencies
      hive.w4b.required_by: "svc3"     # Inverse dependencies
```

### Group-Based Operations

Services can be managed individually or as groups:

```bash
hivectl start auth        # Starts all services in the 'auth' group
hivectl stop monitoring   # Stops all services in the 'monitoring' group
```

### State Management

HiveCtl maintains state information through compose file analysis and runtime inspection:

- Network states are tracked and validated
- Volume existence and configurations are verified
- Container health and status are monitored

## Architecture

### Core Components

1. **ComposeConfig**
   - Parses and validates compose file
   - Manages service metadata
   - Handles dependency resolution

2. **NetworkManager**
   - Network creation and validation
   - Subnet management
   - Network state tracking

3. **VolumeManager**
   - Volume lifecycle management
   - Configuration management
   - State validation

4. **ContainerManager**
   - Container lifecycle operations
   - Health monitoring
   - Group resolution

### Command Flow
1. Command invocation
2. Compose file parsing
3. State validation
4. Dependency resolution
5. Operation execution
6. Status update

## Implementation Details

### Service Resolution
```python
# Group to service resolution
services = manager.resolve_services(['auth'])
# Resolves to actual services: ['keycloak', 'postgres_auth', ...]
```

### State Tracking
```python
# Network state example
{
    'network_name': NetworkState(
        exists=True,
        subnet='10.0.0.0/24',
        internal=True,
        ...
    )
}
```

### Health Checks
- Container health is monitored through podman health checks
- States: healthy, unhealthy, starting, unknown
- Progressive backoff for health check retries

## Working with HiveCtl

### Extending Commands
To add a new command:
1. Create command function in hivectl.py
2. Use click decorators for CLI interface
3. Implement in appropriate manager class
4. Add to COMMANDS dictionary

Example:
```python
@cli.command()
@click.argument('name')
def new_command(name: str):
    """Command description"""
    hive = get_hivectl()
    try:
        # Implementation
        with ui.show_progress("Operation...") as progress:
            task = progress.add_task("Working...", total=1)
            # Do work
            progress.update(task, completed=1)
    except Exception as e:
        ui.print_error(e)
        sys.exit(1)
```

### Adding Features to Managers
Manager classes follow a pattern:
1. Initialize with compose config
2. Provide state inspection methods
3. Implement operations
4. Handle errors consistently

Example:
```python
class NewManager:
    def __init__(self, compose_config):
        self.compose = compose_config
        
    def get_state(self) -> Dict[str, State]:
        # State inspection
        
    def ensure_resources(self) -> bool:
        # Resource management
        
    def operation(self, resource: str) -> bool:
        # Specific operation implementation
```

### Error Handling
HiveCtl uses a hierarchical exception system:
```python
class HiveCtlError(Exception): pass
class ResourceError(HiveCtlError): pass
class OperationError(HiveCtlError): pass
```

### UI Patterns
The ConsoleUI class provides consistent output formatting:
- Progress indicators for long operations
- Color-coded status output
- Structured error messages
- Table-based data display

## Best Practices

1. **State Validation**
   - Always check current state before operations
   - Validate against compose file configurations
   - Provide clear error messages for mismatches

2. **Error Handling**
   - Use specific exceptions for different error types
   - Provide recovery suggestions where possible
   - Log errors with appropriate detail level

3. **Progress Indication**
   - Use progress indicators for long operations
   - Show intermediate steps
   - Provide clear success/failure messages

4. **Resource Management**
   - Clean up resources on failure
   - Validate configurations before creating resources
   - Check dependencies before operations

5. **Command Design**
   - Follow existing command patterns
   - Provide --help documentation
   - Include force/skip options where appropriate

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

## Debugging Tips

1. Enable debug logging:

```bash
hivectl --debug 
```

2. Inspect service state:

```bash
hivectl inspect 
```

3. View detailed logs:

```bash
hivectl show-logs -n 100
```
