#!/usr/bin/env python3
"""
WireGuard VPN Manager for W4B Hive System

This utility helps manage WireGuard VPN configurations for the 
hive server and edge devices.
"""

import os
import sys
import re
import argparse
import subprocess
import ipaddress
import yaml
from pathlib import Path
import inquirer
from datetime import datetime

# Add the repository root to the path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hive_config_manager.utils.security import SecurityUtils
from hive_config_manager.core.manager import HiveManager


class WireGuardManager:
    """
    Manages WireGuard VPN configurations for the W4B system.
    
    Features:
    - Configure server
    - Add/remove clients
    - Assign IP addresses
    - Update client configurations in hive YAML files
    """
    
    def __init__(self, config_path: str = None):
        """
        Initialize the WireGuard manager.
        
        Args:
            config_path: Path to WireGuard config directory, defaults to /etc/wireguard
        """
        self.config_path = Path(config_path or "/etc/wireguard")
        self.server_config_path = self.config_path / "wg0.conf"
        self.hive_manager = HiveManager()
        
        # Default network settings
        self.default_network = {
            'subnet': '10.10.0.0/24',
            'server_ip': '10.10.0.1/24',
            'port': 51820,
            'endpoint': 'vpn.example.com:51820'
        }
    
    def check_requirements(self):
        """Check if WireGuard is installed and the user has proper permissions."""
        try:
            # Check if wireguard is installed
            result = subprocess.run(["which", "wg"], capture_output=True, text=True)
            if result.returncode != 0:
                print("WireGuard is not installed. Please install it first.")
                return False
                
            # Check if user can access the wireguard directory
            if self.config_path.exists() and not os.access(str(self.config_path), os.W_OK):
                print(f"No write permission for {self.config_path}. Try running with sudo.")
                return False
                
            return True
        except Exception as e:
            print(f"Error checking requirements: {str(e)}")
            return False
    
    def initialize_server(self, subnet: str = None, port: int = None):
        """
        Initialize the WireGuard server configuration.
        
        Args:
            subnet: The subnet to use (e.g., 10.10.0.0/24)
            port: The UDP port for the server
        """
        if not self.check_requirements():
            return False
            
        # Create config directory if it doesn't exist
        if not self.config_path.exists():
            try:
                self.config_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"Error creating directory {self.config_path}: {str(e)}")
                return False
        
        # Check if a server config already exists
        if self.server_config_path.exists():
            overwrite = inquirer.prompt([
                inquirer.Confirm('overwrite',
                    message=f"Server configuration already exists at {self.server_config_path}. Overwrite?",
                    default=False)
            ])
            if not overwrite['overwrite']:
                print("Aborting server initialization.")
                return False
        
        # Generate server keys
        keys = SecurityUtils.generate_wireguard_keys()
        
        # Use provided subnet or default
        subnet = subnet or self.default_network['subnet']
        port = port or self.default_network['port']
        
        # Parse subnet to get server IP
        try:
            network = ipaddress.ip_network(subnet)
            server_ip = f"{next(network.hosts())}/{network.prefixlen}"
        except Exception as e:
            print(f"Error parsing subnet {subnet}: {str(e)}")
            return False
        
        # Create server config
        server_config = f"""[Interface]
PrivateKey = {keys['private_key']}
Address = {server_ip}
ListenPort = {port}
SaveConfig = true

# Enable IP forwarding
PostUp = sysctl -w net.ipv4.ip_forward=1
PostUp = iptables -A FORWARD -i %i -j ACCEPT
PostUp = iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT
PostDown = iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE

# Client configurations will be added below
"""
        
        # Write the server config
        try:
            with open(self.server_config_path, 'w') as f:
                f.write(server_config)
            os.chmod(self.server_config_path, 0o600)  # Secure permissions
            
            print(f"Server configuration created at {self.server_config_path}")
            print(f"Server public key: {keys['public_key']}")
            print(f"Using subnet: {subnet}")
            print(f"Server IP: {server_ip}")
            print(f"Server port: {port}")
            
            # Save server info to a metadata file
            metadata = {
                'public_key': keys['public_key'],
                'subnet': subnet,
                'server_ip': server_ip,
                'port': port,
                'created_at': datetime.now().isoformat()
            }
            
            metadata_path = self.config_path / "server_metadata.yaml"
            with open(metadata_path, 'w') as f:
                yaml.dump(metadata, f, default_flow_style=False)
            
            return True
        except Exception as e:
            print(f"Error creating server configuration: {str(e)}")
            return False
    
    def get_server_metadata(self):
        """Get server metadata from the metadata file."""
        metadata_path = self.config_path / "server_metadata.yaml"
        if not metadata_path.exists():
            return None
            
        try:
            with open(metadata_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Error reading server metadata: {str(e)}")
            return None
    
    def get_next_client_ip(self):
        """Get the next available client IP address."""
        metadata = self.get_server_metadata()
        if not metadata:
            print("Server metadata not found. Initialize the server first.")
            return None
            
        # Parse the subnet
        try:
            network = ipaddress.ip_network(metadata['subnet'])
            hosts = list(network.hosts())
            
            # First IP is the server
            hosts.pop(0)
            
            # Get existing client IPs from the server config
            existing_ips = set()
            with open(self.server_config_path, 'r') as f:
                for line in f:
                    if line.strip().startswith("AllowedIPs"):
                        # Extract IP from AllowedIPs line (format: AllowedIPs = x.x.x.x/32)
                        match = re.search(r'AllowedIPs\s*=\s*([0-9\.]+)/32', line)
                        if match:
                            existing_ips.add(match.group(1))
            
            # Find the first available IP
            for host in hosts:
                if str(host) not in existing_ips:
                    return f"{host}/32"
            
            print("No available IP addresses in the subnet.")
            return None
            
        except Exception as e:
            print(f"Error finding next client IP: {str(e)}")
            return None
    
    def add_hive_client(self, hive_id: str, endpoint: str = None):
        """
        Add a hive client to the WireGuard server and update the hive configuration.
        
        Args:
            hive_id: The ID of the hive to add
            endpoint: Optional server endpoint override (IP:port or hostname:port)
        """
        if not self.check_requirements():
            return False
            
        # Check if the server is initialized
        if not self.server_config_path.exists():
            print(f"Server configuration not found at {self.server_config_path}. "
                  "Initialize the server first.")
            return False
        
        # Check if the hive exists
        if hive_id not in self.hive_manager.list_hives():
            print(f"Hive {hive_id} not found.")
            return False
        
        # Get server metadata
        metadata = self.get_server_metadata()
        if not metadata:
            print("Server metadata not found. Initialize the server first.")
            return False
        
        # Get the next available client IP
        client_ip = self.get_next_client_ip()
        if not client_ip:
            return False
        
        # Generate client keys
        keys = SecurityUtils.generate_wireguard_keys()
        
        # Use provided endpoint or construct from metadata
        if not endpoint:
            # Ask for the public endpoint
            endpoint_input = inquirer.prompt([
                inquirer.Text('endpoint',
                    message="Server public endpoint (IP/hostname:port)",
                    default=self.default_network['endpoint'])
            ])
            endpoint = endpoint_input['endpoint']
        
        # Generate client config
        client_config = SecurityUtils.generate_wireguard_config(
            private_key=keys['private_key'],
            server_public_key=metadata['public_key'],
            server_endpoint=endpoint,
            allowed_ips=metadata['subnet'],
            client_ip=client_ip
        )
        
        # Add client to server config
        with open(self.server_config_path, 'a') as f:
            f.write(f"\n# Hive: {hive_id}\n")
            f.write(f"[Peer]\n")
            f.write(f"PublicKey = {keys['public_key']}\n")
            f.write(f"AllowedIPs = {client_ip}\n")
            f.write(f"# Added on {datetime.now().isoformat()}\n")
        
        print(f"Added client {hive_id} to server configuration")
        print(f"Client IP: {client_ip}")
        
        # Update the hive configuration
        credentials = {
            'wireguard': {
                'private_key': keys['private_key'],
                'public_key': keys['public_key'],
                'client_ip': client_ip,
                'config': client_config
            }
        }
        
        try:
            # Get the current hive config
            hive_config = self.hive_manager.get_hive(hive_id)
            
            # Initialize security section if it doesn't exist
            if 'security' not in hive_config:
                hive_config['security'] = {}
            
            # Update the WireGuard configuration
            hive_config['security']['wireguard'] = credentials['wireguard']
            
            # Update the hive
            self.hive_manager.update_hive(hive_id, hive_config)
            
            print(f"Updated WireGuard configuration in hive {hive_id}")
            return True
        except Exception as e:
            print(f"Error updating hive configuration: {str(e)}")
            return False
    
    def remove_client(self, hive_id: str):
        """
        Remove a client from the WireGuard server configuration.
        
        Args:
            hive_id: The ID of the hive to remove
        """
        if not self.check_requirements():
            return False
            
        # Check if the server is initialized
        if not self.server_config_path.exists():
            print(f"Server configuration not found at {self.server_config_path}.")
            return False
        
        # Read the server config
        with open(self.server_config_path, 'r') as f:
            lines = f.readlines()
        
        # Find and remove the client section
        new_lines = []
        skip = False
        removed = False
        
        for i, line in enumerate(lines):
            # Look for the client header comment
            if line.strip() == f"# Hive: {hive_id}":
                skip = True
                removed = True
                continue
            
            # If we're skipping and we reach another peer or the end, stop skipping
            if skip and (i+1 >= len(lines) or lines[i+1].strip() == "[Peer]" or lines[i+1].strip().startswith("# Hive:")):
                skip = False
                continue
            
            # Add the line if we're not skipping
            if not skip:
                new_lines.append(line)
        
        if not removed:
            print(f"Client {hive_id} not found in server configuration.")
            return False
        
        # Write the new config
        with open(self.server_config_path, 'w') as f:
            f.writelines(new_lines)
        
        print(f"Removed client {hive_id} from server configuration.")
        
        # Optionally remove from hive configuration
        try:
            hive_config = self.hive_manager.get_hive(hive_id)
            if 'security' in hive_config and 'wireguard' in hive_config['security']:
                # Don't completely remove, just mark as inactive
                hive_config['security']['wireguard']['active'] = False
                self.hive_manager.update_hive(hive_id, hive_config)
                print(f"Updated hive {hive_id} configuration to mark WireGuard as inactive.")
            
            return True
        except Exception as e:
            print(f"Note: Could not update hive configuration: {str(e)}")
            return True  # Still return true since we removed from server config


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Manage WireGuard VPN for W4B Hive System"
    )
    parser.add_argument('--config-path', help="Path to WireGuard configuration directory")
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Initialize server command
    init_parser = subparsers.add_parser('init-server', help='Initialize WireGuard server')
    init_parser.add_argument('--subnet', help='Subnet to use (e.g., 10.10.0.0/24)')
    init_parser.add_argument('--port', type=int, help='UDP port for the server')
    
    # Add client command
    add_parser = subparsers.add_parser('add-client', help='Add a hive client')
    add_parser.add_argument('hive_id', help='ID of the hive to add')
    add_parser.add_argument('--endpoint', help='Server endpoint (IP:port or hostname:port)')
    
    # Remove client command
    remove_parser = subparsers.add_parser('remove-client', help='Remove a hive client')
    remove_parser.add_argument('hive_id', help='ID of the hive to remove')
    
    # List clients command
    subparsers.add_parser('list-clients', help='List all clients')
    
    args = parser.parse_args()
    manager = WireGuardManager(args.config_path)
    
    if args.command == 'init-server':
        manager.initialize_server(args.subnet, args.port)
    elif args.command == 'add-client':
        manager.add_hive_client(args.hive_id, args.endpoint)
    elif args.command == 'remove-client':
        manager.remove_client(args.hive_id)
    elif args.command == 'list-clients':
        # Read server config and list clients
        if not manager.server_config_path.exists():
            print(f"Server configuration not found at {manager.server_config_path}.")
            return
            
        print("WireGuard Clients:")
        with open(manager.server_config_path, 'r') as f:
            lines = f.readlines()
            
        current_hive = None
        for line in lines:
            line = line.strip()
            if line.startswith("# Hive:"):
                current_hive = line.replace("# Hive:", "").strip()
            elif line.startswith("AllowedIPs") and current_hive:
                ip = line.split("=")[1].strip()
                print(f"  - Hive: {current_hive}, IP: {ip}")
    else:
        # Interactive mode if no command specified
        actions = [
            ('Initialize WireGuard server', 'init-server'),
            ('Add hive client', 'add-client'),
            ('Remove hive client', 'remove-client'),
            ('List clients', 'list-clients'),
            ('Exit', 'exit')
        ]
        
        while True:
            action = inquirer.prompt([
                inquirer.List('command',
                    message="Select an action",
                    choices=[a[0] for a in actions])
            ])
            
            command = next(a[1] for a in actions if a[0] == action['command'])
            
            if command == 'exit':
                break
            elif command == 'init-server':
                subnet = inquirer.prompt([
                    inquirer.Text('subnet',
                        message="Subnet to use",
                        default=manager.default_network['subnet'])
                ])
                port = inquirer.prompt([
                    inquirer.Text('port',
                        message="UDP port for the server",
                        default=str(manager.default_network['port']))
                ])
                manager.initialize_server(subnet['subnet'], int(port['port']))
            elif command == 'add-client':
                hives = manager.hive_manager.list_hives()
                if not hives:
                    print("No hives found. Please create a hive configuration first.")
                    continue
                    
                hive = inquirer.prompt([
                    inquirer.List('id',
                        message="Select a hive to add",
                        choices=hives)
                ])
                endpoint = inquirer.prompt([
                    inquirer.Text('endpoint',
                        message="Server endpoint (IP/hostname:port)",
                        default=manager.default_network['endpoint'])
                ])
                manager.add_hive_client(hive['id'], endpoint['endpoint'])
            elif command == 'remove-client':
                # Interactive client removal
                if not manager.server_config_path.exists():
                    print(f"Server configuration not found at {manager.server_config_path}.")
                    continue
                    
                # Find clients in the server config
                clients = []
                with open(manager.server_config_path, 'r') as f:
                    lines = f.readlines()
                    
                current_hive = None
                for line in lines:
                    line = line.strip()
                    if line.startswith("# Hive:"):
                        current_hive = line.replace("# Hive:", "").strip()
                        clients.append(current_hive)
                
                if not clients:
                    print("No clients found in server configuration.")
                    continue
                    
                client = inquirer.prompt([
                    inquirer.List('id',
                        message="Select a client to remove",
                        choices=clients)
                ])
                manager.remove_client(client['id'])
            elif command == 'list-clients':
                # List clients (same as above)
                if not manager.server_config_path.exists():
                    print(f"Server configuration not found at {manager.server_config_path}.")
                    continue
                    
                print("WireGuard Clients:")
                with open(manager.server_config_path, 'r') as f:
                    lines = f.readlines()
                    
                current_hive = None
                for line in lines:
                    line = line.strip()
                    if line.startswith("# Hive:"):
                        current_hive = line.replace("# Hive:", "").strip()
                    elif line.startswith("AllowedIPs") and current_hive:
                        ip = line.split("=")[1].strip()
                        print(f"  - Hive: {current_hive}, IP: {ip}")


if __name__ == "__main__":
    main()
