# /hivectl/hivectl.py
#!/usr/bin/env python3
"""
HiveCtl - Management tool for containerized infrastructure.
"""
import sys
import time
import logging
from pathlib import Path
from typing import Optional, List, Tuple

import click
from rich.console import Console
from rich.table import Table

from rich.console import Console, Group, Text
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress

from hivectl.core.compose import ComposeConfig
from hivectl.core.container import ContainerManager
from hivectl.core.network import NetworkManager
from hivectl.core.volume import VolumeManager
from hivectl.core.exceptions import HiveCtlError, ComposeFileNotFound
from hivectl.core.utils import setup_logging
from hivectl.ui.console import ConsoleUI

VERSION = "2.0.0"
console = Console()
ui = ConsoleUI()
logger = logging.getLogger(__name__)

class HiveCtl:
    """Main HiveCtl application class."""
    
    def __init__(self):
        """Initialize HiveCtl with all required managers."""
        try:
            self.compose = ComposeConfig()
            self.network = NetworkManager(self.compose)
            self.container = ContainerManager(self.compose, self.network)
            self.volume = VolumeManager(self.compose)
        except ComposeFileNotFound:
            ui.print_error(ComposeFileNotFound())
            sys.exit(1)
        except Exception as e:
            ui.print_error(e, show_traceback=True)
            sys.exit(1)

def get_hivectl() -> HiveCtl:
    """Get HiveCtl instance with error handling."""
    try:
        return HiveCtl()
    except Exception as e:
        ui.print_error(e)
        sys.exit(1)

# CLI Commands
@click.group(invoke_without_command=True)
@click.version_option(version=VERSION)
@click.option('--debug', is_flag=True, help='Enable debug logging')
@click.pass_context
def cli(ctx, debug):
    """HiveCtl - Management tool for containerized infrastructure"""
    # Initialize logging with debug flag
    setup_logging(debug)
    
    # Store debug setting in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj['DEBUG'] = debug
    
    if debug:
        logger.debug("Debug mode enabled")
        logger.debug(f"Current working directory: {Path.cwd()}")
    
    # Always show compose file info
    compose_path = Path.cwd() / 'compose.yaml'
    logger.info(f"Using compose file: {compose_path}")
    
    if ctx.invoked_subcommand is None:
        try:
            hive = get_hivectl()
            # Display service overview
            ui.display_service_overview(
                hive.compose.groups,
                hive.compose.services
            )
            # Show available commands with improved formatting
            ui.display_commands(COMMANDS)
        except Exception as e:
            ui.print_error(e)
            sys.exit(1)

@cli.command()
@click.option('--service', help='Show status for specific service or group')
@click.option('--health', is_flag=True, help='Include health check information')
def status(service: Optional[str], health: bool):
    """Show status of services"""
    hive = get_hivectl()
    try:
        if health:
            services = hive.container.get_container_status(service)
            ui.display_service_status(services, show_health=True)
        else:
            services = hive.container.get_container_status(service)
            ui.display_service_status(services)
    except Exception as e:
        ui.print_error(e)
        sys.exit(1)

@cli.command()
@click.argument('services', nargs=-1)
@click.option('--force', is_flag=True, help='Force recreation of containers')
@click.option('--skip-running', is_flag=True, help='Skip containers that are already running')
def start(services: Tuple[str], force: bool, skip_running: bool):
    """Start services or service groups"""
    hive = get_hivectl()
    try:
        if services:
            # Resolve and validate services/groups first
            try:
                resolved = hive.container.resolve_services(list(services))
                if resolved:
                    # Show the group resolution info
                    for service in services:
                        group_services = [s for s in resolved if hive.compose.services[s]['group'] == service]
                        if group_services:
                            console.print(f"[blue]Group '{service}'[/blue] resolves to: {', '.join(group_services)}")
                    console.print(f"\n[green]Starting services in order:[/green] {', '.join(resolved)}\n")
            except HiveCtlError as e:
                ui.print_error(e)
                return

            # Check running state if needed
            if not force and not skip_running:
                running = []
                for service in resolved:
                    status = hive.container.get_container_status(service)
                    if status and status[0].state.lower() == 'running':
                        running.append(service)

                if running:
                    message = [
                        "[yellow]These services are already running:[/yellow]"
                    ]
                    for service in running:
                        message.append(f"- {service}")
                    message.extend([
                        "",
                        "[cyan]Options:[/cyan]",
                        f"1. Stop services first: hivectl stop {' '.join(services)}",
                        f"2. Force restart all: hivectl start {' '.join(services)} --force",
                        f"3. Start only stopped services: hivectl start {' '.join(services)} --skip-running"
                    ])
                    console.print("\n".join(message))
                    return

            if skip_running:
                resolved = [s for s in resolved if not any(
                    c.state.lower() == 'running' 
                    for c in hive.container.get_container_status(s)
                )]
                if not resolved:
                    console.print("[green]All specified services are already running[/green]")
                    return

        # Ensure networks exist
        with ui.show_progress("Ensuring networks exist...") as progress:
            task = progress.add_task("Creating networks...", total=1)
            hive.network.ensure_networks()
            progress.update(task, completed=1)
        
        # Ensure volumes exist
        with ui.show_progress("Ensuring volumes exist...") as progress:
            task = progress.add_task("Creating volumes...", total=1)
            hive.volume.ensure_volumes()
            progress.update(task, completed=1)
        
        # Start containers
        with ui.show_progress("Starting services...") as progress:
            task = progress.add_task("Starting...", total=1)
            hive.container.start_containers(list(services) if services else None, force)
            progress.update(task, completed=1)
        
        # Show status after start
        time.sleep(2)  # Brief pause for containers to initialize
        console.print("\n[cyan]Status after start:[/cyan]")
        if services:
            # Get services to display status for
            service_list = resolved if 'resolved' in locals() else list(services)
            service_statuses = []
            for svc in service_list:
                status = hive.container.get_container_status(svc)
                if status:
                    service_statuses.extend(status)
            ui.display_service_status(service_statuses, show_health=True)
        else:
            # Show status for all services
            all_statuses = hive.container.get_container_status()
            ui.display_service_status(all_statuses, show_health=True)
            
    except Exception as e:
        ui.print_error(e)
        sys.exit(1)

