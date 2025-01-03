# /hivectl/hivectl/core/network.py
"""
Network management functionality for HiveCtl.

This module handles all network-related operations including creation,
removal, validation, and diagnostics of container networks.
"""
import json
import logging
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import ipaddress
import yaml

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

@dataclass
class NetworkDiagnostic:
    """Network diagnostic information."""
    name: str
    state: str
    issues: List[str]
    recommendations: List[str]

class NetworkManager:
    """Manages container network operations."""
    
    def __init__(self, compose_config):
        """
        Initialize network manager.
        
        Args:
            compose_config: Parsed compose configuration
        """
        self.compose = compose_config
        self.config_dir = Path(compose_config.compose_path).parent / 'config'
        self._load_network_config()
        
    def _load_network_config(self):
        """Load network configuration from config/networks.yaml if it exists."""
        self.network_config = {
            'alternative_ranges': [
                {'subnet': '172.24.0.0/16', 'mask': 24},
                {'subnet': '172.25.0.0/16', 'mask': 24},
                {'subnet': '172.26.0.0/16', 'mask': 24}
            ],
            'retry_attempts': 3,
            'retry_delay': 2,
            'cleanup_delay': 1
        }
        
        config_file = self.config_dir / 'networks.yaml'
        if config_file.exists():
            try:
                with open(config_file) as f:
                    custom_config = yaml.safe_load(f)
                    if custom_config:
                        self.network_config.update(custom_config)
            except Exception as e:
                logger.warning(f"Failed to load network config: {e}")

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
                    # Get detailed network info
                    detail_cmd = f"podman network inspect {network_name}"
                    try:
                        details = json.loads(run_command(detail_cmd).stdout)[0]
                        ipam = details.get('IPAM', {}).get('Config', [{}])[0]
                        states[name] = NetworkState(
                            name=network_name,
                            exists=True,
                            subnet=ipam.get('Subnet', 'N/A'),
                            gateway=ipam.get('Gateway', 'N/A'),
                            internal=details.get('Internal', False),
                            labels=details.get('Labels', {}),
                            containers=list(details.get('Containers', {}).keys())
                        )
                    except Exception as e:
                        logger.debug(f"Failed to get details for {network_name}: {e}")
                        states[name] = NetworkState(
                            name=network_name,
                            exists=True,
                            diagnostics={'error': str(e)}
                        )
                else:
                    # Include configured subnet in state even if network doesn't exist
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

    def diagnose_networks(self) -> List[NetworkDiagnostic]:
        """
        Perform comprehensive network diagnostics.
        
        Returns:
            List[NetworkDiagnostic]: Diagnostic results for each network
        """
        diagnostics = []
        states = self.get_network_state()
        
        for name, state in states.items():
            issues = []
            recommendations = []
            config = self.compose.networks[name]
            
            # Check existence
            if not state.exists:
                issues.append("Network does not exist")
                recommendations.append("Run 'hivectl network create' to create the network")
            else:
                # Check subnet conflicts
                if state.subnet:
                    try:
                        result = run_command(f"ip addr show | grep '{state.subnet}'")
                        if result.stdout.strip():
                            issues.append(f"Subnet {state.subnet} conflicts with existing network interface")
                            recommendations.append("Consider using an alternative subnet range")
                    except:
                        pass

                # Check configuration matches
                if config.get('internal', False) != state.internal:
                    issues.append("Network internal setting mismatch")
                    recommendations.append("Recreate network with correct settings")

                # Check container connectivity
                for container in state.containers:
                    try:
                        result = run_command(f"podman inspect {container}")
                        details = json.loads(result.stdout)[0]
                        if not details.get('State', {}).get('Running'):
                            issues.append(f"Container {container} is not running")
                    except:
                        issues.append(f"Unable to inspect container {container}")

            diagnostics.append(NetworkDiagnostic(
                name=state.name,
                state="healthy" if not issues else "issues",
                issues=issues,
                recommendations=recommendations
            ))
        
        return diagnostics

    def ensure_networks(self, force: bool = False) -> bool:
        """
        Ensure all required networks exist.
        
        Args:
            force: Whether to force recreation of networks
            
        Returns:
            bool: Success status
        """
        success = True
        states = self.get_network_state()

        # Remove networks if forced
        if force:
            for name, state in states.items():
                if state.exists:
                    try:
                        logger.info(f"Force removing network: {state.name}")
                        if not self.remove_network(state.name):
                            success = False
                        else:
                            state.exists = False
                    except Exception as e:
                        logger.error(f"Failed to remove network {state.name}: {e}")
                        success = False

            # Add delay after cleanup
            time.sleep(self.network_config['cleanup_delay'])

        # Create missing networks
        for name, state in states.items():
            if not state.exists:
                try:
                    config = self.compose.networks[name]
                    logger.info(f"Creating network: {state.name}")
                    if not self.create_network(config):
                        success = False
                except Exception as e:
                    logger.error(f"Failed to create network {state.name}: {e}")
                    success = False

        return success

    def _get_alternative_subnet(self, preferred_subnet: str) -> Optional[Tuple[str, str]]:
        """Get an alternative subnet."""
        used_subnets = set()
        
        # Track subnets we've tried
        if not hasattr(self, '_tried_subnets'):
            self._tried_subnets = set()
        
        # Add preferred subnet to tried list
        self._tried_subnets.add(preferred_subnet)
        
        # Get existing networks' subnets
        try:
            result = run_command("podman network inspect --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}' $(podman network ls -q)")
            if result.stdout.strip():
                used_subnets.update(result.stdout.strip().split())
        except Exception:
            pass

        # Get interfaces' subnets
        try:
            result = run_command("ip -j addr show")
            interfaces = json.loads(result.stdout)
            for iface in interfaces:
                for addr in iface.get('addr_info', []):
                    if 'local' in addr:
                        used_subnets.add(f"{addr['local']}/{addr['prefixlen']}")
        except Exception:
            pass

        # Try alternative ranges
        for range_config in self.network_config['alternative_ranges']:
            try:
                network = ipaddress.ip_network(range_config['subnet'])
                mask = range_config['mask']
                
                for subnet in network.subnets(new_prefix=mask):
                    subnet_str = str(subnet)
                    if subnet_str not in used_subnets and subnet_str not in self._tried_subnets:
                        gateway = str(next(subnet.hosts()))
                        self._tried_subnets.add(subnet_str)
                        return subnet_str, gateway
            except Exception as e:
                logger.debug(f"Failed to process subnet range {range_config}: {e}")
                continue

        return None

    def create_network(self, config: dict) -> bool:
        """Create a network."""
        try:
            # Build basic command
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
            
            # Handle subnet configuration
            ipam = config.get('ipam', {}).get('config', [{}])[0]
            if 'subnet' in ipam:
                # Try original subnet first
                subnet = ipam['subnet']
                gateway = ipam.get('gateway')
                
                max_attempts = self.network_config['retry_attempts']
                for attempt in range(max_attempts):
                    try:
                        if attempt > 0:
                            # Try alternative subnet
                            alternative = self._get_alternative_subnet(subnet)
                            if alternative is None:
                                raise NetworkError("No available subnets found")
                            subnet, gateway = alternative
                            logger.info(f"Trying alternative subnet: {subnet}")

                        cmd = cmd_parts.copy()
                        cmd.extend([
                            f"--subnet={subnet}"
                        ])
                        if gateway:
                            cmd.append(f"--gateway={gateway}")
                        
                        # Add network name last
                        cmd.append(config['name'])
                        
                        run_command(" ".join(cmd))
                        logger.info(f"Created network {config['name']} with subnet {subnet}")
                        return True

                    except Exception as e:
                        if "already being used" in str(e) and attempt < max_attempts - 1:
                            logger.warning(f"Subnet {subnet} in use, will try alternative")
                            time.sleep(self.network_config['retry_delay'])
                            continue
                        elif attempt == max_attempts - 1:
                            raise NetworkError(f"Failed to create network after {max_attempts} attempts: {e}")
                        else:
                            raise

            else:
                # Create network without subnet specification
                cmd_parts.append(config['name'])
                run_command(" ".join(cmd_parts))
                logger.info(f"Created network: {config['name']}")
                return True
            
        except Exception as e:
            logger.error(f"Failed to create network {config['name']}: {e}")
            raise NetworkOperationError(f"Failed to create network: {e}")

        return False

    def remove_network(self, network_name: str) -> bool:
        """
        Remove a network.
        
        Args:
            network_name: Name of the network to remove
            
        Returns:
            bool: Success status
        """
        try:
            # First disconnect any containers
            try:
                inspect = json.loads(run_command(f"podman network inspect {network_name}").stdout)[0]
                if 'Containers' in inspect:
                    for container_id in inspect['Containers'].keys():
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
            result = run_command("podman network ls --format json")
            networks = json.loads(result.stdout) if result.stdout.strip() else []
            if not isinstance(networks, list):
                networks = [networks]

            project_prefix = f"{self.compose.project_name}_"
            for network in networks:
                name = network.get('Name', '')
                if not name.startswith(project_prefix):
                    continue

                # Get detailed info for the network
                try:
                    inspect = json.loads(run_command(f"podman network inspect {name}").stdout)[0]
                    ipam = inspect.get('IPAM', {}).get('Config', [{}])[0]
                    subnet = ipam.get('Subnet', 'N/A')
                except Exception:
                    subnet = 'N/A'

                if force or not network.get('Containers'):  # Remove if forced or unused
                    try:
                        logger.info(f"Removing network: {name}")
                        if self.remove_network(name):
                            removed.append({
                                'name': name,
                                'subnet': subnet,
                                'containers': len(network.get('Containers', {}))
                            })
                    except Exception as e:
                        logger.error(f"Failed to remove network {name}: {e}")

            return len(removed), removed

        except Exception as e:
            logger.error(f"Failed to cleanup networks: {e}")
            return 0, []

    def list_networks(self) -> List[Dict]:
        """
        List all networks with details.
        
        Returns:
            List[Dict]: Network information list
        """
        states = self.get_network_state()
        return [state.to_dict() for state in states.values()]
