"""
Compose file handling for HiveCtl.
"""
import logging
from pathlib import Path
import yaml
from typing import Dict, List, Optional, Set, Tuple

from .exceptions import (
    ComposeFileNotFound,
    InvalidComposeFile,
    MissingLabelsError,
    CircularDependencyError
)
from .utils import validate_label_schema, parse_dependencies

logger = logging.getLogger('hivectl.compose')

class ComposeConfig:
    """
    Handles parsing and validation of the compose file.
    """
    def __init__(self, compose_path: Optional[Path] = None):
        """
        Initialize the compose configuration.
        
        Args:
            compose_path: Path to the compose file. If None, looks in current directory.
        """
        self.compose_path = compose_path or Path.cwd() / 'compose.yaml'
        if not self.compose_path.exists():
            self.compose_path = Path.cwd() / 'compose.yml'
            if not self.compose_path.exists():
                raise ComposeFileNotFound()
                
        self.config = self._load_compose_file()
        self.project_name = self.config.get('name', Path.cwd().name)
        self._validate_compose_file()
        
        # Parse service metadata
        self.services = self._parse_services()
        self.networks = self._parse_networks()
        self.volumes = self._parse_volumes()
        self.groups = self._parse_groups()
        
        logger.info(f"Loaded compose file: {self.compose_path}")
        logger.debug(f"Found {len(self.services)} services in {len(self.groups)} groups")

    def _load_compose_file(self) -> dict:
        """Load and parse the compose file."""
        try:
            with open(self.compose_path) as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse compose file: {e}")
            raise InvalidComposeFile(f"Invalid YAML format: {e}")

    def _validate_compose_file(self):
        """Validate the compose file structure and required sections."""
        required_sections = ['services']
        missing = [section for section in required_sections 
                  if section not in self.config]
        
        if missing:
            raise InvalidComposeFile(
                f"Missing required sections: {', '.join(missing)}"
            )

    def _parse_services(self) -> Dict[str, dict]:
        """Parse service configurations and validate labels."""
        services = {}
        services_config = self.config.get('services', {})
        
        for service_name, service_config in services_config.items():
            # Validate labels
            labels = service_config.get('labels', {})
            is_valid, missing_labels = validate_label_schema(labels, service_name)
            
            if not is_valid:
                raise MissingLabelsError(service_name, missing_labels)
                
            # Parse dependencies
            depends_on = set(service_config.get('depends_on', []))
            label_depends, label_required = parse_dependencies(labels)
            
            # Merge compose and label dependencies
            all_dependencies = depends_on.union(label_depends)
            
            services[service_name] = {
                'config': service_config,
                'group': labels['hive.w4b.group'],
                'type': labels['hive.w4b.type'],
                'description': labels['hive.w4b.description'],
                'priority': int(labels['hive.w4b.priority']),
                'depends_on': list(all_dependencies),
                'required_by': label_required,
                'health_config': service_config.get('healthcheck', {})
            }
            
        return services

    def _parse_networks(self) -> Dict[str, dict]:
        """Parse network configurations."""
        return {
            name: {
                'driver': config.get('driver', 'bridge'),
                'internal': config.get('internal', False),
                'ipam': config.get('ipam', {}),
                'name': config.get('name', f"{self.project_name}_{name}")
            }
            for name, config in self.config.get('networks', {}).items()
        }

    def _parse_volumes(self) -> Dict[str, dict]:
        """Parse volume configurations."""
        volumes = {}
        for name, config in self.config.get('volumes', {}).items():
            # Extract service name from volume name if possible
            parts = name.split('_')
            if len(parts) > 2:
                service = '_'.join(parts[:-1])  # Everything except the last part
                volume_type = parts[-1]  # Last part
            else:
                service = name
                volume_type = 'data'
                
            if service not in volumes:
                volumes[service] = {}
            
            volumes[service][volume_type] = {
                'name': name,
                'config': config
            }
            
        return volumes

    def _parse_groups(self) -> Dict[str, dict]:
        """Parse service groups from labels."""
        groups = {}
        for service_name, service_data in self.services.items():
            group_name = service_data['group']
            
            if group_name not in groups:
                groups[group_name] = {
                    'services': [],
                    'types': set(),
                    'description': f"Services for {group_name}"
                }
                
            groups[group_name]['services'].append(service_name)
            groups[group_name]['types'].add(service_data['type'])
            
        return groups

    def validate_dependencies(self) -> bool:
        """
        Validate service dependencies and check for circular dependencies.
        
        Returns:
            bool: True if dependencies are valid
            
        Raises:
            CircularDependencyError: If circular dependencies are detected
        """
        def check_circular(service: str, stack: Set[str]) -> None:
            if service in stack:
                path = ' -> '.join(list(stack) + [service])
                raise CircularDependencyError(
                    f"Circular dependency detected: {path}"
                )
                
            stack.add(service)
            for dep in self.services[service]['depends_on']:
                if dep in self.services:  # Skip external dependencies
                    check_circular(dep, stack.copy())

        # Check each service
        for service in self.services:
            check_circular(service, set())
            
        return True

    def get_service_order(self) -> List[str]:
        """
        Get services in dependency order for startup/shutdown.
        
        Returns:
            List[str]: Services in correct startup order
        """
        self.validate_dependencies()
        
        # Build dependency graph
        graph = {service: set(data['depends_on']) 
                for service, data in self.services.items()}
                
        # Topological sort
        result = []
        visited = set()
        
        def visit(service: str):
            if service in visited:
                return
            visited.add(service)
            for dep in graph[service]:
                if dep in graph:  # Only visit known services
                    visit(dep)
            result.append(service)
            
        for service in sorted(graph, key=lambda s: self.services[s]['priority']):
            visit(service)
            
        return result

    def get_group_services(self, group: str) -> List[str]:
        """Get all services in a group."""
        return self.groups.get(group, {}).get('services', [])

    def get_service_commands(self, service: str) -> Dict[str, str]:
        """Get the commands configured for a service."""
        service_config = self.services[service]['config']
        return {
            'command': service_config.get('command', ''),
            'entrypoint': service_config.get('entrypoint', '')
        }

    def get_service_environment(self, service: str) -> Dict[str, str]:
        """Get the environment variables for a service."""
        return self.services[service]['config'].get('environment', {})

    def get_service_networks(self, service: str) -> List[str]:
        """Get the networks a service is connected to."""
        return list(self.services[service]['config'].get('networks', {}).keys())

    def get_service_volumes(self, service: str) -> List[str]:
        """Get the volumes mounted to a service."""
        return self.services[service]['config'].get('volumes', [])