@cli.command()
@click.argument('services', nargs=-1)
def stop(services: List[str]):
    """Stop services"""
    hive = get_hivectl()
    try:
        with ui.show_progress("Stopping services...") as progress:
            task = progress.add_task("Stopping...", total=1)
            hive.container.stop_containers(services)
            progress.update(task, completed=1)
    except Exception as e:
        ui.print_error(e)
        sys.exit(1)

@cli.command()
@click.argument('services', nargs=-1)
def restart(services: List[str]):
    """Restart services"""
    hive = get_hivectl()
    try:
        stop(services)
        time.sleep(2)
        start(services)
    except Exception as e:
        ui.print_error(e)
        sys.exit(1)

@cli.command()
def health():
    """Show detailed health status"""
    hive = get_hivectl()
    try:
        health_data = []
        for service in hive.compose.services:
            result = hive.container.check_container_health(service)
            container_status = hive.container.get_container_status(service)[0]
            health_data.append({
                'service': service,
                'status': container_status.state,
                'health_status': result.is_healthy,
                'message': result.message,
                'timestamp': result.timestamp
            })
        ui.display_health_status(health_data)
    except Exception as e:
        ui.print_error(e)
        sys.exit(1)

@cli.command()
@click.argument('service')
@click.option('--lines', '-n', default=100, help='Number of lines to show')
@click.option('--follow', '-f', is_flag=True, help='Follow log output')
def logs(service: str, lines: int, follow: bool):
    """Show service logs"""
    hive = get_hivectl()
    try:
        logs = hive.container.get_container_logs(service, lines, follow)
        if not follow and logs:
            ui.display_logs(logs, service)
    except Exception as e:
        ui.print_error(e)
        sys.exit(1)

@cli.command()
@click.option('--service', help='Show volumes for specific service')
def volumes(service: Optional[str]):
    """Show volume information"""
    hive = get_hivectl()
    try:
        volumes = hive.volume.validate_volumes()
        if service:
            volumes = {service: volumes.get(service, {})}
        ui.display_volume_status(volumes)
    except Exception as e:
        ui.print_error(e)
        sys.exit(1)

@cli.command()
@click.option('--verify', is_flag=True, help='Verify configuration files')
def config(verify: bool):
    """Show configuration status"""
    hive = get_hivectl()
    try:
        config_status = {
            'compose_exists': True,
            'networks': hive.network.validate_networks(),
            'volumes': hive.volume.validate_volumes()
        }
        ui.display_config_tree(config_status)
    except Exception as e:
        ui.print_error(e)
        sys.exit(1)

@cli.command()
@click.option('--all', 'all_resources', is_flag=True, help='Show all resource statistics')
def stats(all_resources: bool):
    """Show resource usage statistics"""
    hive = get_hivectl()
    try:
        resources = []
        for service in hive.compose.services:
            stats = hive.container.get_container_stats(service)
            if stats:
                resources.append(stats[0])
        ui.display_resource_usage(resources)
    except Exception as e:
        ui.print_error(e)
        sys.exit(1)

@cli.command()
@click.argument('service')
def inspect(service: str):
    """Inspect a service"""
    hive = get_hivectl()
    try:
        # Get service details
        config = hive.compose.services.get(service)
        if not config:
            raise click.BadParameter(f"Service {service} not found")
            
        # Show comprehensive service information
        console.print(f"\n[bold cyan]Service: {service}[/bold cyan]")
        console.print(f"Group: {config['group']}")
        console.print(f"Type: {config['type']}")
        console.print(f"Description: {config['description']}")
        console.print(f"Priority: {config['priority']}")
        
        if config['depends_on']:
            console.print(f"Depends on: {', '.join(config['depends_on'])}")
        if config['required_by']:
            console.print(f"Required by: {', '.join(config['required_by'])}")
            
        # Show current status
        status = hive.container.get_container_status(service)
        if status:
            console.print("\n[bold cyan]Current Status:[/bold cyan]")
            ui.display_service_status(status, show_health=True)
            
        # Show resource usage
        stats = hive.container.get_container_stats(service)
        if stats:
            console.print("\n[bold cyan]Resource Usage:[/bold cyan]")
            ui.display_resource_usage([stats[0]])
            
    except Exception as e:
        ui.print_error(e)
        sys.exit(1)

