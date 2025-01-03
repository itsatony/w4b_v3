# /hivectl/ui/console.py
"""
Console UI functionality for HiveCtl using Rich library.
"""
import sys
from typing import List, Dict, Any, Optional
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.prompt import Confirm

from hivectl.core.exceptions import HiveCtlError

console = Console()

class ConsoleUI:
    """Handles console output formatting and user interaction."""

    def __init__(self):
        self.console = console

    def print_error(self, error: Exception, show_traceback: bool = False):
        """
        Print an error message with optional traceback.
        
        Args:
            error: Exception to display
            show_traceback: Whether to show full traceback
        """
        if isinstance(error, HiveCtlError):
            self.console.print(f"[red]Error:[/red] {str(error)}")
            if hasattr(error, 'recovery_suggestion') and error.recovery_suggestion:
                self.console.print(f"[yellow]Suggestion:[/yellow] {error.recovery_suggestion}")
        else:
            self.console.print(f"[red]An unexpected error occurred:[/red] {str(error)}")
        
        if show_traceback:
            self.console.print_exception()

    def display_service_overview(self, groups: Dict[str, dict], services: Dict[str, dict]):
        """Display service overview with groups and services."""
        # Groups Table
        groups_table = Table(title="Service Groups", show_header=True, header_style="bold magenta")
        groups_table.add_column("Group", style="cyan", no_wrap=True)
        groups_table.add_column("Services", style="green")
        groups_table.add_column("Types", style="yellow")
        
        for name, details in sorted(groups.items()):
            groups_table.add_row(
                name,
                ", ".join(sorted(details['services'])),
                ", ".join(sorted(details['types']))
            )
        
        # Services Table
        services_table = Table(title="Services", show_header=True, header_style="bold magenta")
        services_table.add_column("Service", style="cyan", no_wrap=True)
        services_table.add_column("Group", style="yellow")
        services_table.add_column("Type", style="green")
        services_table.add_column("Description", style="blue")
        services_table.add_column("Priority", justify="right")
        
        for name, details in sorted(services.items()):
            services_table.add_row(
                name,
                details['group'],
                details['type'],
                details['description'],
                str(details['priority'])
            )
        
        self.console.print(groups_table)
        self.console.print("\n")
        self.console.print(services_table)

    def display_service_status(self, services: List[dict], show_health: bool = True):
        """Display service status information."""
        table = Table(title="Service Status", show_header=True, header_style="bold magenta")
        table.add_column("Service", style="cyan")
        table.add_column("Status", style="green")
        if show_health:
            table.add_column("Health", style="yellow")
        table.add_column("Uptime", style="blue")
        table.add_column("Memory", style="magenta")
        table.add_column("CPU", style="red")
        
        for service in sorted(services, key=lambda s: s['name']):
            row = [
                service['name'],
                self._format_status(service['state']),
            ]
            if show_health:
                row.append(self._format_health(service['health']))
            row.extend([
                service['uptime'],
                service['memory_usage'],
                service['cpu_usage']
            ])
            table.add_row(*row)
        
        self.console.print(table)

    def _format_status(self, status: str) -> str:
        """Format status string with color."""
        colors = {
            'running': 'green',
            'stopped': 'red',
            'restarting': 'yellow',
            'created': 'blue',
            'exited': 'red',
            'paused': 'yellow'
        }
        color = colors.get(status.lower(), 'white')
        return f"[{color}]{status}[/{color}]"

    def _format_health(self, health: str) -> str:
        """Format health string with color."""
        colors = {
            'healthy': 'green',
            'unhealthy': 'red',
            'starting': 'yellow',
            'none': 'blue',
            'N/A': 'white'
        }
        color = colors.get(health.lower(), 'white')
        return f"[{color}]{health}[/{color}]"

    def display_network_status(self, networks: List[dict]):
        """Display network status information."""
        table = Table(title="Network Status", show_header=True, header_style="bold magenta")
        table.add_column("Network", style="cyan")
        table.add_column("Driver", style="yellow")
        table.add_column("Scope", style="green")
        table.add_column("Internal", style="blue")
        table.add_column("Subnet", style="magenta")
        table.add_column("Connected", style="red")
        
        for network in sorted(networks, key=lambda n: n['name']):
            table.add_row(
                network['name'],
                network['driver'],
                network['scope'],
                '✓' if network['internal'] else '✗',
                network['ipam_config'].get('Subnet', 'N/A'),
                str(len(network['containers']))
            )
        
        self.console.print(table)

    def display_volume_status(self, volumes: Dict[str, dict]):
        """Display volume status by service."""
        table = Table(title="Volume Status", show_header=True, header_style="bold magenta")
        table.add_column("Service", style="cyan", no_wrap=True)
        table.add_column("Type", style="yellow")
        table.add_column("Volume", style="green")
        table.add_column("Status", style="blue")
        table.add_column("Size", style="magenta")
        
        for service, service_volumes in sorted(volumes.items()):
            first_row = True
            for vol_type, details in sorted(service_volumes.items()):
                status = "[green]✓" if details['exists'] else "[red]✗"
                size = details.get('details', {}).get('size', 'N/A')
                
                table.add_row(
                    service if first_row else "",
                    vol_type,
                    details['name'],
                    status,
                    size
                )
                first_row = False
        
        self.console.print(table)

    def display_logs(self, logs: str, service: str = None):
        """Display logs with syntax highlighting."""
        title = f"Logs for {service}" if service else "Logs"
        syntax = Syntax(logs, "log", theme="monokai", line_numbers=True)
        self.console.print(Panel(syntax, title=title))

    def display_config_tree(self, config_status: dict):
        """Display configuration status as a tree."""
        tree = Tree("[bold cyan]System Configuration[/bold cyan]")
        
        # Compose File
        compose = tree.add("📄 compose.yaml")
        if config_status['compose_exists']:
            compose.add("[green]✓ Present[/green]")
        else:
            compose.add("[red]✗ Missing[/red]")
        
        # Networks
        networks = tree.add("🌐 Networks")
        for name, status in config_status['networks'].items():
            networks.add(
                f"[{'green' if status['exists'] else 'red'}]{'✓' if status['exists'] else '✗'} "
                f"{name}[/] ({'internal' if status['internal'] else 'external'})"
            )
        
        # Volumes
        volumes = tree.add("📦 Volumes")
        for service, service_volumes in config_status['volumes'].items():
            service_node = volumes.add(f"[blue]{service}[/]")
            for vol_type, details in service_volumes.items():
                service_node.add(
                    f"[{'green' if details['exists'] else 'red'}]{'✓' if details['exists'] else '✗'} "
                    f"{vol_type}[/]"
                )
        
        self.console.print(tree)

    def confirm_action(self, message: str, default: bool = False) -> bool:
        """
        Ask for user confirmation.
        
        Args:
            message: Confirmation message
            default: Default response
            
        Returns:
            bool: User's response
        """
        return Confirm.ask(message, default=default)

    def show_progress(self, message: str):
        """
        Create a progress context.
        
        Args:
            message: Progress message to display
            
        Returns:
            Progress context manager
        """
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        )

    def display_health_status(self, health_data: List[dict]):
        """Display detailed health status information."""
        table = Table(title="Health Status", show_header=True, header_style="bold magenta")
        table.add_column("Service", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Health", style="yellow")
        table.add_column("Last Check", style="blue")
        table.add_column("Details", style="white")
        
        for service in sorted(health_data, key=lambda h: h['service']):
            check_time = datetime.fromtimestamp(service['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            table.add_row(
                service['service'],
                self._format_status(service['status']),
                self._format_health(service['health_status']),
                check_time,
                service.get('message', 'N/A')
            )
        
        self.console.print(table)

    def display_resource_usage(self, resources: List[dict]):
        """Display resource usage information."""
        table = Table(title="Resource Usage", show_header=True, header_style="bold magenta")
        table.add_column("Service", style="cyan")
        table.add_column("Memory", style="green")
        table.add_column("CPU %", style="yellow")
        table.add_column("Net I/O", style="blue")
        table.add_column("Block I/O", style="magenta")
        
        for resource in sorted(resources, key=lambda r: r['name']):
            table.add_row(
                resource['name'],
                self._format_memory(resource['memory']),
                f"{resource['cpu']:.1f}%",
                f"↑{resource['net_in']} ↓{resource['net_out']}",
                f"↑{resource['block_in']} ↓{resource['block_out']}"
            )
        
        self.console.print(table)

    def _format_memory(self, memory: Dict[str, int]) -> str:
        """Format memory usage with color based on utilization."""
        used = memory['used']
        limit = memory['limit']
        percentage = (used / limit) * 100 if limit > 0 else 0
        
        color = 'green'
        if percentage > 90:
            color = 'red'
        elif percentage > 75:
            color = 'yellow'
            
        return f"[{color}]{used}/{limit} MB ({percentage:.1f}%)[/{color}]"

    def display_help(self, commands: Dict[str, str]):
        """Display command help information."""
        table = Table(title="Available Commands", show_header=True, header_style="bold magenta")
        table.add_column("Command", style="cyan")
        table.add_column("Description", style="green")
        
        for command, description in sorted(commands.items()):
            table.add_row(command, description)
        
        self.console.print(table)
        self.console.print("\n[cyan]Use 'hivectl COMMAND --help' for more information about a command.[/cyan]")