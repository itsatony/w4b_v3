# /server/w4b_containers/hivectl/hivectl.py

import os
import sys
import time
import click
import subprocess
import json
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
from rich.panel import Panel
from pathlib import Path

console = Console()

class HiveCtl:
    def __init__(self):
        # Get the directory where the script is located
        self.script_dir = Path(__file__).resolve().parent
        # Define paths relative to the deployment directory (one level up)
        self.deployment_dir = self.script_dir.parent
        self.compose_file = self.deployment_dir / "compose.yaml"
        self.config_dir = self.deployment_dir / "config"
        self.data_dir = self.deployment_dir / "data"
        self.scripts_dir = self.deployment_dir / "scripts"

    def run_command(self, cmd, capture_output=True):
        """Run a shell command and handle errors"""
        # Ensure we're in the deployment directory for relative paths
        original_dir = os.getcwd()
        os.chdir(self.deployment_dir)
        try:
            result = subprocess.run(
                cmd, 
                shell=True, 
                capture_output=capture_output,
                text=True
            )
            if result.returncode != 0 and capture_output:
                console.print(f"[red]Error:[/red] {result.stderr}")
                return False
            return result if capture_output else True
        except Exception as e:
            console.print(f"[red]Error executing command:[/red] {str(e)}")
            return False
        finally:
            os.chdir(original_dir)

    def get_service_status(self, service=None):
        """Get status of one or all services"""
        cmd = "podman ps --format json"
        if service:
            cmd += f" --filter name=hive_{service}"
        
        result = self.run_command(cmd)
        if not result:
            return []
        
        try:
            containers = json.loads(result.stdout)
            return containers if isinstance(containers, list) else [containers]
        except json.JSONDecodeError:
            return []

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

@click.group()
@click.version_option(version='1.0.0')
def cli():
    """HiveCtl - Management tool for We4Bee server infrastructure"""
    pass

@cli.command()
@click.option('--service', help='Specific service to check')
def status(service):
    """Show status of all services or a specific service"""
    hive = HiveCtl()
    containers = hive.get_service_status(service)
    
    if containers:
        hive.display_status(containers)
    else:
        console.print("[yellow]No services found running[/yellow]")

@cli.command()
@click.argument('services', nargs=-1)
@click.option('--force', is_flag=True, help='Force recreation of containers')
def start(services, force):
    """Start services"""
    hive = HiveCtl()
    
    # Use absolute path for compose file
    compose_path = hive.compose_file
    
    # Clean up existing containers only if they exist
    containers = hive.run_command("podman container ls -aq")
    if containers and containers.stdout.strip():
        with Progress() as progress:
            task = progress.add_task("[yellow]Stopping existing services...", total=100)
            hive.run_command("podman stop $(podman container ls -aq)", capture_output=False)
            progress.update(task, completed=100)
    
    # Clean up containers and networks
    with Progress() as progress:
        task = progress.add_task("[yellow]Cleaning up...", total=100)
        hive.run_command("podman container rm -f $(podman container ls -aq 2>/dev/null) 2>/dev/null || true", capture_output=False)
        hive.run_command("podman pod rm -f pod_deployment 2>/dev/null || true", capture_output=False)
        progress.update(task, completed=100)
    
    # Create networks if they don't exist
    networks = ["frontend", "application", "database", "monitoring", "vpn"]
    with Progress() as progress:
        task = progress.add_task("[cyan]Setting up networks...", total=len(networks))
        for network in networks:
            exists = hive.run_command(f"podman network inspect {network} 2>/dev/null")
            if not exists:
                hive.run_command(f"podman network create {network}", capture_output=False)
            progress.advance(task)
    
    # Start services
    cmd = f"podman-compose -f {compose_path} up -d"
    if services:
        cmd += f" {' '.join(services)}"
    
    with Progress() as progress:
        task = progress.add_task("[green]Starting services...", total=100)
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                # Update progress based on service startup
                if "Starting" in output:
                    progress.update(task, advance=5)
                elif "Created" in output:
                    progress.update(task, advance=5)
                elif "Started" in output:
                    progress.update(task, advance=5)
        
        return_code = process.wait()
        stderr = process.stderr.read()
        
        if return_code == 0:
            progress.update(task, completed=100)
            console.print("[green]Services started successfully[/green]")
            time.sleep(2)  # Give services time to initialize
            # Show current status
            status(None)
        else:
            console.print("[red]Failed to start services[/red]")
            if stderr:
                console.print(f"[red]Error details:[/red]\n{stderr}")

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
    """Run health checks"""
    hive = HiveCtl()
    script = hive.scripts_dir / "health-check.sh"
    
    if not script.exists():
        console.print("[red]Health check script not found[/red]")
        return
    
    # Make sure script is executable
    os.chmod(script, 0o755)
    
    # Run health check with absolute path
    try:
        subprocess.run([str(script)], check=True)
    except subprocess.CalledProcessError as e:
        if e.returncode == 1:
            console.print("[yellow]System partially degraded[/yellow]")
        else:
            console.print("[red]System unhealthy[/red]")
        sys.exit(e.returncode)

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
    result = hive.run_command("podman volume ls --format json")
    
    if result:
        volumes = json.loads(result.stdout)
        table = Table(title="Volume Information")
        table.add_column("Name", style="cyan")
        table.add_column("Driver", style="green")
        table.add_column("Size", style="yellow")
        table.add_column("Created", style="blue")
        
        for vol in volumes:
            inspect = json.loads(hive.run_command(f"podman volume inspect {vol['name']}").stdout)
            size = hive.run_command(f"du -sh {inspect[0]['Mountpoint']}").stdout.split()[0]
            table.add_row(
                vol['name'],
                vol['driver'],
                size,
                vol['created']
            )
        
        console.print(table)

@cli.command()
def config():
    """Show configuration status"""
    hive = HiveCtl()
    paths = {
        'Compose File': hive.compose_file,
        'Config Directory': hive.config_dir,
        'Data Directory': hive.data_dir,
    }
    
    table = Table(title="Configuration Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Path", style="yellow")
    
    for name, path in paths.items():
        status = "✓ Present" if path.exists() else "✗ Missing"
        style = "green" if path.exists() else "red"
        table.add_row(name, f"[{style}]{status}[/{style}]", str(path))
    
    console.print(table)

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

if __name__ == '__main__':
    cli()