@cli.command()
@click.option('--lines', '-n', default=50, help='Number of lines to show')
def show_logs(lines: int):
    """Show HiveCtl logs"""
    try:
        logger = logging.getLogger('hivectl')
        handler = next((h for h in logger.handlers if isinstance(h, logging.FileHandler)), None)
        if handler:
            with open(handler.baseFilename) as f:
                content = f.readlines()
                # Show last n lines
                for line in content[-lines:]:
                    console.print(line.strip())
    except Exception as e:
        ui.print_error(e)
        sys.exit(1)

@cli.command()
def clear_logs():
    """Clear HiveCtl logs"""
    try:
        logger = logging.getLogger('hivectl')
        handler = next((h for h in logger.handlers if isinstance(h, logging.FileHandler)), None)
        if handler:
            with open(handler.baseFilename, 'w'):
                pass
            console.print("[green]Logs cleared successfully[/green]")
    except Exception as e:
        ui.print_error(e)
        sys.exit(1)

@cli.group()
def network():
    """Network management commands."""
    pass

@network.command(name='list')
def network_list():
    """List all networks and their status."""
    hive = get_hivectl()
    try:
        networks = hive.network.list_networks()
        table = Table(title="Network Status")
        table.add_column("Network", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Subnet", style="yellow")
        table.add_column("Internal", style="blue")
        table.add_column("Containers", style="magenta")
        
        for net in networks:
            status = "[green]✓" if net['exists'] else "[red]✗"
            internal = "Yes" if net.get('internal', False) else "No"
            containers = len(net.get('containers', []))
            
            table.add_row(
                net['name'],
                status,
                net.get('subnet', 'N/A'),
                internal,
                str(containers)
            )
        
        console.print(table)
            
    except Exception as e:
        ui.print_error(e)
        sys.exit(1)

@network.command()
@click.option('--force', is_flag=True, help='Force removal of all networks')
def cleanup(force):
    """Clean up unused or all networks."""
    hive = get_hivectl()
    try:
        if force and not click.confirm("This will remove ALL networks. Continue?"):
            return
            
        count, removed = hive.network.cleanup_networks(force)
        
        if count > 0:
            table = Table(title=f"Removed {count} Networks")
            table.add_column("Network Name", style="cyan")
            
            for name in removed:
                table.add_row(name)
            
            console.print(table)
        else:
            console.print("[yellow]No networks were removed[/yellow]")
            
    except Exception as e:
        ui.print_error(e)
        sys.exit(1)

@network.command()
@click.option('--force', is_flag=True, help='Force recreation of networks')
def create(force):
    """Create required networks."""
    hive = get_hivectl()
    try:
        with Progress() as progress:
            task = progress.add_task("Creating networks...", total=1)
            
            if hive.network.ensure_networks(force):
                progress.update(task, completed=1)
                console.print("[green]Networks created successfully[/green]")
            else:
                progress.update(task, completed=1)
                console.print("[yellow]Some networks could not be created[/yellow]")
                
    except Exception as e:
        ui.print_error(e)
        sys.exit(1)

@network.command()
def prune():
    """Remove unused networks."""
    hive = get_hivectl()
    try:
        count, removed = hive.network.cleanup_networks(force=False)
        
        if count > 0:
            table = Table(title=f"Removed {count} Unused Networks")
            table.add_column("Network Name", style="cyan")
            
            for name in removed:
                table.add_row(name)
            
            console.print(table)
        else:
            console.print("[green]No unused networks found[/green]")
            
    except Exception as e:
        ui.print_error(e)
        sys.exit(1)

# /hivectl/hivectl/hivectl.py

# Command descriptions for help display
COMMANDS = {
    # Service Management
    'status': 'Show service status',
    'start': 'Start services',
    'stop': 'Stop services',
    'restart': 'Restart services',
    'health': 'Show health status',
    'logs': 'Show service logs',
    'inspect': 'Inspect a service',
    
    # Network Management
    'network': {
        'description': 'Network management commands',
        'subcommands': {
            'list': 'List all networks and their status',
            'cleanup': 'Clean up unused or all networks',
            'create': 'Create required networks',
            'prune': 'Remove unused networks'
        }
    },
    
    # Resource Management
    'volumes': 'Show volume information',
    'stats': 'Show resource usage statistics',
    
    # Configuration and System
    'config': 'Show configuration status',
    'show-logs': 'Show HiveCtl logs',
    'clear-logs': 'Clear HiveCtl logs'
}

if __name__ == '__main__':
    cli()