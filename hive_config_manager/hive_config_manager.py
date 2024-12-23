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
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import nanoid

class HiveManager:
    def __init__(self, base_path: str = None):
        self.base_path = Path(base_path or os.path.join(os.getcwd(), 'hives'))
        self.base_path.mkdir(exist_ok=True)
        
    def list_hives(self) -> List[str]:
        """List all existing hive configurations"""
        return [f.stem for f in self.base_path.glob('*.yaml')]
    
    def generate_hive_id(self) -> str:
        """Generate a unique hive ID"""
        return f"hive_{nanoid.generate(size=8)}"
    
    def create_hive(self) -> None:
        """Interactive hive creation process"""
        print("\n=== Creating New Hive Configuration ===\n")
        
        # Basic information gathering
        questions = [
            inquirer.Text('name', message="Hive name"),
            inquirer.Text('location', message="Hive location address"),
            inquirer.Text('latitude', message="Latitude (e.g., 48.123456)"),
            inquirer.Text('longitude', message="Longitude (e.g., 11.123456)"),
            inquirer.List('timezone',
                         message="Select timezone",
                         choices=['Europe/Berlin', 'Europe/London', 'UTC']),
            inquirer.Text('notes', message="Hive notes (optional)"),
        ]
        answers = inquirer.prompt(questions)
        
        # Network configuration
        network_type = inquirer.prompt([
            inquirer.List('type',
                         message="Primary network connection",
                         choices=['wifi', 'lan'])
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
                    inquirer.Text('ssid', message="WiFi SSID"),
                    inquirer.Password('password', message="WiFi password"),
                    inquirer.Text('priority', message="Priority (1=highest)", default="1")
                ])
                wifi_networks.append({
                    'ssid': wifi['ssid'],
                    'password': wifi['password'],
                    'priority': int(wifi['priority'])
                })
            network_config['wifi'] = wifi_networks
        
        # Administrator configuration
        admins = []
        while True:
            add_admin = inquirer.prompt([
                inquirer.Confirm('add', message="Add administrator?", default=True)
            ])
            if not add_admin['add']:
                break
                
            admin = inquirer.prompt([
                inquirer.Text('name', message="Admin name"),
                inquirer.Text('email', message="Admin email"),
                inquirer.Text('username', message="Admin username"),
                inquirer.Text('phone', message="Admin phone"),
                inquirer.List('role',
                            message="Admin role",
                            choices=['hive_admin', 'hive_viewer'])
            ])
            admins.append(admin)
        
        # Generate configuration
        hive_id = self.generate_hive_id()
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
        
        # Save configuration
        config_path = self.base_path / f"{hive_id}.yaml"
        with open(config_path, 'w') as f:
            yaml.safe_dump(config, f, sort_keys=False)
        
        print(f"\nCreated hive configuration: {config_path}")
        self.edit_hive(hive_id)
    
    def edit_hive(self, hive_id: str) -> None:
        """Open hive configuration in system editor"""
        config_path = self.base_path / f"{hive_id}.yaml"
        if not config_path.exists():
            print(f"Error: Hive configuration {hive_id} not found")
            return
        
        editor = os.environ.get('EDITOR', 'vim')
        subprocess.call([editor, str(config_path)])
    
    def remove_hive(self, hive_id: str) -> None:
        """Remove a hive configuration"""
        config_path = self.base_path / f"{hive_id}.yaml"
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
        config_path = self.base_path / f"{hive_id}.yaml"
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
    manager = HiveManager()
    
    while True:
        # List existing hives
        hives = manager.list_hives()
        
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
            manager.create_hive()
        
        elif answer['action'] == 'edit':
            if not hives:
                print("\nNo hives found")
                continue
                
            hive = inquirer.prompt([
                inquirer.List('id',
                            message="Select hive to edit",
                            choices=hives)
            ])
            manager.edit_hive(hive['id'])
        
        elif answer['action'] == 'remove':
            if not hives:
                print("\nNo hives found")
                continue
                
            hive = inquirer.prompt([
                inquirer.List('id',
                            message="Select hive to remove",
                            choices=hives)
            ])
            manager.remove_hive(hive['id'])
        
        elif answer['action'] == 'validate':
            if not hives:
                print("\nNo hives found")
                continue
                
            hive = inquirer.prompt([
                inquirer.List('id',
                            message="Select hive to validate",
                            choices=hives)
            ])
            if manager.validate_hive(hive['id']):
                print("Configuration is valid")
        
        elif answer['action'] == 'exit':
            break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
