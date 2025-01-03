import os
import sys
import time
import click
import subprocess
import json
import yaml
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.tree import Tree
from rich import print as rprint

VERSION = "1.2.0"
console = Console()

class HiveCtl:
    def __init__(self):
        self.script_dir = Path(__file__).resolve().parent
        self.deployment_dir = self.script_dir.parent
        self.scripts_dir = self.deployment_dir / "scripts"
        self.compose_file = self.deployment_dir / "compose.yaml"
        self.config_dir = self.deployment_dir / "config"
        self.env = self.load_env()
        self.load_compose_config()
        self.service_groups = self._load_service_groups()
        self.service_metadata = self._load_service_metadata()
        self.networks = self._load_network_metadata()
        self.volumes = self._load_volume_metadata()
        self.project_name = "w4b"

    def _load_service_groups(self):
        """Load service groups from compose file labels"""
        groups = {}
        services = self.compose_config.get('services', {})
        
        for service_name, service_config in services.items():
            labels = service_config.get('labels', {})
            group_name = labels.get('w4b.group')
            
            if group_name:
                if group_name not in groups:
                    groups[group_name] = {
                        'description': f"Services for {group_name}",
                        'services': []
                    }
                groups[group_name]['services'].append(service_name)
        
        return groups

    def _load_service_metadata(self):
        """Load service groups and metadata from compose file labels"""
        metadata = {
            'groups': {},
            'services': {},
            'types': set()
        }
        
        services = self.compose_config.get('services', {})
        for service_name, service_config in services.items():
            labels = service_config.get('labels', {})
            
            # Skip services without labels
            if not labels:
                continue
            
            # Extract metadata
            group = labels.get('w4b.group')
            description = labels.get('w4b.description', '')
            service_type = labels.get('w4b.type', 'service')
            priority = int(labels.get('w4b.priority', '50'))
            depends_on = labels.get('w4b.depends_on', '').split(',')
            required_by = labels.get('w4b.required_by', '').split(',')
            
            # Clean up empty strings from lists
            depends_on = [d.strip() for d in depends_on if d.strip()]
            required_by = [r.strip() for r in required_by if r.strip()]
            
            # Store service metadata
            metadata['services'][service_name] = {
                'group': group,
                'description': description,
                'type': service_type,
                'priority': priority,
                'depends_on': depends_on,
                'required_by': required_by
            }
            
            # Add to type set
            metadata['types'].add(service_type)
            
            # Group metadata
            if group:
                if group not in metadata['groups']:
                    metadata['groups'][group] = {
                        'description': f"Services for {group}",
                        'services': [],
                        'types': set()
                    }
                metadata['groups'][group]['services'].append(service_name)
                metadata['groups'][group]['types'].add(service_type)
        
        return metadata

    def _load_network_metadata(self):
        """Load network configuration from compose file"""
        networks = {}
        for name, config in self.compose_config.get('networks', {}).items():
            networks[name] = {
                'driver': config.get('driver', 'bridge'),
                'internal': config.get('internal', False),
                'ipam': config.get('ipam', {}),
                'description': config.get('labels', {}).get('w4b.description', 'Network')
            }
        return networks

    def _load_volume_metadata(self):
        """Load volume configuration from compose file"""
        volumes = {}
        volume_configs = self.compose_config.get('volumes', {})
        
        # Group volumes by their prefix
        for name in volume_configs:
            parts = name.split('_')
            if len(parts) > 2:
                group = '_'.join(parts[0:2])  # w4b_service
                type_name = '_'.join(parts[2:])  # volume type (data, config, etc)
                if group not in volumes:
                    volumes[group] = {}
                volumes[group][type_name] = name
        
        return volumes

    def load_env(self):
        """Load environment variables from .env file"""
        env_path = self.deployment_dir / ".env"
        if (env_path.exists()):
            env_vars = {}
            with open(env_path) as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        try:
                            key, value = line.strip().split('=', 1)
                            env_vars[key.strip()] = value.strip()
                        except ValueError:
                            console.print(f"[yellow]Warning: Invalid .env line: {line.strip()}[/yellow]")
            return env_vars
        return {}

    def load_compose_config(self):
        """Load and parse the compose file"""
        try:
            with open(self.compose_file) as f:
                self.compose_config = yaml.safe_load(f)
            self.services = list(self.compose_config.get('services', {}).keys())
            self.networks = list(self.compose_config.get('networks', {}).keys())
        except FileNotFoundError:
            console.print(f"\n[red]Error: Compose file not found at {self.compose_file}[/red]")
            self.compose_config = {}
            self.services = []
            self.networks = []
        except yaml.YAMLError as e:
            console.print(f"\n[red]Error parsing compose file: {e}[/red]")
            self.compose_config = {}
            self.services = []
            self.networks = []

    def get_service_containers(self, service):
        """Get containers for a service or group"""
        metadata = self.service_metadata
        
        # Check if it's a group
        if service in metadata['groups']:
            return metadata['groups'][service]['services']
        
        # Check if it's a direct service name
        if service in metadata['services']:
            return [service]
        
        return []

    def run_command(self, cmd, capture_output=True, env=None, show_output=False):
        """Enhanced command execution with better output handling"""
        env_dict = os.environ.copy()
        if env:
            env_dict.update(env)

        try:
            with console.status(f"[cyan]Running: {cmd}[/cyan]", spinner="dots") as status:
                process = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=capture_output,
                    text=True,
                    env=env_dict,
                    cwd=self.deployment_dir
                )

                if process.returncode != 0:
                    if process.stderr:
                        console.print(f"\n[red]Error executing command:[/red]\n{process.stderr.strip()}")
                    return False

                if show_output and process.stdout:
                    console.print(f"\n{process.stdout.strip()}")

                return process if capture_output else True

        except Exception as e:
            console.print(f"\n[red]Error executing command:[/red]\n{str(e)}")
            return False

    def get_service_status(self, service=None):
        """Get status of services with enhanced error handling"""
        containers = []
        if service:
            target_containers = self.get_service_containers(service)
            for container in target_containers:
                result = self.run_command(f"podman ps --format json --filter name={container}")
                if result and result.stdout.strip():
                    try:
                        data = json.loads(result.stdout)
                        if isinstance(data, list):
                            containers.extend(data)
                        else:
                            containers.append(data)
                    except json.JSONDecodeError as e:
                        console.print(f"\n[red]Error parsing container status: {e}[/red]")
        else:
            # Get all containers
            result = self.run_command("podman ps --format json")
            if result and result.stdout.strip():
                try:
                    containers = json.loads(result.stdout)
                    if not isinstance(containers, list):
                        containers = [containers]
                except json.JSONDecodeError as e:
                    console.print(f"\n[red]Error parsing container status: {e}[/red]")

        return containers

    def get_service_details(self, service):
        """Get detailed configuration for a service"""
        return self.compose_config.get('services', {}).get(service, {})

    def verify_networks(self):
        """Verify all required networks exist"""
        try:
            existing = json.loads(self.run_command("podman network ls --format json").stdout)
            existing_names = [n['Name'] for n in existing]
            
            return {
                name: {
                    'exists': name in existing_names,
                    'config': config,
                    'details': next((n for n in existing if n['Name'] == name), None)
                }
                for name, config in self.networks.items()
            }
        except Exception as e:
            console.print(f"[red]Error verifying networks: {e}[/red]")
            return {}

    def verify_config_dirs(self):
        """Verify configuration directories from compose services"""
        config_status = {}
        
        for service_name, service_config in self.compose_config.get('services', {}).items():
            # Check for volume mounts that reference config
            for volume in service_config.get('volumes', []):
                if ':' in volume and 'config' in volume:
                    source = volume.split(':')[0]
                    if source.startswith('./config/'):
                        service_dir = self.config_dir / source.replace('./config/', '')
                        config_status[service_name] = service_dir.exists()
        
        return config_status

    def verify_volumes(self):
        """Verify all required volumes exist with improved structure"""
        try:
            volumes = self.compose_config.get('volumes', {}).keys()
            existing_volumes = json.loads(self.run_command("podman volume ls --format json").stdout)
            existing_names = [v['Name'] for v in existing_volumes]
            
            return {
                vol: {
                    'name': vol,
                    'exists': vol in existing_names,
                    'details': next((v for v in existing_volumes if v['Name'] == vol), None),
                    'size': next((v.get('Size', 'N/A') for v in existing_volumes if v['Name'] == vol), 'N/A')
                } for vol in volumes
            }
        except Exception as e:
            console.print(f"[red]Error verifying volumes: {e}[/red]")
            return {}

    def display_status(self, containers):
        """Display service status in a table"""
        table = Table(title="Hive Service Status")
        table.add_column("Service", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Health", style="yellow")
        table.add_column("Uptime", style="blue")

        for container in containers:
            name = container['Names'][0]
            status = container['State']
            health = container.get('Health', {}).get('Status', 'N/A')
            uptime = container['StartedAt']

            table.add_row(
                name,
                status,
                health,
                uptime
            )

        console.print(table)

    def display_config_status(self, verify=False):
        """Display comprehensive configuration status"""
        tree = Tree("[bold cyan]📁 System Configuration[/bold cyan]")

        # Compose file
        compose_node = tree.add("📄 compose.yaml")
        if self.compose_file.exists():
            compose_node.add("[green]✓ Present[/green]")
        else:
            compose_node.add("[red]✗ Missing[/red]")

        # Networks
        network_node = tree.add("🌐 Networks")
        network_status = self.verify_networks()
        for name, status in network_status.items():
            network_node.add(
                f"[{'green' if status['exists'] else 'red'}]{'✓' if status['exists'] else '✗'} {name}[/] "
                f"({'internal' if status['config']['internal'] else 'external'})"
            )

        # Volumes
        volume_node = tree.add("📦 Volumes")
        volume_status = self.verify_volumes()
        for group, volumes in self.volumes.items():
            group_node = volume_node.add(f"[blue]{group}[/]")
            for vol_type, vol_name in volumes.items():
                exists = vol_name in volume_status and volume_status[vol_name]['exists']
                group_node.add(f"[{'green' if exists else 'red'}]{'✓' if exists else '✗'} {vol_type}[/]")

        # Config directories
        config_node = tree.add("⚙️ Service Configs")
        config_status = self.verify_config_dirs()
        for service, exists in config_status.items():
            config_node.add(f"[{'green' if exists else 'red'}]{'✓' if exists else '✗'} {service}[/]")

        console.print(tree)

    def display_health_status(self):
        """Show health status based on compose services"""
        table = Table(title="System Health Status")
        table.add_column("Group", style="cyan")
        table.add_column("Service", style="blue")
        table.add_column("Status", style="green")
        table.add_column("Health", style="yellow")
        table.add_column("Dependencies", style="magenta")

        services = self.compose_config.get('services', {})
        for service_name, service_config in services.items():
            labels = service_config.get('labels', {})
            group = labels.get('w4b.group', 'other')
            
            # Get container status
            result = self.run_command(f"podman inspect {service_name} --format '{{{{.State.Status}}}}|{{{{.State.Health.Status}}}}|{{{{.State.Health.FailingStreak}}}}'")
            
            if result and result.stdout.strip():
                status, health, failing_streak = result.stdout.strip().split('|')
                
                # Get dependency status
                deps = labels.get('w4b.depends_on', '').split(',')
                deps_status = []
                for dep in deps:
                    if dep:
                        dep_result = self.run_command(f"podman inspect {dep.strip()} --format '{{{{.State.Status}}}}'")
                        deps_status.append(f"{dep.strip()}: {'✓' if dep_result and 'running' in dep_result.stdout else '✗'}")
                
                # Status styling
                status_style = "[green]✓ running" if status == "running" else "[red]✗ " + status
                health_style = {
                    "healthy": "[green]✓ healthy",
                    "unhealthy": f"[red]✗ unhealthy ({failing_streak} fails)",
                    "none": "[yellow]⚠ no health check"
                }.get(health, "[yellow]⚠ unknown")
            else:
                status_style = "[red]✗ not found"
                health_style = "[red]✗ not running"
                deps_status = []

            table.add_row(
                group,
                service_name,
                status_style,
                health_style,
                ", ".join(deps_status) if deps_status else "none"
            )

        console.print(table)

    def init_volumes(self):
        """Initialize all required volumes"""
        volumes = self.compose_config.get('volumes', {}).keys()
        
        with Progress() as progress:
            task = progress.add_task("[cyan]Creating volumes...", total=len(volumes))
            
            for volume in volumes:
                # Check if volume exists first
                result = self.run_command(f"podman volume inspect {volume}", show_output=False)
                if not result:
                    # Create volume if it doesn't exist
                    create_result = self.run_command(f"podman volume create {volume}", show_output=False)
                    if not create_result:
                        console.print(f"[red]Failed to create volume {volume}[/red]")
                progress.advance(task)

    def copy_configs(self):
        """Copy configuration files to volumes"""
        config_volumes = [v for v in self.compose_config.get('volumes', {}).keys() 
                         if v.startswith('w4b_config_')]
        
        with Progress() as progress:
            task = progress.add_task("[cyan]Copying configurations...", total=len(config_volumes))
            
            for volume in config_volumes:
                service = volume.replace('w4b_config_', '')
                src_path = self.config_dir / service
                
                if src_path.exists():
                    # Create a temporary staging directory
                    temp_dir = self.deployment_dir / "temp_config" / service
                    temp_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Copy files to staging directory
                    self.run_command(f"cp -r {src_path}/* {temp_dir}/")
                    
                    # Ensure proper permissions
                    self.run_command(f"chmod -R 755 {temp_dir}")
                    
                    # Create and mount a temporary container to copy files
                    cmd = f"""podman run --rm \
                            -v {volume}:/dest \
                            -v {temp_dir}:/src:ro \
                            alpine sh -c "cp -r /src/* /dest/ && chown -R 1000:1000 /dest/"
                    """
                    self.run_command(cmd)
                    
                    # Cleanup temporary directory
                    self.run_command(f"rm -rf {temp_dir.parent}")
                else:
                    console.print(f"[yellow]Warning: No configuration found for {service}[/yellow]")
                
                progress.advance(task)

    def display_volume_status(self):
        """Display volume status grouped by service"""
        volume_status = self.verify_volumes()
        
        # Group volumes by service prefix
        grouped_volumes = {}
        for vol_name, details in volume_status.items():
            # Split on underscore and take first two parts (e.g., w4b_service)
            parts = vol_name.split('_')
            if len(parts) > 2:
                service = '_'.join(parts[0:2])
                vol_type = '_'.join(parts[2:])
                if service not in grouped_volumes:
                    grouped_volumes[service] = {}
                grouped_volumes[service][vol_type] = details

        table = Table(title="Volume Status by Service")
        table.add_column("Service", style="cyan", no_wrap=True)
        table.add_column("Type", style="yellow")
        table.add_column("Volume Name", style="blue")
        table.add_column("Status", style="green")
        table.add_column("Size", style="magenta")
        
        for service, volumes in grouped_volumes.items():
            first_row = True
            for vol_type, details in volumes.items():
                table.add_row(
                    service if first_row else "",
                    vol_type,
                    details['name'],
                    "[green]✓" if details['exists'] else "[red]✗",
                    details['size']
                )
                first_row = False
        
        console.print(table)

    def start_services(self, services=None, force=False):
        """Start services with dependency resolution"""
        # Initialize volumes
        self.init_volumes()
        
        # Ensure networks exist
        self.init_networks()
        
        # Clean up if needed
        if force:
            self.run_command("podman-compose down -v")
        
        # Build command with project name
        cmd = f"podman-compose -p {self.project_name} -f {self.compose_file}"
        if services:
            # Make sure we use full service names from compose file
            expanded_services = []
            for service in services:
                if service in self.service_metadata['groups']:
                    # If it's a group, get all services in that group
                    expanded_services.extend(
                        s.replace('w4b_', '') 
                        for s in self.service_metadata['groups'][service]['services']
                    )
                else:
                    expanded_services.append(service)
            
            cmd += f" up -d {' '.join(expanded_services)}"
        else:
            cmd += " up -d"
        
        console.print(f"[cyan]Executing: {cmd}[/cyan]")
        return self.run_command(cmd, env=self.env)

    def init_networks(self):
        """Initialize required networks"""
        networks = self.compose_config.get('networks', {})
        for net_name, net_config in networks.items():
            # Use explicit network name if defined, otherwise use compose naming convention
            actual_name = net_config.get('name', f"{self.project_name}_{net_name}")
            
            # Check if network exists
            check = self.run_command(f"podman network inspect {actual_name}", show_output=False)
            if not check:
                # Create network with proper configuration
                cmd = f"podman network create"
                if net_config.get('internal', False):
                    cmd += " --internal"
                if 'ipam' in net_config:
                    ipam = net_config['ipam']['config'][0]
                    if 'subnet' in ipam:
                        cmd += f" --subnet {ipam['subnet']}"
                    if 'gateway' in ipam:
                        cmd += f" --gateway {ipam['gateway']}"
                cmd += f" {actual_name}"
                
                console.print(f"[cyan]Creating network: {actual_name}[/cyan]")
                self.run_command(cmd)

    def logs(self, service):
        """Get logs for a service"""
        # Add w4b_ prefix if not present
        container = f"w4b_{service}" if not service.startswith('w4b_') else service
        return self.run_command(f"podman logs {container}")

    def display_service_overview(self):
        """Display service overview from compose metadata"""
        # Display Groups Table
        groups_table = Table(title="Service Groups")
        groups_table.add_column("Group", style="cyan", no_wrap=True)
        groups_table.add_column("Services", style="yellow")
        groups_table.add_column("Types", style="green")
        
        for group, details in self.service_metadata['groups'].items():
            groups_table.add_row(
                group,
                ", ".join(details['services']),  # Don't modify service names
                ", ".join(sorted(details['types']))
            )
        
        # Display Services Table
        services_table = Table(title="Services")
        services_table.add_column("Service", style="cyan", no_wrap=True)
        services_table.add_column("Group", style="yellow")
        services_table.add_column("Type", style="green")
        services_table.add_column("Description", style="blue")
        services_table.add_column("Dependencies", style="magenta")
        
        for service, details in self.service_metadata['services'].items():
            deps = details['depends_on']
            deps_str = ", ".join(deps) if deps else "none"  # Don't modify dependency names
            
            services_table.add_row(
                service,  # Don't modify service name
                details['group'],
                details['type'],
                details['description'],
                deps_str
            )
        
        console.print("\n")
        console.print(groups_table)
        console.print("\n")
        console.print(services_table)
        console.print("\n")

@click.group(invoke_without_command=True)
@click.version_option(version=VERSION)
@click.pass_context
def cli(ctx):
    """W4B HiveCtl v{} - Management tool for We4Bee server infrastructure""".format(VERSION)
    
    if ctx.invoked_subcommand is None:
        hive = HiveCtl()
        hive.display_service_overview()
        
        # Show available commands
        console.print("\n[bold cyan]Available Commands:[/bold cyan]")
        console.print("  status     - Show service status")
        console.print("  start      - Start services")
        console.print("  stop       - Stop services")
        console.print("  restart    - Restart services")
        console.print("  health     - Show health status")
        console.print("  logs       - Show service logs")
        console.print("  update     - Update services")
        console.print("  networks   - Show network information")
        console.print("  volumes    - List volumes")
        console.print("  config     - Show configuration status")
        console.print("\nUse [cyan]hivectl COMMAND --help[/cyan] for more information about a command.")

@cli.command()
@click.option('--service', help='Specific service to check (e.g., keycloak, monitoring, database)')
def status(service):
    """Show status of all services or a specific service group"""
    hive = HiveCtl()
    containers = hive.get_service_status(service)
    
    if not containers:
        if service:
            console.print(f"\n[yellow]No running containers found for service: {service}[/yellow]")
        else:
            console.print("\n[yellow]No running containers found[/yellow]")
        return

    # Group containers by service
    grouped_containers = {}
    for container in containers:
        name = container['Names'][0].replace('w4b_', '')
        group = CONTAINER_TO_GROUP.get(container['Names'][0], 'other')
        if group not in grouped_containers:
            grouped_containers[group] = []
        grouped_containers[group].append(container)

    # Display grouped status
    for group, group_containers in grouped_containers.items():
        console.print(f"\n[bold cyan]{group.upper()}[/bold cyan]")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Container")
        table.add_column("Status")
        table.add_column("Health")
        table.add_column("Uptime")

        for container in group_containers:
            name = container['Names'][0].replace('w4b_', '')
            status = container['State']
            health = container.get('Health', {}).get('Status', 'N/A')
            uptime = container['StartedAt']

            status_color = "green" if status == "running" else "red"
            health_color = {
                "healthy": "green",
                "unhealthy": "red",
                "N/A": "yellow"
            }.get(health, "yellow")

            table.add_row(
                name,
                f"[{status_color}]{status}[/{status_color}]",
                f"[{health_color}]{health}[/{health_color}]",
                uptime
            )

        console.print(table)

@cli.command()
@click.argument('services', nargs=-1)
@click.option('--force', is_flag=True, help='Force recreation of containers')
def start(services, force):
    """Start services"""
    hive = HiveCtl()
    metadata = hive.service_metadata
    
    # Validate services
    invalid_services = []
    for service in services:
        if service not in metadata['groups'] and \
           service not in metadata['services'] and \
           f"w4b_{service}" not in metadata['services']:
            invalid_services.append(service)
    
    if invalid_services:
        console.print("[yellow]Invalid service or group names:[/yellow]")
        for invalid in invalid_services:
            console.print(f"  - {invalid}")
        console.print("\n[cyan]Available options:[/cyan]")
        console.print("Groups:")
        for group in sorted(metadata['groups']):
            console.print(f"  - {group}")
        console.print("\nServices:")
        for service in sorted(metadata['services']):
            console.print(f"  - {service}")
        return
    
    # Use the new start_services method
    if hive.start_services(services, force):
        console.print("[green]Services started successfully[/green]")
        time.sleep(2)  # Give services time to initialize
        status(None)
    else:
        console.print("[red]Failed to start services[/red]")

@cli.command()
@click.argument('services', nargs=-1)
def stop(services):
    """Stop services"""
    hive = HiveCtl()
    cmd = "podman-compose down"
    
    if services:
        cmd += f" {' '.join(services)}"
        
    with Progress() as progress:
        task = progress.add_task("[yellow]Stopping services...", total=100)
        success = hive.run_command(cmd, capture_output=False)
        progress.update(task, completed=100)
    
    if success:
        console.print("[green]Services stopped successfully[/green]")
    else:
        console.print("[red]Failed to stop services[/red]")

@cli.command()
@click.argument('services', nargs=-1)
def restart(services):
    """Restart services"""
    stop(services)
    time.sleep(2)
    start(services)

@cli.command()
@click.argument('service')
@click.option('--lines', '-n', default=100, help='Number of lines to show')
@click.option('--follow', '-f', is_flag=True, help='Follow log output')
def logs(service, lines, follow):
    """Show service logs"""
    hive = HiveCtl()
    
    # Build the container name
    container = service
    if not service.startswith('hive_') and len(service) != 64:
        container = f"hive_{service}"
    
    cmd_parts = ["podman", "logs"]
    
    if follow:
        cmd_parts.append("-f")
    if lines:
        cmd_parts.extend(["--tail", str(lines)])
    
    cmd_parts.append(container)
    cmd = " ".join(cmd_parts)
    
    try:
        if follow:
            subprocess.run(cmd, shell=True)
        else:
            result = hive.run_command(cmd)
            if result:
                console.print(result.stdout)
    except KeyboardInterrupt:
        pass

@cli.command()
def health():
    """Show health status of all services"""
    hive = HiveCtl()
    hive.display_health_status()

@cli.command()
@click.option('--service', help='Update specific service')
def update(service):
    """Update services"""
    hive = HiveCtl()
    cmd = "podman-compose pull"
    
    if service:
        cmd += f" {service}"
    
    with Progress() as progress:
        task = progress.add_task("[blue]Pulling updates...", total=100)
        success = hive.run_command(cmd, capture_output=False)
        progress.update(task, completed=100)
    
    if success:
        restart(service if service else None)

@cli.command()
def cleanup():
    """Clean up unused resources"""
    hive = HiveCtl()
    steps = [
        ("Removing unused containers", "podman container prune -f"),
        ("Removing unused volumes", "podman volume prune -f"),
        ("Removing unused images", "podman image prune -f")
    ]
    
    with Progress() as progress:
        task = progress.add_task("[cyan]Cleaning up...", total=len(steps))
        for description, cmd in steps:
            console.print(f"\n[cyan]{description}...[/cyan]")
            hive.run_command(cmd)
            progress.advance(task)

@cli.command()
@click.argument('service')
def debug(service):
    """Debug a service"""
    hive = HiveCtl()
    container_name = f"hive_{service}"
    
    # Get service information
    info = hive.run_command(f"podman inspect {container_name}")
    if info:
        try:
            data = json.loads(info.stdout)[0]
            console.print(Panel.fit(
                f"[bold cyan]Debug Information for {service}[/bold cyan]\n\n"
                f"Status: {data['State']['Status']}\n"
                f"Health: {data['State'].get('Health', {}).get('Status', 'N/A')}\n"
                f"Created: {data['Created']}\n"
                f"IP: {data['NetworkSettings']['IPAddress']}\n"
                f"Ports: {data['NetworkSettings']['Ports']}\n"
                f"Mounts: {data['Mounts']}"
            ))
        except (json.JSONDecodeError, KeyError) as e:
            console.print(f"[red]Error parsing service information: {str(e)}[/red]")

@cli.command()
@click.option('--full', is_flag=True, help='Show full statistics')
def stats(full):
    """Show resource usage statistics"""
    hive = HiveCtl()
    containers = hive.get_service_status()
    
    table = Table(title="Resource Usage Statistics")
    table.add_column("Service", style="cyan")
    table.add_column("CPU %", style="green")
    table.add_column("Memory Usage", style="blue")
    table.add_column("Network I/O", style="yellow")
    if full:
        table.add_column("Disk I/O", style="magenta")
        table.add_column("Pids", style="red")

    for container in containers:
        name = container['Names'][0].replace('hive_', '')
        stats = json.loads(hive.run_command(f"podman stats --no-stream --format json {name}").stdout)
        if stats:
            stat = stats[0]
            table.add_row(
                name,
                f"{stat['CPU']}",
                f"{stat['MemUsage']}",
                f"↑{stat['NetInput']} ↓{stat['NetOutput']}",
                *([] if not full else [
                    f"R:{stat['BlockInput']} W:{stat['BlockOutput']}",
                    str(stat['PIDs'])
                ])
            )

    console.print(table)

@cli.command()
def networks():
    """Show network information"""
    hive = HiveCtl()
    network_status = hive.verify_networks()
    
    table = Table(title="Network Configuration")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="yellow")
    table.add_column("Subnet", style="green")
    table.add_column("Gateway", style="blue")
    table.add_column("Status", style="magenta")
    
    for name, status in network_status.items():
        config = status['config']
        details = status['details'] or {}
        ipam = config.get('ipam', {}).get('config', [{}])[0]
        
        table.add_row(
            name,
            "Internal" if config['internal'] else "External",
            ipam.get('subnet', 'N/A'),
            ipam.get('gateway', 'N/A'),
            "[green]✓ Active" if status['exists'] else "[red]✗ Missing"
        )
    
    console.print(table)

