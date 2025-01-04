# /hivectl/hivectl/core/network.py
"""
Network management functionality for HiveCtl.
"""
import json
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

from .exceptions import NetworkError, NetworkNotFound, NetworkOperationError
from .utils import run_command

logger = logging.getLogger('hivectl.network')

@dataclass
class NetworkState:
    """Network state information."""
    name: str
    exists: bool
    subnet: Optional[str] = None
    gateway: Optional[str] = None
    internal: bool = False
    labels: Dict[str, str] = field(default_factory=dict)
    containers: List[str] = field(default_factory=list)
    diagnostics: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}

class NetworkManager:
    """Manages container network operations."""
    
    def __init__(self, compose_config):
        """
        Initialize network manager.
        
        Args:
            compose_config: Parsed compose configuration
        """
        self.compose = compose_config

    def get_network_details(self, network_name: str) -> Optional[Dict]:
        """Get detailed network information from Podman."""
        try:
            cmd = f"podman network inspect {network_name}"
            result = run_command(cmd)
            if result and result.stdout:
                details = json.loads(result.stdout)
                if isinstance(details, list):
                    details = details[0]

                # Get containers connected to this network
                container_cmd = f"podman ps -a --format json --filter network={network_name}"
                container_result = run_command(container_cmd)
                containers = []
                
                if container_result.stdout.strip():
                    try:
                        container_data = json.loads(container_result.stdout)
                        if isinstance(container_data, dict):
                            container_data = [container_data]
                        elif not isinstance(container_data, list):
                            container_data = []
                        containers = [
                            {'Id': c['Id'], 'Name': c['Names'][0] if isinstance(c['Names'], list) else c['Names']}
                            for c in container_data
                        ]
                    except Exception as e:
                        logger.debug(f"Failed to parse container data: {e}")

                # Extract network config
                bridge_plugin = next((p for p in details.get('plugins', []) 
                                    if p.get('type') == 'bridge'), {})
                ipam_config = bridge_plugin.get('ipam', {})
                ranges = ipam_config.get('ranges', [[{}]])[0][0] if ipam_config.get('ranges') else {}

                return {
                    'Name': network_name,
                    'Driver': 'bridge',
                    'Internal': bridge_plugin.get('internal', False),
                    'IPAM': {
                        'Config': [{
                            'Subnet': ranges.get('subnet'),
                            'Gateway': ranges.get('gateway')
                        }]
                    },
                    'Labels': details.get('labels', {}),
                    'Containers': containers
                }
            return None
        except Exception as e:
            logger.debug(f"Failed to get network details for {network_name}: {e}")
            return None

    def get_network_state(self) -> Dict[str, NetworkState]:
        """Get current state of all networks."""
        states = {}
        try:
            # Get all existing networks
            cmd = "podman network ls --format json"
            result = run_command(cmd)
            networks = json.loads(result.stdout) if result.stdout.strip() else []
            if not isinstance(networks, list):
                networks = [networks]

            # Build state map
            for name, config in self.compose.networks.items():
                network_name = config['name']
                existing = next((n for n in networks if n['Name'] == network_name), None)
                
                if existing:
                    details = self.get_network_details(network_name)
                    if details:
                        ipam_config = (details.get('IPAM', {}).get('Config', [{}]) or [{}])[0]
                        states[name] = NetworkState(
                            name=network_name,
                            exists=True,
                            subnet=ipam_config.get('Subnet', 'N/A'),
                            gateway=ipam_config.get('Gateway', 'N/A'),
                            internal=details.get('Internal', False),
                            labels=details.get('Labels', {}),
                            containers=[c['Name'] for c in details.get('Containers', []) if isinstance(c, dict)]
                        )
                    else:
                        states[name] = NetworkState(
                            name=network_name,
                            exists=True,
                            subnet='N/A',
                            internal=config.get('internal', False)
                        )
                else:
                    ipam = config.get('ipam', {}).get('config', [{}])[0]
                    states[name] = NetworkState(
                        name=network_name,
                        exists=False,
                        subnet=ipam.get('subnet', 'N/A'),
                        internal=config.get('internal', False),
                        diagnostics={'status': 'not_created'}
                    )

        except Exception as e:
            logger.error(f"Failed to get network state: {e}")
            states = {
                name: NetworkState(
                    name=config['name'],
                    exists=False,
                    diagnostics={'error': str(e)}
                )
                for name, config in self.compose.networks.items()
            }

        return states

    def validate_networks(self) -> Dict[str, dict]:
        """Validate all required networks exist."""
        validation = {}
        states = self.get_network_state()
        
        for name, state in states.items():
            config = self.compose.networks[name]
            actual_name = config['name']
            
            validation[name] = {
                'exists': state.exists,
                'config': config,
                'details': state.to_dict() if state.exists else None
            }
            
            if state.exists:
                logger.debug(f"Validating network {name}: config_internal={config.get('internal')}, state_internal={state.internal}")
                if config.get('internal', False) != state.internal:
                    validation[name].setdefault('issues', []).append(
                        f"Network internal setting mismatch (config: {config.get('internal')}, actual: {state.internal})"
                    )
                
                ipam_config = config.get('ipam', {}).get('config', [{}])[0]
                if 'subnet' in ipam_config:
                    expected_subnet = ipam_config['subnet']
                    if state.subnet != 'N/A' and state.subnet != expected_subnet:
                        validation[name].setdefault('issues', []).append(
                            f'Subnet mismatch: expected {expected_subnet}, got {state.subnet}'
                        )
            
        return validation

    def create_network(self, config: dict) -> bool:
        """Create a network exactly as specified in compose file."""
        try:
            cmd_parts = ["podman", "network", "create"]
            
            # Add labels
            cmd_parts.extend([
                f"--label=io.podman.compose.project={self.compose.project_name}",
                f"--label=com.docker.compose.project={self.compose.project_name}"
            ])
            
            for key, value in config.get('labels', {}).items():
                cmd_parts.append(f"--label={key}={value}")

            # Add network configuration
            if config.get('internal', False):
                cmd_parts.append("--internal")
            
            cmd_parts.append("--driver=bridge")
            
            # Add IPAM configuration
            ipam = config.get('ipam', {}).get('config', [{}])[0]
            if 'subnet' in ipam:
                cmd_parts.append(f"--subnet={ipam['subnet']}")
            if 'gateway' in ipam:
                cmd_parts.append(f"--gateway={ipam['gateway']}")
            
            # Add network name
            cmd_parts.append(config['name'])
            
            try:
                run_command(" ".join(cmd_parts))
                logger.info(f"Created network {config['name']}")
                return True
                
            except Exception as e:
                if "already being used" in str(e):
                    error_msg = (
                        f"Cannot create network {config['name']} with subnet {ipam.get('subnet')}: "
                        "Subnet is already in use.\n"
                        "Please:\n"
                        "1. Check for conflicts with 'ip addr show'\n"
                        "2. Update the subnet in your compose.yaml\n"
                        "3. Remove conflicting networks if appropriate"
                    )
                    raise NetworkError(error_msg)
                raise
            
        except Exception as e:
            logger.error(f"Failed to create network {config['name']}: {e}")
            raise NetworkOperationError(f"Failed to create network: {e}")

    def remove_network(self, network_name: str) -> bool:
        """Remove a network."""
        try:
            # First disconnect any containers
            try:
                details = self.get_network_details(network_name)
                if details and details.get('Containers'):
                    for cinfo in details['Containers']:
                        container_id = cinfo.get('Id')
                        if container_id:
                            try:
                                run_command(f"podman network disconnect -f {network_name} {container_id}")
                            except Exception as e:
                                logger.warning(f"Failed to disconnect container {container_id}: {e}")
            except Exception as e:
                logger.debug(f"Failed to get network containers: {e}")

            # Remove the network
            run_command(f"podman network rm -f {network_name}")
            logger.info(f"Removed network: {network_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove network {network_name}: {e}")
            return False

    def cleanup_networks(self, force: bool = False) -> Tuple[int, List[Dict[str, str]]]:
        """Clean up networks."""
        removed = []
        try:
            # Get existing networks first
            cmd = "podman network ls --format json"
            result = run_command(cmd)
            networks = json.loads(result.stdout) if result.stdout.strip() else []
            if not isinstance(networks, list):
                networks = [networks]

            project_prefix = f"{self.compose.project_name}_"
            for network in networks:
                name = network.get('Name', '')
                if not name.startswith(project_prefix):
                    continue

                # Get detailed info
                details = self.get_network_details(name)
                if not details:
                    continue

                if force or not details.get('Containers'):
                    try:
                        container_count = len(details['Containers']) if isinstance(details['Containers'], list) else 0
                        logger.info(f"Removing network: {name}")
                        if self.remove_network(name):
                            removed.append({
                                'name': name,
                                'subnet': details.get('IPAM', {}).get('Config', [{}])[0].get('Subnet', 'N/A'),
                                'containers': container_count
                            })
                    except Exception as e:
                        logger.error(f"Failed to remove network {name}: {e}")

            return len(removed), removed

        except Exception as e:
            logger.error(f"Failed to cleanup networks: {e}")
            return 0, []

    def ensure_networks(self, force: bool = False) -> bool:
        """Ensure all required networks exist."""
        success = True
        states = self.get_network_state()
        failed_networks = []

        # Remove networks if forced
        if force:
            for name, state in states.items():
                if state.exists:
                    try:
                        logger.info(f"Force removing network: {state.name}")
                        if not self.remove_network(state.name):
                            success = False
                            failed_networks.append(f"{state.name} (removal failed)")
                    except Exception as e:
                        logger.error(f"Failed to remove network {state.name}: {e}")
                        success = False
                        failed_networks.append(f"{state.name} (removal error: {str(e)})")

        # Create missing networks
        for name, state in states.items():
            if not state.exists:
                try:
                    config = self.compose.networks[name]
                    logger.info(f"Creating network: {state.name}")
                    self.create_network(config)
                except Exception as e:
                    logger.error(f"Failed to create network {state.name}: {e}")
                    success = False
                    failed_networks.append(f"{state.name} (creation failed: {str(e)})")

        if not success:
            raise NetworkError(
                "Network setup failed:\n" + 
                "\n".join(f"- {failure}" for failure in failed_networks)
            )

        return success

    def list_networks(self) -> List[Dict]:
        """List all networks with details."""
        try:
            cmd = "podman network ls --format json"
            result = run_command(cmd)
            
            try:
                networks = json.loads(result.stdout) if result.stdout.strip() else []
                if not isinstance(networks, list):
                    networks = [networks] if networks else []
            except json.JSONDecodeError as e:
                logger.error("Failed to parse network list JSON: %s", e)
                return []

            network_list = []
            for net in networks:
                try:
                    if not net['Name'].startswith(f"{self.compose.project_name}_"):
                        continue
                        
                    details = self.get_network_details(net['Name'])
                    if not details:
                        continue

                    # Simply get container_count from the length of Containers list
                    container_count = details.get('Containers', 0)
                    
                    subnet = 'N/A'
                    internal = False
                    if details:
                        ipam_config = (details.get('IPAM', {}).get('Config', [{}]) or [{}])[0]
                        subnet = ipam_config.get('Subnet', 'N/A')
                        internal = details.get('Internal', False)

                    network_list.append({
                        'name': net['Name'],
                        'exists': True,
                        'subnet': subnet,
                        'internal': internal,
                        'containers': container_count  # This is now an integer
                    })
                    
                except Exception as e:
                    logger.warning(f"Error processing network {net.get('Name', 'unknown')}: {e}")
                    continue

            return network_list

        except Exception as e:
            logger.exception("Failed to list networks")
            return []

    def get_network_containers(self, network_name: str) -> List[str]:
        """
        Get containers connected to a network.
        """
        states = self.get_network_state()
        if network_name in states and states[network_name].exists:
            return states[network_name].containers
        return []

