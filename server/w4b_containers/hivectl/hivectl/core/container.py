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
    state: str = "not_found"
    health: str = "N/A"
    uptime: str = "N/A"
    memory_usage: str = "N/A"
    cpu_usage: str = "N/A"

@dataclass
class HealthCheckResult:
    """Health check result information."""
    is_healthy: bool
    message: str
    failing_streak: int
    timestamp: float

class ContainerManager:
    """Manages container operations and health checks."""
    
    def __init__(self, compose_config, network_manager=None):
        """Initialize container manager."""
        self.compose = compose_config
        self.max_retries = 5
        self.base_delay = 1
        # Allow network manager to be injected or create new one
        if network_manager is None:
            from .network import NetworkManager
            network_manager = NetworkManager(compose_config)
        self.network_manager = network_manager

    def get_container_status(self, service_name: Optional[str] = None) -> List[ContainerStatus]:
        """Get status of one or all containers."""
        try:
            cmd = "podman ps --format json"
            if service_name:
                cmd += f" --filter name={service_name}"
            
            result = run_command(cmd)
            
            try:
                containers = json.loads(result.stdout)
                if not isinstance(containers, list):
                    containers = [containers] if containers else []
            except json.JSONDecodeError:
                logger.error(f"Failed to parse container list output: {result.stdout}")
                return []

            # If looking for specific service and not found, return empty status
            if service_name and not containers:
                return [ContainerStatus(name=service_name)]

            status_list = []
            for c in containers:
                try:
                    status = ContainerStatus(
                        name=c['Names'][0],
                        state=c['State'],
                        health=c.get('Health', {}).get('Status', 'N/A'),
                        uptime=c['StartedAt'],
                        memory_usage=c.get('MemUsage', 'N/A'),
                        cpu_usage=c.get('CPUUsage', 'N/A')
                    )
                    status_list.append(status)
                except Exception as e:
                    logger.warning(f"Failed to parse container status: {e}")
                    status_list.append(ContainerStatus(name=c.get('Names', ['unknown'])[0]))

            return status_list

        except Exception as e:
            logger.error(f"Failed to get container status: {e}")
            if service_name:
                return [ContainerStatus(name=service_name)]
            return []

    def check_container_health(self, service_name: str) -> Optional[Dict]:
        """Check container health with retries."""
        try:
            # Check if container exists first
            status = self.get_container_status(service_name)
            if not status or status[0].state == "not_found":
                logger.debug(f"Container {service_name} not found, skipping health check")
                return {
                    'Status': 'not_found',
                    'FailingStreak': 0,
                    'Message': 'Container not found'
                }

            cmd = f"podman inspect --format '{{{{.State.Health}}}}' {service_name}"
            result = run_command(cmd)
            
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse health check output: {result.stdout}")
                return {
                    'Status': 'unknown',
                    'FailingStreak': 0,
                    'Message': 'Failed to parse health data'
                }

        except Exception as e:
            logger.error(f"Failed to check container health: {e}")
            return {
                'Status': 'error',
                'FailingStreak': 0,
                'Message': str(e)
            }

    def start_containers(self, services: Optional[List[str]] = None, force: bool = False) -> bool:
        """Start containers with dependency resolution."""
        try:
            # Check networks first
            networks = self.network_manager.list_networks()
            missing_networks = [n for n in networks if not n['exists']]
            if missing_networks:
                logger.info("Setting up required networks...")
                if not self.network_manager.ensure_networks(force=force):
                    if not force:
                        logger.warning("Network setup failed. Try using --force to recreate networks")
                    else:
                        logger.error("Network setup failed even with force option")
                        return False

            # Add small delay to allow network setup to complete
            time.sleep(2)

            # Build podman-compose command
            cmd_parts = ["podman-compose"]
            
            if self.compose.project_name:
                cmd_parts.extend(["-p", self.compose.project_name])
                
            if force:
                cmd_parts.append("up -d --force-recreate")
            else:
                cmd_parts.append("up -d")
                
            if services:
                # Resolve service names from groups
                resolved_services = self.resolve_services(services)
                if not resolved_services:
                    raise ContainerError("No valid services found to start")
                    
                logger.debug(f"Starting services: {resolved_services}")
                cmd_parts.extend(resolved_services)
                
            cmd = " ".join(cmd_parts)
            logger.debug(f"Executing command: {cmd}")
            
            # Execute with retries
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    run_command(cmd)
                    return True
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Start attempt {attempt + 1} failed: {e}")
                        time.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        raise
            
        except Exception as e:
            logger.error(f"Failed to start containers: {e}")
            raise ContainerOperationError(f"Failed to start containers: {e}")

        return False

    def stop_containers(self, services: Optional[List[str]] = None) -> bool:
        """Stop containers."""
        try:
            cmd_parts = ["podman-compose", "down"]
            
            if services:
                # Resolve service names from groups
                resolved_services = self.resolve_services(services)
                if resolved_services:
                    cmd_parts.extend(resolved_services)
                    
            cmd = " ".join(cmd_parts)
            logger.debug(f"Executing command: {cmd}")
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

    def get_container_stats(self, service_name: str) -> Optional[Dict]:
        """Get container statistics."""
        try:
            # Check if container exists first
            status = self.get_container_status(service_name)
            if not status or status[0].state == "not_found":
                logger.debug(f"Container {service_name} not found, skipping stats")
                return None

            cmd = f"podman stats --no-stream --format json {service_name}"
            result = run_command(cmd)
            
            try:
                stats = json.loads(result.stdout)
                return stats[0] if isinstance(stats, list) and stats else None
            except json.JSONDecodeError:
                logger.error(f"Failed to parse container stats output: {result.stdout}")
                return None

        except Exception as e:
            logger.error(f"Failed to get container stats: {e}")
            return None

    def resolve_services(self, services: Optional[List[str]] = None) -> List[str]:
        """
        Resolve service names from group names or service names.
        
        Args:
            services: List of service or group names to resolve
            
        Returns:
            List of actual service names
        """
        if not services:
            return list(self.compose.services.keys())
            
        resolved_services = set()
        for name in services:
            # Check if it's a group name
            if name in self.compose.groups:
                group_services = self.compose.groups[name]['services']
                logger.debug(f"Resolved group {name} to services: {group_services}")
                resolved_services.update(group_services)
            # Check if it's a service name
            elif name in self.compose.services:
                resolved_services.add(name)
            else:
                logger.warning(f"Unknown service or group: {name}")
                raise ContainerError(f"Unknown service or group: {name}")
                
        return list(resolved_services)
