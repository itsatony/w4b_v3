#!/usr/bin/env python3
"""
Hive Configuration Manager
Version: 1.0.0
"""

import os
import sys
import yaml
import inquirer
import subprocess
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import nanoid
import re

# Fix imports for both direct execution and package usage
if __name__ == "__main__":
    # When run directly as a script, use absolute imports
    from core.manager import HiveManager
    from core.exceptions import HiveConfigError, ConfigNotFoundError, ValidationError
    from core.security import SecurityUtils
else:
    # When imported as a module, use relative imports
    from .core.manager import HiveManager
    from .core.exceptions import HiveConfigError, ConfigNotFoundError, ValidationError
    from .core.security import SecurityUtils

class HiveManagerCLI:
    def __init__(self, base_path: str = None):
        self.manager = HiveManager(base_path or os.path.join(os.getcwd(), 'hives'))
        
    def list_hives(self) -> List[str]:
        """List all existing hive configurations"""
        return self.manager.list_hives()
    
    def create_hive(self) -> None:
        """Interactive hive creation process"""
        print("\n=== Creating New Hive Configuration ===\n")
        
        # Define validation functions with correct signatures
        def validate_non_empty(answers, current):
            """Validate that input is not empty"""
            return bool(current.strip())
        
        def validate_latitude(answers, current):
            """Validate latitude is within range -90 to 90"""
            if not current.strip():
                return False
            try:
                lat = float(current)
                return -90 <= lat <= 90
            except ValueError:
                return False
                
        def validate_longitude(answers, current):
            """Validate longitude is within range -180 to 180"""
            if not current.strip():
                return False
            try:
                lon = float(current)
                return -180 <= lon <= 180
            except ValueError:
                return False
        
        # Basic information gathering with validation and defaults
        questions = [
            inquirer.Text('name', 
                          message="Hive name",
                          validate=validate_non_empty),
            inquirer.Text('location', 
                          message="Hive location address",
                          validate=validate_non_empty),
            inquirer.Text('latitude', 
                          message="Latitude (e.g., 48.123456)",
                          validate=validate_latitude,
                          default="48.123456"),
            inquirer.Text('longitude', 
                          message="Longitude (e.g., 11.123456)",
                          validate=validate_longitude,
                          default="11.123456"),
            inquirer.List('timezone',
                         message="Select timezone",
                         choices=['Europe/Berlin', 'Europe/London', 'UTC'],
                         default='Europe/Berlin'),
            inquirer.Text('notes', 
                          message="Hive notes (optional)"),
        ]
        answers = inquirer.prompt(questions)
        
        # Network configuration with validation
        network_type = inquirer.prompt([
            inquirer.List('type',
                         message="Primary network connection",
                         choices=['wifi', 'lan'],
                         default='wifi')
        ])
        
        network_config = {'primary': network_type['type']}
        
        if network_type['type'] == 'wifi':
            wifi_networks = []
            while True:
                add_network = inquirer.prompt([
                    inquirer.Confirm('add', message="Add WiFi network?", default=True)
                ])
                if not add_network['add']:
                    break
                    
                wifi = inquirer.prompt([
                    inquirer.Text('ssid', 
                                  message="WiFi SSID",
                                  validate=validate_non_empty),
                    inquirer.Password('password', 
                                      message="WiFi password",
                                      validate=validate_non_empty),
                    inquirer.Text('priority', 
                                  message="Priority (1=highest)", 
                                  default="1",
                                  validate=lambda answers, current: current.isdigit() and int(current) > 0)
                ])
                wifi_networks.append({
                    'ssid': wifi['ssid'],
                    'password': wifi['password'],
                    'priority': int(wifi['priority'])
                })
            # Ensure at least one WiFi network is configured
            if not wifi_networks:
                print("Warning: No WiFi networks configured. Adding default test network.")
                wifi_networks.append({
                    'ssid': 'default_network',
                    'password': 'change_this_password',
                    'priority': 1
                })
            network_config['wifi'] = wifi_networks
        elif network_type['type'] == 'lan':
            # Add LAN configuration options
            lan_config = {}
            
            # Ask if DHCP should be used
            dhcp = inquirer.prompt([
                inquirer.Confirm('use_dhcp',
                               message="Use DHCP?",
                               default=True)
            ])
            
            lan_config['dhcp'] = dhcp['use_dhcp']
            
            # If not using DHCP, collect static IP information
            if not dhcp['use_dhcp']:
                def validate_ip(answers, current):
                    """Validate IP address format"""
                    import re
                    return bool(re.match(r'^(\d{1,3}\.){3}\d{1,3}$', current))
                
                static_config = inquirer.prompt([
                    inquirer.Text('ip',
                                message="Static IP address",
                                validate=validate_ip),
                    inquirer.Text('gateway',
                                message="Gateway address",
                                validate=validate_ip),
                    inquirer.Text('dns',
                                message="DNS servers (comma-separated)",
                                validate=lambda answers, current: all(validate_ip(answers, ip.strip()) for ip in current.split(',')))
                ])
                
                lan_config['static'] = {
                    'ip': static_config['ip'],
                    'gateway': static_config['gateway'],
                    'dns': [dns.strip() for dns in static_config['dns'].split(',')]
                }
            
            network_config['lan'] = lan_config
        
        # Administrator configuration with validation
        admins = []
        while True:
            add_admin = inquirer.prompt([
                inquirer.Confirm('add', message="Add administrator?", default=True)
            ])
            if not add_admin['add']:
                break
                
            admin = inquirer.prompt([
                inquirer.Text('name', 
                              message="Admin name",
                              validate=validate_non_empty),
                inquirer.Text('email', 
                              message="Admin email",
                              validate=lambda answers, current: bool(re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', current))),
                inquirer.Text('username', 
                              message="Admin username",
                              validate=lambda answers, current: bool(current.strip()) and ' ' not in current),
                inquirer.Text('phone', 
                              message="Admin phone"),
                inquirer.List('role',
                            message="Admin role",
                            choices=['hive_admin', 'hive_viewer'],
                            default='hive_admin')
            ])
            admins.append(admin)
        
        # Ensure at least one admin is configured
        if not admins:
            print("Warning: No administrators configured. Adding default admin.")
            admins.append({
                'name': 'Default Admin',
                'email': 'admin@example.com',
                'username': 'admin',
                'phone': '',
                'role': 'hive_admin'
            })
            
        # Security configuration with validation
        security_config = inquirer.prompt([
            inquirer.Confirm('generate_keys',
                            message="Generate security keys automatically?",
                            default=True),
            inquirer.Text('server_endpoint',
                        message="WireGuard server endpoint (IP:Port)",
                        default="vpn.example.com:51820",
                        validate=lambda answers, current: bool(re.match(r'^[a-zA-Z0-9\.\-]+:\d+$', current)))
        ])
        
        # Generate configuration
        hive_id = self.manager.generate_hive_id()
        config = {
            'hive_id': hive_id,
            'version': '1.0.0',
            'metadata': {
                'name': answers['name'],
                'location': {
                    'address': answers['location'],
                    'latitude': float(answers['latitude']),
                    'longitude': float(answers['longitude']),
                    'timezone': answers['timezone']
                },
                'notes': answers['notes']
            },
            'network': network_config,
            'administrators': admins,
            'collector': {
                'interval': 60,
                'batch_size': 100,
                'retry_attempts': 3,
                'retry_delay': 5,
                'buffer_size': 1000,
                'logging': {
                    'level': 'INFO',
                    'max_size': '100M',
                    'retention': 7
                }
            },
            'sensors': [],  # Empty sensor array to be edited manually
            'maintenance': {
                'backup': {
                    'enabled': True,
                    'interval': 86400,
                    'retention': 7
                },
                'updates': {
                    'auto_update': True,
                    'update_hour': 3,
                    'allowed_days': ['Sunday']
                },
                'monitoring': {
                    'metrics_retention': 30,
                    'enable_detailed_logging': True
                }
            }
        }
        
        try:
            # Create the base hive configuration
            self.manager.create_hive(config)
            
            # Generate security credentials if requested
            if security_config['generate_keys']:
                credentials = self.manager.generate_security_credentials(
                    hive_id, security_config['server_endpoint']
                )
                
                # Apply credentials to the configuration
                self.manager.apply_security_credentials(hive_id, credentials)
                
                # Display the credentials
                self._display_credentials(credentials)
            
            print(f"\nCreated hive configuration: {hive_id}")
            
            # Ask if user wants to edit the configuration
            edit = inquirer.prompt([
                inquirer.Confirm('edit', message="Edit hive configuration now?", default=True)
            ])
            
            if edit['edit']:
                self.edit_hive(hive_id)
                
        except HiveConfigError as e:
            print(f"Error creating hive: {str(e)}")
            return
    
    def _display_credentials(self, credentials: Dict) -> None:
        """Display the generated security credentials"""
        print("\n=== SECURITY CREDENTIALS ===")
        print("KEEP THIS INFORMATION SECURE!")
        
        print("\n--- SSH Keys ---")
        print("Public Key:")
        print(credentials['ssh']['public_key'])
        print("Private Key: [REDACTED - stored in config]")
        
        print("\n--- WireGuard ---")
        print(f"Client IP: {credentials['wireguard']['client_ip']}")
        print(f"Public Key: {credentials['wireguard']['public_key']}")
        print("Private Key: [REDACTED - stored in config]")
        
        print("\n--- Database ---")
        print(f"Username: {credentials['database']['username']}")
        print(f"Password: {credentials['database']['password']}")
        
        print("\n--- Local Access ---")
        print(f"Username: {credentials['local_access']['username']}")
        print(f"Password: {credentials['local_access']['password']}")
        
        # Ask to save to file
        save = inquirer.prompt([
            inquirer.Confirm('save',
                           message="Save credentials to file?",
                           default=False)
        ])
        
        if save['save']:
            # Get the hive ID from the current config being created
            hive_id = self.manager.generate_hive_id()
            
            # Create filename in the hives folder
            credentials_filename = f"{hive_id}_credentials.txt"
            credentials_path = os.path.join(self.manager.base_path, credentials_filename)
            
            file_path = inquirer.prompt([
                inquirer.Text('path',
                            message="File path",
                            default=credentials_path)
            ])['path']
            
            try:
                with open(file_path, 'w') as f:
                    f.write("=== HIVE SECURITY CREDENTIALS ===\n\n")
                    f.write("--- SSH Keys ---\n")
                    f.write(f"Public Key:\n{credentials['ssh']['public_key']}\n\n")
                    f.write(f"Private Key:\n{credentials['ssh']['private_key']}\n\n")
                    
                    f.write("--- WireGuard ---\n")
                    f.write(f"Client IP: {credentials['wireguard']['client_ip']}\n")
                    f.write(f"Public Key: {credentials['wireguard']['public_key']}\n")
                    f.write(f"Private Key: {credentials['wireguard']['private_key']}\n\n")
                    
                    f.write("--- Database ---\n")
                    f.write(f"Username: {credentials['database']['username']}\n")
                    f.write(f"Password: {credentials['database']['password']}\n\n")
                    
                    f.write("--- Local Access ---\n")
                    f.write(f"Username: {credentials['local_access']['username']}\n")
                    f.write(f"Password: {credentials['local_access']['password']}\n")
                
                print(f"Credentials saved to {file_path}")
                print("WARNING: This file contains sensitive information!")
            except Exception as e:
                print(f"Error saving credentials: {str(e)}")
    
    def edit_hive(self, hive_id: str) -> None:
        """Open hive configuration in system editor"""
        config_path = self.manager.get_hive_path(hive_id)
        if not config_path.exists():
            print(f"Error: Hive configuration {hive_id} not found")
            return
        
        editor = os.environ.get('EDITOR', 'vim')
        subprocess.call([editor, str(config_path)])
    
    def remove_hive(self, hive_id: str) -> None:
        """Remove a hive configuration"""
        config_path = self.manager.get_hive_path(hive_id)
        if not config_path.exists():
            print(f"Error: Hive configuration {hive_id} not found")
            return
        
        confirm = inquirer.prompt([
            inquirer.Confirm('confirm',
                           message=f"Are you sure you want to remove {hive_id}?",
                           default=False)
        ])
        
        if confirm['confirm']:
            config_path.unlink()
            print(f"Removed hive configuration: {hive_id}")
    
    def validate_hive(self, hive_id: str) -> bool:
        """Validate hive configuration"""
        config_path = self.manager.get_hive_path(hive_id)
        if not config_path.exists():
            print(f"Error: Hive configuration {hive_id} not found")
            return False
        
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
            # TODO: Add more validation logic
            return True
        except Exception as e:
            print(f"Error validating configuration: {str(e)}")
            return False

def main():
    parser = argparse.ArgumentParser(description="Hive Configuration Manager")
    parser.add_argument("--generate-image", metavar="HIVE_ID", 
                       help="Generate Raspberry Pi image for specified hive")
    args = parser.parse_args()
    
    if args.generate_image:
        # Import and use the image generator
        try:
            from edge.raspiImageGenerator.outdated.image_generator_cli import ImageGeneratorCLI
            generator = ImageGeneratorCLI()
            generator.generate_image(args.generate_image)
            sys.exit(0)
        except ImportError:
            print("Image generator not available. Check that you're running from the repository root.")
            sys.exit(1)
        except Exception as e:
            print(f"Error generating image: {str(e)}")
            sys.exit(1)
    
    # Continue with normal CLI operation
    cli = HiveManagerCLI()
    
    while True:
        # List existing hives
        hives = cli.list_hives()
        
        # Main menu
        questions = [
            inquirer.List('action',
                         message="Select action",
                         choices=[
                             ('List hives', 'list'),
                             ('Add new hive', 'add'),
                             ('Edit hive', 'edit'),
                             ('Remove hive', 'remove'),
                             ('Validate hive', 'validate'),
                             ('Exit', 'exit')
                         ])
        ]
        
        answer = inquirer.prompt(questions)
        
        if answer['action'] == 'list':
            print("\nExisting hives:")
            for hive in hives:
                print(f"- {hive}")
            print()
        
        elif answer['action'] == 'add':
            cli.create_hive()
        
        elif answer['action'] == 'edit':
            if not hives:
                print("\nNo hives found")
                continue
                
            hive = inquirer.prompt([
                inquirer.List('id',
                            message="Select hive to edit",
                            choices=hives)
            ])
            cli.edit_hive(hive['id'])
        
        elif answer['action'] == 'remove':
            if not hives:
                print("\nNo hives found")
                continue
                
            hive = inquirer.prompt([
                inquirer.List('id',
                            message="Select hive to remove",
                            choices=hives)
            ])
            cli.remove_hive(hive['id'])
        
        elif answer['action'] == 'validate':
            if not hives:
                print("\nNo hives found")
                continue
                
            hive = inquirer.prompt([
                inquirer.List('id',
                            message="Select hive to validate",
                            choices=hives)
            ])
            if cli.validate_hive(hive['id']):
                print("Configuration is valid")
        
        elif answer['action'] == 'exit':
            break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
