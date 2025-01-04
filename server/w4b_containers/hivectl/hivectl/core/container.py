# /hivectl/core/container.py
"""
Container management functionality for HiveCtl.
"""
import json
import time
import logging
from typing import List, Dict, Optional, Tuple
from rich.console import Console
from dataclasses import dataclass, field, asdict

from .exceptions import (
    ContainerError,
    ContainerNotFound,
    ContainerOperationError,
    HealthCheckError,
    HealthCheckTimeout,
    HiveCtlError
)
from .utils import run_command

logger = logging.getLogger('hivectl.container')

@dataclass
class ContainerStatus:
    """Container status information."""
    id: str = ""
    name: str = ""
    state: str = "not_found"
    health: str = "N/A"
    uptime: str = "N/A"
    memory_usage: str = "N/A"
    cpu_usage: str = "N/A"
    ports: List[str] = field(default_factory=list)
    networks: List[str] = field(default_factory=list)
    image: str = "N/A"
    group: str = "N/A"  # From compose labels
    service_type: str = "N/A"

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

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
            cmd = "podman ps -a --format json"
            if service_name:
                cmd += f" --filter name={service_name}"
            
            result = run_command(cmd)
            containers = json.loads(result.stdout) if result.stdout.strip() else []
            if not isinstance(containers, list):
                containers = [containers] if containers else []

            status_list = []
            for c in containers:
                try:
                    # Get detailed info
                    inspect_cmd = f"podman inspect {c['Id']}"
                    details = json.loads(run_command(inspect_cmd).stdout)[0]
                    state = details.get('State', {})

                    # Parse health status from healthcheck
                    health_status = 'N/A'
                    if state.get('Healthcheck'):
                        health_status = state['Healthcheck'].get('Status', 'N/A')
                    elif 'Health' in state:
                        health_status = state['Health'].get('Status', 'N/A')
                    elif '(healthy)' in c.get('Status', ''):
                        health_status = 'healthy'
                    elif '(unhealthy)' in c.get('Status', ''):
                        health_status = 'unhealthy'

                    # Parse ports
                    ports = []
                    for port_config in c.get('Ports', []):
                        host_ip = port_config.get('hostIP', '')
                        if not host_ip:
                            host_ip = '0.0.0.0'
                        ports.append(
                            f"{host_ip}:{port_config['hostPort']}->{port_config['containerPort']}/{port_config.get('protocol', 'tcp')}"
                        )

                    # Get networks
                    networks = c.get('Networks', [])
                    if not isinstance(networks, list):
                        networks = [networks] if networks else []

                    # Get labels
                    labels = c.get('Labels', {})
                    group = labels.get('hive.w4b.group', 'N/A')
                    service_type = labels.get('hive.w4b.type', 'N/A')

                    status = ContainerStatus(
                        id=c['Id'][:12],
                        name=c['Names'][0],
                        state=c['State'],
                        health=health_status,
                        uptime=c.get('Status', 'N/A'),
                        ports=ports,
                        networks=networks,
                        image=c['Image'].split(':')[-1],  # Just the tag
                        group=group,
                        service_type=service_type  # Using service_type instead of type
                    )
                    status_list.append(status)

                except Exception as e:
                    logger.warning(f"Failed to get detailed status for container {c['Names'][0]}: {e}")
                    status_list.append(ContainerStatus(
                        id=c['Id'][:12],
                        name=c['Names'][0],
                        state=c['State']
                    ))

            return sorted(status_list, key=lambda x: (x.group, x.name))

        except Exception as e:
            logger.error(f"Failed to get container status: {e}")
            if service_name:
                return [ContainerStatus(name=service_name)]
            return []

    def check_container_health(self, service_name: str) -> Optional[Dict]:
        """Check container health with retries."""
        try:
            # Check if container exists first
            status_list = self.get_container_status(service_name)
            if not status_list:
                logger.debug(f"Container {service_name} not found, skipping health check")
                return {
                    'Status': 'not_found',
                    'FailingStreak': 0,
                    'Message': 'Container not found'
                }
                
            status = status_list[0]  # Get first status
            if status.state == "not_found":
                logger.debug(f"Container {service_name} not found, skipping health check")
                return {
                    'Status': 'not_found',
                    'FailingStreak': 0,
                    'Message': 'Container not found'
                }

            cmd = f"podman inspect --format '{{{{.State.Health}}}}' {service_name}"
            result = run_command(cmd)
            
            try:
                health_data = json.loads(result.stdout)
                return health_data
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
            cmd_parts = ["podman-compose"]
            
            if self.compose.project_name:
                cmd_parts.extend(["-p", self.compose.project_name])
                
            if force:
                cmd_parts.append("up -d --force-recreate")
            else:
                cmd_parts.append("up -d")
                
            if services:
                resolved = self.resolve_services(services)
                if not resolved:
                    raise ContainerError("No valid services found to start")
                    
                logger.debug(f"Starting services in order: {resolved}")
                cmd_parts.extend(resolved)
                
            cmd = " ".join(cmd_parts)
            logger.debug(f"Executing command: {cmd}")
            run_command(cmd)
            return True
            
        except Exception as e:
            logger.error(f"Failed to start containers: {e}")
            raise ContainerOperationError(f"Failed to start containers: {e}")

    def stop_containers(self, services: Optional[List[str]] = None) -> bool:
        """Stop containers in reverse dependency order."""
        try:
            if services:
                resolved = self.resolve_services(services)
                # Reverse the order for stopping
                resolved.reverse()
            else:
                resolved = None
                
            cmd = "podman-compose down"
            if resolved:
                cmd += f" {' '.join(resolved)}"
                
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

    def resolve_services(self, services: List[str]) -> List[str]:
        """
        Resolve service names or groups to a list of service names.
        Takes into account group names and service dependencies.
        
        Args:
            services: List of service or group names
            
        Returns:
            List[str]: Ordered list of service names
        """
        resolved = set()
        
        for name in services:
            # Check if it's a direct service name
            if name in self.compose.services:
                logger.debug(f"Found direct service: {name}")
                resolved.add(name)
                continue
                
            # Check if it's a group name
            group_services = self._get_services_by_group(name)
            if group_services:
                logger.debug(f"Found services for group {name}: {group_services}")
                resolved.update(group_services)
                continue
                
            raise HiveCtlError(f"No service or group found with name: {name}")
            
        if not resolved:
            raise HiveCtlError(f"No services found to start for: {services}")
            
        # Get dependencies for all resolved services
        all_services = set()
        for service in resolved:
            deps = self._get_service_dependencies(service)
            logger.debug(f"Dependencies for {service}: {deps}")
            all_services.update(deps)
            all_services.add(service)
            
        # Return services in dependency order
        ordered = self._order_by_dependencies(list(all_services))
        logger.debug(f"Final ordered service list: {ordered}")
        return ordered

    def _get_services_by_group(self, group: str) -> List[str]:
        """
        Get all services belonging to a group.
        Handles both direct service names and group names from labels.
        """
        logger.debug(f"Looking for services in group: {group}")
        logger.debug(f"Available groups: {list(self.compose.groups.keys())}")
        
        # First check if group exists in our parsed groups
        if group.lower() in (g.lower() for g in self.compose.groups):
            # Find the actual group name with proper case
            actual_group = next(g for g in self.compose.groups.keys() if g.lower() == group.lower())
            services = self.compose.groups[actual_group]['services']
            logger.debug(f"Found services in group {actual_group}: {services}")
            return services
            
        # Fallback to checking labels directly
        services = []
        for service, config in self.compose.services.items():
            service_group = config.get('group', '')
            if service_group.lower() == group.lower():
                services.append(service)
                
        logger.debug(f"Found services by label for group {group}: {services}")
        return services

    def _get_service_dependencies(self, service: str) -> List[str]:
        """Get all dependencies for a service including transitive ones."""
        deps = set()
        service_config = self.compose.services.get(service, {})
        
        # Check declared dependencies in labels
        labels = service_config.get('labels', {})
        for label, value in labels.items():
            if label.endswith('.depends_on') and value:
                deps.update(value.split(','))
                
        # Check compose file dependencies
        if 'depends_on' in service_config:
            deps.update(service_config['depends_on'])
            
        # Get transitive dependencies
        all_deps = deps.copy()
        for dep in deps:
            transitive = self._get_service_dependencies(dep)
            all_deps.update(transitive)
            
        return list(all_deps)

    def _order_by_dependencies(self, services: List[str]) -> List[str]:
        """Order services by dependencies (topological sort)."""
        ordered = []
        seen = set()
        
        def visit(service):
            if service in seen:
                return
            if service not in self.compose.services:
                return
                
            seen.add(service)
            deps = self._get_service_dependencies(service)
            for dep in deps:
                visit(dep)
            ordered.append(service)
            
        for service in services:
            visit(service)
            
        return ordered

