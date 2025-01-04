"""
Compose file parsing and configuration management.
"""
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Set
from .utils import get_compose_path
from .exceptions import ComposeFileNotFound, ComposeParseError

logger = logging.getLogger('hivectl.compose')

class ComposeConfig:
    """Manages compose file parsing and configuration."""

    def __init__(self):
        """Initialize compose configuration."""
        self.path = get_compose_path()
        self.raw_config = self._load_compose_file()
        self.project_name = self.raw_config.get('name', '')
        self.services = {}
        self.groups = {}
        self.volumes = {}
        self.networks = {}
        self._parse_config()

    def _load_compose_file(self) -> dict:
        """Load and parse compose file."""
        try:
            with open(self.path) as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            raise ComposeFileNotFound()
        except yaml.YAMLError as e:
            raise ComposeParseError(f"Failed to parse compose file: {e}")

    def _parse_config(self):
        """Parse compose configuration."""
        services_config = self.raw_config.get('services', {})
        networks_config = self.raw_config.get('networks', {})
        volumes_config = self.raw_config.get('volumes', {})
        
        # First pass: collect basic service info and groups
        for name, config in services_config.items():
            labels = config.get('labels', {})
            
            # Get service metadata from labels
            group = labels.get('hive.w4b.group', 'ungrouped')
            service_type = labels.get('hive.w4b.type', 'service')
            
            # Initialize group if not exists
            if group not in self.groups:
                self.groups[group] = {
                    'services': [],
                    'types': set()
                }
            
            # Add service to group
            self.groups[group]['services'].append(name)
            self.groups[group]['types'].add(service_type)
            
            # Store service config
            self.services[name] = {
                'group': group,
                'type': service_type,
                'description': labels.get('hive.w4b.description', ''),
                'priority': int(labels.get('hive.w4b.priority', '50')),
                'depends_on': [],
                'required_by': [],
                'config': config
            }
        
        # Second pass: resolve dependencies
        for name, service in self.services.items():
            labels = services_config[name].get('labels', {})
            
            # Get dependencies from labels
            if 'hive.w4b.depends_on' in labels:
                deps = labels['hive.w4b.depends_on'].split(',')
                service['depends_on'] = [d.strip() for d in deps if d.strip()]
                
            if 'hive.w4b.required_by' in labels:
                reqs = labels['hive.w4b.required_by'].split(',')
                service['required_by'] = [r.strip() for r in reqs if r.strip()]
            
            # Add compose file dependencies
            if 'depends_on' in services_config[name]:
                compose_deps = services_config[name]['depends_on']
                if isinstance(compose_deps, list):
                    service['depends_on'].extend(compose_deps)
                elif isinstance(compose_deps, dict):
                    service['depends_on'].extend(compose_deps.keys())

        # Sort group services and convert types to list
        for group in self.groups.values():
            group['services'].sort()
            group['types'] = sorted(list(group['types']))

        # Parse networks
        for name, config in networks_config.items():
            network_name = config.get('name', f"{self.project_name}_{name}")
            parsed_config = {
                'name': network_name,
                'driver': config.get('driver', 'bridge'),
                'internal': bool(config.get('internal', False)),  # Ensure boolean
                'ipam': config.get('ipam', {}),
                'labels': config.get('labels', {}),
                'config': config
            }
            self.networks[name] = parsed_config
            logger.debug(f"Parsed network {name}: internal={parsed_config['internal']}")

        # Parse volumes with service grouping
        volumes_config = self.raw_config.get('volumes', {})
        for name, config in volumes_config.items():
            if not isinstance(config, dict):
                config = {}  # Handle empty volume definitions
            
            volume_name = name
            if not volume_name.startswith(f"{self.project_name}_"):
                volume_name = f"{self.project_name}_{name}"
                
            # Group volumes by service
            service_name = next(
                (svc for svc in self.services.keys() if name.startswith(f"{self.project_name}_{svc}")),
                "w4b"  # Default service group
            )
            
            if service_name not in self.volumes:
                self.volumes[service_name] = {}
                
            self.volumes[service_name][name] = {
                'name': volume_name,
                'driver': config.get('driver', 'local'),
                'config': config
            }

        logger.debug(f"Parsed {len(self.services)} services, {len(self.networks)} networks, {len(self.volumes)} volumes")
        logger.debug(f"Groups: {list(self.groups.keys())}")