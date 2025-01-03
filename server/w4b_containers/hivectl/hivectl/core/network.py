# /hivectl/core/network.py
"""
Network management functionality for HiveCtl.
"""
import json
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

from .exceptions import NetworkError, NetworkNotFound, NetworkOperationError
from .utils import run_command

logger = logging.getLogger('hivectl.network')

@dataclass
class NetworkStatus:
    """Network status information."""
    name: str
    driver: str = "bridge"
    scope: str = "local"
    internal: bool = False
    ipam_config: Dict = None
    containers: List[str] = None

    def __post_init__(self):
        if self.ipam_config is None:
            self.ipam_config = {}
        if self.containers is None:
            self.containers = []

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'name': self.name,
            'driver': self.driver,
            'scope': self.scope,
            'internal': self.internal,
            'ipam_config': self.ipam_config,
            'containers': self.containers
        }

class NetworkManager:
    """Manages container network operations."""
    
    def __init__(self, compose_config):
        """
        Initialize network manager.
        
        Args:
            compose_config: Parsed compose configuration
        """
        self.compose = compose_config

    def get_network_status(self, network_name: Optional[str] = None) -> List[Dict]:
        """Get status of networks."""
        try:
            cmd = "podman network ls --format json"
            result = run_command(cmd)
            
            try:
                networks = json.loads(result.stdout)
                if not isinstance(networks, list):
                    networks = [networks] if networks else []
            except json.JSONDecodeError:
                logger.error(f"Failed to parse network list output: {result.stdout}")
                return []

            status_list = []
            for net in networks:
                if network_name and net.get('Name') != network_name:
                    continue
                
                try:
                    # Get detailed network info
                    detail_cmd = f"podman network inspect {net['Name']}"
                    detail_result = run_command(detail_cmd)
                    details = json.loads(detail_result.stdout)[0]

                    # Create NetworkStatus and immediately convert to dict
                    status_dict = NetworkStatus(
                        name=net.get('Name', 'unknown'),
                        driver=net.get('Driver', 'bridge'),
                        scope=net.get('Scope', 'local'),
                        internal=details.get('Internal', False),
                        ipam_config=details.get('IPAM', {}).get('Config', [{}])[0],
                        containers=list(details.get('Containers', {}).keys())
                    ).to_dict()
                    
                    status_list.append(status_dict)
                except Exception as e:
                    logger.warning(f"Failed to get details for network {net.get('Name')}: {e}")
                    # Add basic network info even if details fail
                    status_dict = NetworkStatus(
                        name=net.get('Name', 'unknown'),
                        driver=net.get('Driver', 'bridge')
                    ).to_dict()
                    status_list.append(status_dict)

            return status_list

        except Exception as e:
            logger.error(f"Failed to get network status: {e}")
            raise NetworkError(f"Failed to get network status: {e}")
 
    def create_network(self, network_name: str, config: dict) -> bool:
        """Create a network if it doesn't exist."""
        try:
            # Check if network exists first
            existing = self.get_network_status(network_name)
            if existing:
                logger.debug(f"Network {network_name} already exists")
                return True

            cmd_parts = ["podman", "network", "create"]
            
            if config.get('internal', False):
                cmd_parts.append("--internal")
                
            ipam = config.get('ipam', {}).get('config', [{}])[0]
            if 'subnet' in ipam:
                cmd_parts.extend(["--subnet", ipam['subnet']])
            if 'gateway' in ipam:
                cmd_parts.extend(["--gateway", ipam['gateway']])
                
            cmd_parts.append(network_name)
            cmd = " ".join(cmd_parts)
            
            run_command(cmd)
            logger.info(f"Created network: {network_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create network {network_name}: {e}")
            raise NetworkOperationError(f"Failed to create network: {e}")

    def remove_network(self, network_name: str) -> bool:
        """Remove a network."""
        try:
            run_command(f"podman network rm {network_name}")
            logger.info(f"Removed network: {network_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove network {network_name}: {e}")
            raise NetworkOperationError(f"Failed to remove network: {e}")

    def ensure_networks(self) -> bool:
        """Ensure all networks defined in compose exist."""
        success = True
        for name, config in self.compose.networks.items():
            try:
                self.create_network(config['name'], config)
            except Exception as e:
                logger.error(f"Failed to ensure network {name}: {e}")
                success = False
        return success

    def validate_networks(self) -> Dict[str, dict]:
        """Validate all required networks exist."""
        validation = {}
        try:
            existing_networks = self.get_network_status()  # This now returns list of dicts
            existing_names = {net['name'] for net in existing_networks}
            
            for name, config in self.compose.networks.items():
                actual_name = config['name']
                network_details = next(
                    (n for n in existing_networks if n['name'] == actual_name),
                    None
                )
                
                validation[name] = {
                    'exists': actual_name in existing_names,
                    'config': config,
                    'details': network_details  # network_details is already a dict
                }

        except Exception as e:
            logger.error(f"Failed to validate networks: {e}")
            # Return empty validation result rather than failing
            validation = {
                name: {
                    'exists': False,
                    'config': config,
                    'details': None
                } for name, config in self.compose.networks.items()
            }

        return validation

    def get_network_containers(self, network_name: str) -> List[str]:

        """
        Get containers connected to a network.
        
        Args:
            network_name: Name of the network
            
        Returns:
            List of container names
        """
        networks = self.get_network_status(network_name)
        if not networks:
            raise NetworkNotFound(f"Network {network_name} not found")
            
        return networks[0].containers