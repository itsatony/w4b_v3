# /server/w4b_containers/hivectl/hivectl.py

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

VERSION = "1.1.0"
console = Console()

# Service group definitions with descriptions
SERVICE_GROUPS = {
    'keycloak': {
        'description': 'Authentication and Authorization services (Keycloak + PostgreSQL)',
        'containers': ['w4b_keycloak', 'w4b_postgres_keycloak']
    },
    'monitoring': {
        'description': 'System monitoring stack (Prometheus, Grafana, AlertManager, Blackbox)',
        'containers': ['w4b_prometheus', 'w4b_grafana', 'w4b_alertmanager', 'w4b_blackbox']
    },
    'database': {
        'description': 'Primary data storage services (TimescaleDB, PostgreSQL, Redis)',
        'containers': ['w4b_timescaledb', 'w4b_postgres_app', 'w4b_redis']
    },
    'logging': {
        'description': 'Log aggregation and management (Vector, Loki)',
        'containers': ['w4b_vector', 'w4b_loki']
    },
    'api': {
        'description': 'Core API service for W4B platform',
        'containers': ['w4b_api']
    },
    'vpn': {
        'description': 'VPN service for secure edge device communication (WireGuard)',
        'containers': ['w4b_wireguard']
    }
}

# Reverse mapping for container to service group lookup
CONTAINER_TO_GROUP = {
    container: group
    for group, details in SERVICE_GROUPS.items()
    for container in details['containers']
}

