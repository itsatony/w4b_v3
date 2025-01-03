# /hivectl/core/container.py
"""
Container management functionality for HiveCtl.
"""
import json
import time
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from .exceptions import (
    ContainerError,
    ContainerNotFound,
    ContainerOperationError,
    HealthCheckError,
    HealthCheckTimeout
)
from .utils import run_command

logger = logging.getLogger('hivectl.container')

@dataclass
class ContainerStatus:
    """Container status information."""
    name: str
    state: str
    health: str
    uptime: str
    memory_usage: str
    cpu_usage: str

@dataclass
class HealthCheckResult:
    """Health check result information."""
    is_healthy: bool
    message: str
    failing_streak: int
    timestamp: float

class ContainerManager:
    """Manages container operations and health checks."""
    
    def __init__(self, compose_config):
        """
        Initialize container manager.
        
        Args:
            compose_config: Parsed compose configuration
        """
        self.compose = compose_config
        self.max_retries = 5
        self.base_delay = 1  # Base delay for exponential backoff

    def get_container_status(self, service_name: Optional[str] = None) -> List[ContainerStatus]:
        """
        Get status of one or all containers.
        
        Args:
            service_name: Specific service to check, or None for all
            
        Returns:
            List of ContainerStatus objects
        """
        cmd = "podman ps --format json"
        if service_name:
            cmd += f" --filter name={service_name}"
            
        try:
            result = run_command(cmd)
            containers = json.loads(result.stdout)
            if not isinstance(containers, list):
                containers = [containers]
                
            return [
                ContainerStatus(
                    name=c['Names'][0],
                    state=c['State'],
                    health=c.get('Health', {}).get('Status', 'N/A'),
                    uptime=c['StartedAt'],
                    memory_usage=c.get('MemUsage', 'N/A'),
                    cpu_usage=c.get('CPUUsage', 'N/A')
                )
                for c in containers
            ]
        except Exception as e:
            logger.error(f"Failed to get container status: {e}")
            raise ContainerError(f"Failed to get container status: {e}")

    def check_container_health(self, service_name: str) -> HealthCheckResult:
        """
        Check health of a container with exponential backoff.
        
        Args:
            service_name: Name of the service to check
            
        Returns:
            HealthCheckResult object
        """
        service_config = self.compose.services.get(service_name)
        if not service_config:
            raise ContainerNotFound(f"Service {service_name} not found")
            
        health_config = service_config.get('health_config')
        if not health_config:
            # No health check configured, consider it healthy
            return HealthCheckResult(True, "No health check configured", 0, time.time())
            
        retries = 0
        while retries < self.max_retries:
            delay = self.base_delay * (2 ** retries)  # Exponential backoff
            
            try:
                result = run_command(
                    f"podman inspect --format '{{{{.State.Health}}}}' {service_name}"
                )
                
                health_data = json.loads(result.stdout)
                status = health_data.get('Status', 'unknown')
                failing_streak = health_data.get('FailingStreak', 0)
                
                if status == 'healthy':
                    return HealthCheckResult(
                        True,
                        "Container is healthy",
                        failing_streak,
                        time.time()
                    )
                elif status == 'starting':
                    logger.info(f"Container {service_name} is starting, waiting {delay}s...")
                    time.sleep(delay)
                    retries += 1
                    continue
                else:
                    return HealthCheckResult(
                        False,
                        f"Container health check failed: {status}",
                        failing_streak,
                        time.time()
                    )
                    
            except Exception as e:
                logger.warning(f"Health check attempt {retries + 1} failed: {e}")
                time.sleep(delay)
                retries += 1
                
        raise HealthCheckTimeout(service_name, self.base_delay * (2 ** self.max_retries))

    def start_containers(self, services: Optional[List[str]] = None, force: bool = False) -> bool:
        """
        Start containers with basic dependency resolution.
        
        Args:
            services: List of services to start, or None for all
            force: Whether to force recreation of containers
            
        Returns:
            bool: Success status
        """
        try:
            cmd_parts = ["podman-compose"]
            
            if self.compose.project_name:
                cmd_parts.extend(["-p", self.compose.project_name])
                
            if force:
                cmd_parts.append("up -d --force-recreate")
            else:
                cmd_parts.append("up -d")
                
            if services:
                # Get dependencies if they exist
                all_services = set()
                for service in services:
                    all_services.add(service)
                    service_config = self.compose.services.get(service)
                    if service_config and service_config['depends_on']:
                        all_services.update(service_config['depends_on'])
                        
                cmd_parts.extend(sorted(all_services))  # Sort for consistent order
                
            cmd = " ".join(cmd_parts)
            run_command(cmd)
            return True
            
        except Exception as e:
            logger.error(f"Failed to start containers: {e}")
            raise ContainerOperationError(f"Failed to start containers: {e}")

    def stop_containers(self, services: Optional[List[str]] = None) -> bool:
        """Stop containers."""
        try:
            cmd = "podman-compose down"
            if services:
                cmd += f" {' '.join(services)}"
            run_command(cmd)
            return True
        except Exception as e:
            logger.error(f"Failed to stop containers: {e}")
            raise ContainerOperationError(f"Failed to stop containers: {e}")

    def restart_containers(self, services: Optional[List[str]] = None) -> bool:
        """Restart containers."""
        self.stop_containers(services)
        time.sleep(2)  # Brief pause between stop and start
        return self.start_containers(services)

    def get_container_logs(self, service_name: str, lines: int = 100, follow: bool = False) -> Optional[str]:
        """
        Get container logs.
        
        Args:
            service_name: Name of the service
            lines: Number of lines to retrieve
            follow: Whether to follow log output
            
        Returns:
            str: Log output if not following, None if following
        """
        cmd_parts = ["podman", "logs"]
        
        if follow:
            cmd_parts.append("-f")
        if lines:
            cmd_parts.extend(["--tail", str(lines)])
            
        cmd_parts.append(service_name)
        cmd = " ".join(cmd_parts)
        
        try:
            if follow:
                # For follow mode, execute directly without capturing output
                run_command(cmd, capture_output=False)
                return None
            else:
                result = run_command(cmd)
                return result.stdout
        except Exception as e:
            logger.error(f"Failed to get container logs: {e}")
            raise ContainerOperationError(f"Failed to get logs: {e}")

    def get_container_stats(self, service_name: Optional[str] = None) -> Dict:
        """
        Get container statistics.
        
        Args:
            service_name: Specific service to check, or None for all
            
        Returns:
            dict: Container statistics
        """
        cmd = "podman stats --no-stream --format json"
        if service_name:
            cmd += f" {service_name}"
            
        try:
            result = run_command(cmd)
            return json.loads(result.stdout)
        except Exception as e:
            logger.error(f"Failed to get container stats: {e}")
            raise ContainerOperationError(f"Failed to get container stats: {e}")