@cli.command()
def volumes():
    """List all volumes and their usage"""
    hive = HiveCtl()
    hive.display_volume_status()

@cli.command()
@click.option('--verify', is_flag=True, help='Verify configuration files')
def config(verify):
    """Show and verify configuration status"""
    hive = HiveCtl()
    hive.display_config_status(verify)

@cli.command()
@click.argument('service')
def exec(service):
    """Open an interactive shell in a service"""
    hive = HiveCtl()
    cmd = f"podman exec -it hive_{service} /bin/sh"
    subprocess.run(cmd, shell=True)

@cli.command()
def vpn():
    """Show VPN connection status"""
    hive = HiveCtl()
    result = hive.run_command("wg show all dump")
    
    if result:
        table = Table(title="VPN Connections")
        table.add_column("Peer", style="cyan")
        table.add_column("Endpoint", style="green")
        table.add_column("Latest Handshake", style="yellow")
        table.add_column("Transfer", style="blue")
        
        lines = result.stdout.strip().split('\n')
        for line in lines[1:]:  # Skip header
            fields = line.split('\t')
            if len(fields) >= 4:
                table.add_row(
                    fields[0][:8] + "...",  # Truncated peer ID
                    fields[3] or "N/A",
                    fields[4] if len(fields) > 4 else "Never",
                    f"↑{fields[6]}B ↓{fields[5]}B" if len(fields) > 6 else "N/A"
                )
        
        console.print(table)