class HiveCtl:
    def __init__(self):
        self.script_dir = Path(__file__).resolve().parent
        self.deployment_dir = self.script_dir.parent
        self.scripts_dir = self.deployment_dir / "scripts"  # Add scripts directory
        self.compose_file = self.deployment_dir / "compose.yaml"
        self.config_dir = self.deployment_dir / "config"
        self.env = self.load_env()
        self.load_compose_config()

    def load_env(self):
        """Load environment variables from .env file"""
        env_path = self.deployment_dir / ".env"
        if env_path.exists():
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
        """Get all containers associated with a service"""
        service = service.lower()
        # Direct container name match
        if service.startswith('w4b_'):
            return [service]
        # Service group match
        if service in SERVICE_GROUPS:
            return SERVICE_GROUPS[service]['containers']
        # Try to find partial matches
        for group, details in SERVICE_GROUPS.items():
            if group.startswith(service):
                return details['containers']
        # Default to prefixed service name if no match found
        return [f'w4b_{service}']

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
        if not service.startswith('w4b_'):
            service = f'w4b_{service}'
        
        return self.compose_config.get('services', {}).get(service, {})

    def verify_config_dirs(self):
        """Verify all required configuration directories exist"""
        required_configs = {
            'prometheus': ['prometheus.yml'],
            'grafana': ['grafana.ini', 'provisioning'],
            'keycloak': ['keycloak.conf'],
            'redis': ['redis.conf'],
            'vector': ['vector.yaml'],
            'loki': ['loki-config.yaml'],
            'alertmanager': ['alertmanager.yml']
        }

        config_status = {}
        for service, files in required_configs.items():
            service_dir = self.config_dir / service
            if not service_dir.exists():
                config_status[service] = False
                continue

            config_status[service] = all(
                (service_dir / file).exists() for file in files
            )

        return config_status

    def verify_volumes(self):
        """Verify all required volumes exist"""
        try:
            volumes = self.compose_config.get('volumes', {}).keys()
            existing_volumes = json.loads(self.run_command("podman volume ls --format json").stdout)
            existing_names = [v['Name'] for v in existing_volumes]
            
            volume_status = {}
            for volume in volumes:
                volume_status[volume] = {
                    'exists': volume in existing_names,
                    'details': next((v for v in existing_volumes if v['Name'] == volume), None)
                }
            
            return volume_status
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
            name = container['Names'][0].replace('hive_', '')
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

    def init_volumes(self):
        """Initialize all required volumes"""
        volumes = self.compose_config.get('volumes', {}).keys()
        
        with Progress() as progress:
            task = progress.add_task("[cyan]Creating volumes...", total=len(volumes))
            
            for volume in volumes:
                result = self.run_command(f"podman volume inspect {volume} 2>/dev/null")
                if not result:
                    self.run_command(f"podman volume create {volume}")
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
        """Display volume status in a table"""
        volume_status = self.verify_volumes()
        
        table = Table(title="Volume Status")
        table.add_column("Volume", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Driver", style="yellow")
        table.add_column("Mount Point", style="blue")
        
        for volume, status in volume_status.items():
            details = status['details'] or {}
            table.add_row(
                volume,
                "[green]✓ Present" if status['exists'] else "[red]✗ Missing",
                details.get('Driver', 'N/A'),
                details.get('Mountpoint', 'N/A')
            )
        
        console.print(table)

    def start_services(self, services=None, force=False):
        """Enhanced service startup with better error handling"""
        # Initialize volumes
        self.init_volumes()
        
        # Clean up if needed
        if force:
            self.run_command("podman-compose down -v")
        
        # Prepare compose command with environment
        env = os.environ.copy()
        env.update(self.env)
        
        cmd = f"podman-compose -f {self.compose_file}"
        if services:
            cmd += f" up -d {' '.join(services)}"
        else:
            cmd += " up -d"
        
        return self.run_command(cmd, env=env)

@click.group(invoke_without_command=True)
@click.version_option(version=VERSION)
@click.pass_context
def cli(ctx):
    """W4B HiveCtl v{} - Management tool for We4Bee server infrastructure""".format(VERSION)
    
    if ctx.invoked_subcommand is None:
        # Create a table for service groups
        table = Table(title=f"W4B HiveCtl v{VERSION} - Service Groups", show_header=True)
        table.add_column("Group", style="cyan", no_wrap=True)
        table.add_column("Description", style="green")
        table.add_column("Containers", style="yellow")

        # Add service groups to table
        for group, details in SERVICE_GROUPS.items():
            table.add_row(
                group.upper(),
                details['description'],
                ", ".join(c.replace('w4b_', '') for c in details['containers'])
            )

        # Print version, table and available commands
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
        console.print("\nService Groups:")
        console.print(table)
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
    
    table = Table(title="System Health Status")
    table.add_column("Service Group", style="cyan")
    table.add_column("Container", style="blue")
    table.add_column("Status", style="green")
    table.add_column("Health", style="yellow")
    table.add_column("Response Time", style="magenta")
    
    # Suppress the error output for container inspection
    with console.status("[cyan]Checking system health...[/cyan]", spinner="dots"):
        for group, details in SERVICE_GROUPS.items():
            first_row = True
            for container in details['containers']:
                # Get container status without showing errors
                result = subprocess.run(
                    f"podman inspect {container} --format '{{{{.State.Status}}}}|{{{{.State.Health.Status}}}}|{{{{.State.Health.FailingStreak}}}}'",
                    shell=True,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    status, health, failing_streak = result.stdout.strip().split('|')
                    
                    # Get response time for web services
                    response_time = "N/A"
                    if container in ['w4b_api', 'w4b_keycloak', 'w4b_grafana']:
                        try:
                            curl_result = subprocess.run(
                                f"curl -sI -w '%{{time_total}}' -o /dev/null localhost:{container_ports.get(container, '80')}",
                                shell=True,
                                capture_output=True,
                                text=True
                            )
                            if curl_result.returncode == 0:
                                response_time = f"{float(curl_result.stdout):.2f}s"
                        except:
                            pass
                    
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
                    response_time = "N/A"
                
                table.add_row(
                    group.title() if first_row else "",
                    container.replace('w4b_', ''),
                    status_style,
                    health_style,
                    response_time
                )
                first_row = False
    
    console.print(table)
    
    # Check overall system health using the table content
    try:
        unhealthy = False
        for row in table.rows:
            if "[red]" in str(row.cells[2]):  # Check Status column
                unhealthy = True
                break
        
        if unhealthy:
            console.print("\n[red]System is degraded - some services are unhealthy[/red]")
        else:
            console.print("\n[green]System is healthy - all services are running normally[/green]")
    except Exception:
        # Fail silently if we can't determine overall health
        pass

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
    result = hive.run_command("podman network ls --format json")
    
    if not result or not result.stdout.strip():
        console.print("[yellow]No networks found[/yellow]")
        return
    
    try:
        networks = json.loads(result.stdout)
        if not networks:
            console.print("[yellow]No networks found[/yellow]")
            return
            
        table = Table(title="Network Configuration")
        table.add_column("Name", style="cyan")
        table.add_column("Driver", style="green")
        table.add_column("Subnet", style="yellow")
        table.add_column("Gateway", style="blue")
        
        # Handle both list and single object responses
        networks = networks if isinstance(networks, list) else [networks]
        
        for net in networks:
            try:
                name = net.get('Name', net.get('name', 'N/A'))
                driver = net.get('Driver', net.get('driver', 'N/A'))
                subnet = net.get('Subnet', net.get('subnet', 'N/A'))
                gateway = net.get('Gateway', net.get('gateway', 'N/A'))
                
                table.add_row(name, driver, subnet, gateway)
            except (KeyError, AttributeError) as e:
                console.print(f"[red]Error processing network entry: {e}[/red]")
                continue
        
        console.print(table)
    except json.JSONDecodeError as e:
        console.print(f"[red]Error parsing network information: {e}[/red]")

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
    
    # Show configuration tree
    tree = Tree("📁 Configuration")
    
    # Add compose file
    compose_node = tree.add("📄 compose.yaml")
    if hive.compose_file.exists():
        compose_node.add("[green]✓ Present")
    else:
        compose_node.add("[red]✗ Missing")

    # Add config directories
    config_node = tree.add("📁 config")
    config_status = hive.verify_config_dirs()
    for service, status in config_status.items():
        if status:
            config_node.add(f"[green]✓ {service}")
        else:
            config_node.add(f"[red]✗ {service}")

    # Add volumes status
    volume_node = tree.add("📦 Volumes")
    volume_status = hive.verify_volumes()
    for volume, status in volume_status.items():
        if status['exists']:
            volume_node.add(f"[green]✓ {volume}")
        else:
            volume_node.add(f"[red]✗ {volume}")

    console.print(tree)

    if verify:
        # Perform deeper configuration verification
        console.print("\n[yellow]Verifying configurations...[/yellow]")
        for service, status in config_status.items():
            if status:
                config_file = hive.config_dir / service / f"{service}.yml"
                if config_file.exists():
                    try:
                        with open(config_file) as f:
                            yaml.safe_load(f)
                        console.print(f"[green]✓ {service} configuration is valid")
                    except yaml.YAMLError as e:
                        console.print(f"[red]✗ {service} configuration is invalid: {e}")

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
        hive.run_command("podman volume rm $(podman volume ls -q)")
    
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

if __name__ == '__main__':
    cli()