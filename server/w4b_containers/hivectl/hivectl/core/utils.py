"""
Utility functions for HiveCtl.
"""
import os
import sys
import logging
import logging.config
import subprocess
from pathlib import Path
import yaml
from rich.console import Console
from rich.logging import RichHandler
from .exceptions import CommandError, ComposeFileNotFound

console = Console()
logger = logging.getLogger('hivectl')

def setup_logging():
    """Initialize logging configuration."""
    # Set up root logger with default level
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)  # Default to INFO level
    
    # Configure console handler with proper formatting
    console_handler = RichHandler(console=console, show_time=False, show_path=False)
    console_handler.setLevel(logging.INFO)  # Default to INFO level
    root_logger.addHandler(console_handler)
    
    # Configure hivectl logger
    hivectl_logger = logging.getLogger('hivectl')
    hivectl_logger.setLevel(logging.INFO)  # Default to INFO level
    
    # Debug level will be set later if --debug flag is used
    logger.debug("Logging initialized")

def get_log_directory() -> Path:
    """
    Get the appropriate log directory based on environment.
    
    Returns:
        Path: Log directory path
    """
    # Check if we're root - if so, use system path
    if os.geteuid() == 0:
        log_dir = Path('/var/log/hivectl')
    else:
        # Use XDG_STATE_HOME if available, otherwise fall back to ~/.local/state
        xdg_state = os.environ.get('XDG_STATE_HOME')
        if xdg_state:
            base_dir = Path(xdg_state)
        else:
            base_dir = Path.home() / '.local' / 'state'
        log_dir = base_dir / 'hivectl' / 'logs'
    
    return log_dir

def ensure_log_directory(log_dir: Path) -> None:
    """
    Ensure log directory exists with proper permissions.
    
    Args:
        log_dir: Path to log directory
    """
    try:
        # Create directory with parents if it doesn't exist
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Set proper permissions (700 for user directories, 755 for system)
        if os.geteuid() == 0:
            log_dir.chmod(0o755)  # System directory
        else:
            log_dir.chmod(0o700)  # User directory
            
    except Exception as e:
        console.print(f"[red]Error creating log directory {log_dir}:[/red] {str(e)}")
        console.print("[yellow]Falling back to console-only logging[/yellow]")
        return False
    
    return True

def get_compose_path():
    """Get the path to the compose file in the current directory."""
    compose_path = Path.cwd() / 'compose.yaml'
    if not compose_path.exists():
        compose_path = Path.cwd() / 'compose.yml'
        if not compose_path.exists():
            raise ComposeFileNotFound()
    return compose_path

def run_command(cmd, capture_output=True, env=None, show_output=False):
    """
    Execute a shell command with enhanced error handling and logging.
    
    Args:
        cmd (str): Command to execute
        capture_output (bool): Whether to capture command output
        env (dict): Additional environment variables
        show_output (bool): Whether to show output in console
        
    Returns:
        subprocess.CompletedProcess: Process information if capture_output=True
        bool: Success status if capture_output=False
        
    Raises:
        CommandError: If command execution fails
    """
    logger.debug(f"Executing command: {cmd}")
    
    env_dict = os.environ.copy()
    if env:
        env_dict.update(env)
    
    try:
        process = subprocess.run(
            cmd,
            shell=True,
            capture_output=capture_output,
            text=True,
            env=env_dict,
            cwd=Path.cwd()
        )
        
        if process.returncode != 0:
            error_msg = process.stderr.strip() if process.stderr else "Unknown error"
            logger.error(f"Command failed: {error_msg}")
            raise CommandError(cmd, error_msg, process.returncode)
            
        if show_output and process.stdout:
            console.print(process.stdout.strip())
            
        logger.debug(f"Command completed successfully")
        return process if capture_output else True
        
    except subprocess.SubprocessError as e:
        logger.error(f"Failed to execute command: {str(e)}")
        raise CommandError(cmd, str(e))

def format_error(error, detailed=False):
    """Format error messages for display."""
    if detailed:
        return f"[red]Error:[/red] {str(error)}\n[dim]Type: {type(error).__name__}[/dim]"
    return f"[red]Error:[/red] {str(error)}"

def validate_label_schema(labels, service_name):
    """
    Validate that required labels are present and follow the correct schema.
    
    Args:
        labels (dict): Labels to validate
        service_name (str): Name of the service being validated
        
    Returns:
        tuple: (bool, list) - (is_valid, missing_labels)
    """
    required_labels = {
        'hive.w4b.group',
        'hive.w4b.description',
        'hive.w4b.type',
        'hive.w4b.priority'
    }
    
    if not labels:
        return False, list(required_labels)
        
    missing = [label for label in required_labels if label not in labels]
    return len(missing) == 0, missing

def parse_dependencies(labels):
    """
    Parse dependency information from labels.
    
    Args:
        labels (dict): Service labels
        
    Returns:
        tuple: (list, list) - (depends_on, required_by)
    """
    depends_on = labels.get('hive.w4b.depends_on', '').split(',')
    required_by = labels.get('hive.w4b.required_by', '').split(',')
    
    # Clean up empty strings and whitespace
    depends_on = [d.strip() for d in depends_on if d.strip()]
    required_by = [r.strip() for r in required_by if r.strip()]
    
    return depends_on, required_by

def clear_logs():
    """Clear the log files."""
    log_dir = Path(__file__).parent.parent / 'logs'
    try:
        for log_file in log_dir.glob('*.log*'):
            log_file.unlink()
        logger.info("Log files cleared successfully")
    except Exception as e:
        logger.error(f"Failed to clear log files: {e}")
        raise

def show_logs(lines=50):
    """
    Show the most recent log entries.
    
    Args:
        lines (int): Number of lines to show
    """
    log_file = Path(__file__).parent.parent / 'logs' / 'hivectl.log'
    try:
        if not log_file.exists():
            console.print("[yellow]No log file found[/yellow]")
            return
            
        with open(log_file) as f:
            content = f.readlines()
            
        # Get the last n lines
        last_lines = content[-lines:] if lines < len(content) else content
        
        # Print with nice formatting
        for line in last_lines:
            console.print(line.strip())
            
    except Exception as e:
        logger.error(f"Failed to read log file: {e}")
        raise