@cli.command()
@click.option('--force', is_flag=True, help='Force recreation of volumes')
def init(force):
    """Initialize volumes and copy configurations"""
    hive = HiveCtl()
    
    if force:
        console.print("[yellow]Forcing recreation of volumes...[/yellow]")
        # Get list of existing volumes first
        result = hive.run_command("podman volume ls -q")
        if result and result.stdout.strip():
            volumes = result.stdout.strip().split('\n')
            # Remove each volume individually to avoid the "choose" error
            for volume in volumes:
                if volume.startswith('w4b_'):
                    hive.run_command(f"podman volume rm {volume}")
    
    hive.init_volumes()
    
    # Create required config directories if they don't exist
    required_configs = {
        'prometheus': ['prometheus.yml'],
        'grafana': ['grafana.ini', 'provisioning'],
        'keycloak': ['keycloak.conf'],
        'redis': ['redis.conf'],
        'vector': ['vector.yaml'],
        'loki': ['loki-config.yaml'],
        'alertmanager': ['alertmanager.yml']
    }
    
    for service, files in required_configs.items():
        service_dir = hive.config_dir / service
        if not service_dir.exists():
            console.print(f"[yellow]Creating config directory for {service}[/yellow]")
            service_dir.mkdir(parents=True, exist_ok=True)
            
            # Create basic config files if they don't exist
            for file in files:
                config_file = service_dir / file
                if not config_file.exists():
                    if file == 'prometheus.yml':
                        config_file.write_text("""
global:
  scrape_interval: 15s
scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
""")
                    elif file == 'redis.conf':
                        config_file.write_text("port 6379\nbind 127.0.0.1\n")
                    else:
                        config_file.touch()
    
    hive.copy_configs()
    console.print("[green]Initialization complete[/green]")

