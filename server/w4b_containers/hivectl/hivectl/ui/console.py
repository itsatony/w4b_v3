"""Console UI for HiveCtl."""
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress
from rich.text import Text
import sys
import traceback
from contextlib import contextmanager

class ConsoleUI:
    """UI class for console output."""
    def __init__(self):
        self.console = Console()
        
    def print_error(self, error, show_traceback=False):
        """Print error message."""
        error_text = str(error)
        self.console.print(f"[red]Error:[/red] {error_text}")
        if show_traceback:
            self.console.print_exception()
            
    @contextmanager
    def show_progress(self, title):
        """Show progress indicator."""
        with Progress() as progress:
            yield progress
            
    def display_service_overview(self, groups, services):
        """Display service overview."""
        pass
        
    def display_commands(self, commands):
        """Display available commands."""
        pass
        
    def display_service_status(self, services, show_health=False):
        """Display service status."""
        pass
        
    def display_health_status(self, health_data):
        """Display health status."""
        pass
        
    def display_logs(self, logs, service):
        """Display logs."""
        pass
        
    def display_volume_status(self, volumes):
        """Display volume status."""
        pass
        
    def display_config_tree(self, config_status):
        """Display configuration tree."""
        pass
        
    def display_resource_usage(self, resources):
        """Display resource usage."""
        pass