@cli.command()
@click.argument('group_or_service')
def info(group_or_service):
    """Show detailed information about a service group or service"""
    hive = HiveCtl()
    metadata = hive.service_metadata
    
    # Check if it's a group
    if group_or_service in metadata['groups']:
        group = group_or_service
        details = metadata['groups'][group]
        
        console.print(f"\n[bold cyan]Group: {group}[/bold cyan]")
        console.print(f"Types: {', '.join(sorted(details['types']))}")
        console.print("\nServices:")
        
        for service in sorted(details['services']):
            service_details = metadata['services'][service]
            console.print(f"\n  [yellow]{service}[/yellow]")  # Don't modify service name
            console.print(f"  Description: {service_details['description']}")
            console.print(f"  Type: {service_details['type']}")
            if service_details['depends_on']:
                console.print(f"  Depends on: {', '.join(service_details['depends_on'])}")  # Don't modify dependency names
            if service_details['required_by']:
                console.print(f"  Required by: {', '.join(service_details['required_by'])}")  # Don't modify required_by names
    
    # Check if it's a service
    elif f"w4b_{group_or_service}" in metadata['services']:
        service = f"w4b_{group_or_service}"
        details = metadata['services'][service]
        
        console.print(f"\n[bold cyan]Service: {service}[/bold cyan]")  # Don't modify service name
        console.print(f"Group: {details['group']}")
        console.print(f"Type: {details['type']}")
        console.print(f"Description: {details['description']}")
        console.print(f"Priority: {details['priority']}")
        if details['depends_on']:
            console.print(f"Depends on: {', '.join(details['depends_on'])}")  # Don't modify dependency names
        if details['required_by']:
            console.print(f"Required by: {', '.join(details['required_by'])}")  # Don't modify required_by names
    
    else:
        console.print(f"[red]Error: '{group_or_service}' not found in groups or services[/red]")

if __name__ == '__main__':
    cli()