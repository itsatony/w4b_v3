#!/usr/bin/env python3
"""
Raspberry Pi Image Generator CLI for Hive System

A user-friendly interface for generating customized Raspberry Pi images
with proper security configuration from the hive YAML configurations.
"""

import os
import sys
import argparse
import subprocess
import tempfile
from pathlib import Path
import yaml
import inquirer

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hive_config_manager.core.manager import HiveManager
from hive_config_manager.utils.security import SecurityUtils


class ImageGeneratorCLI:
    """User-friendly interface for generating Raspberry Pi images for hives."""
    
    def __init__(self):
        self.script_dir = Path(__file__).parent.absolute()
        self.generator_script = self.script_dir / "raspi_image_generator.sh"
        self.hive_manager = HiveManager()
    
    def list_hives(self):
        """List all available hives."""
        return self.hive_manager.list_hives()
    
    def validate_hive_security(self, hive_id: str) -> tuple:
        """
        Validate that a hive has all required security configuration.
        
        Args:
            hive_id: The hive ID to validate
            
        Returns:
            (is_valid, missing_items) tuple, where is_valid is a boolean and
            missing_items is a list of missing security items
        """
        try:
            config = self.hive_manager.get_hive(hive_id)
            missing = []
            
            # Check security section exists
            if 'security' not in config:
                return False, ["security section"]
            
            security = config['security']
            
            # Check SSH configuration
            if 'ssh' not in security:
                missing.append("SSH configuration")
            elif 'public_key' not in security['ssh'] or not security['ssh']['public_key']:
                missing.append("SSH public key")
            
            # Check WireGuard configuration
            if 'wireguard' not in security:
                missing.append("WireGuard configuration")
            elif 'private_key' not in security['wireguard'] or not security['wireguard']['private_key']:
                missing.append("WireGuard private key")
            elif 'config' not in security['wireguard'] or not security['wireguard']['config']:
                missing.append("WireGuard configuration")
            
            # Check database configuration
            if 'database' not in security:
                missing.append("Database configuration")
            elif 'password' not in security['database'] or not security['database']['password']:
                missing.append("Database password")
            
            # Check local access configuration
            if 'local_access' not in security:
                missing.append("Local access configuration")
            elif 'password' not in security['local_access'] or not security['local_access']['password']:
                missing.append("Local access password")
            
            return len(missing) == 0, missing
            
        except Exception as e:
            return False, [str(e)]
    
    def generate_missing_security(self, hive_id: str, server_endpoint: str) -> None:
        """
        Generate missing security configuration for a hive.
        
        Args:
            hive_id: The hive ID to update
            server_endpoint: The WireGuard server endpoint (ip:port)
        """
        try:
            # Generate new security credentials
            credentials = self.hive_manager.generate_security_credentials(
                hive_id, server_endpoint
            )
            
            # Apply the credentials to the hive
            self.hive_manager.apply_security_credentials(hive_id, credentials)
            
            print(f"Generated and applied missing security configuration for {hive_id}")
            return True
        except Exception as e:
            print(f"Error generating security configuration: {str(e)}")
            return False
    
    def generate_image(self, hive_id: str) -> None:
        """
        Generate a Raspberry Pi image for the specified hive.
        
        Args:
            hive_id: The hive ID to generate an image for
        """
        # Check if the script exists
        if not self.generator_script.exists():
            print(f"Error: Image generator script not found: {self.generator_script}")
            return False
        
        # Validate that the hive exists
        if hive_id not in self.list_hives():
            print(f"Error: Hive {hive_id} not found")
            return False
        
        # Validate that the hive has all required security configuration
        valid, missing = self.validate_hive_security(hive_id)
        if not valid:
            print(f"Hive {hive_id} is missing required security configuration:")
            for item in missing:
                print(f"  - {item}")
            
            # Ask if we should generate missing security configuration
            generate = inquirer.prompt([
                inquirer.Confirm('generate',
                    message="Do you want to generate the missing security configuration?",
                    default=True)
            ])
            
            if generate['generate']:
                # Ask for the server endpoint
                endpoint = inquirer.prompt([
                    inquirer.Text('endpoint',
                        message="WireGuard server endpoint (IP:Port)",
                        default="vpn.example.com:51820")
                ])
                
                if not self.generate_missing_security(hive_id, endpoint['endpoint']):
                    print("Failed to generate security configuration. Aborting.")
                    return False
            else:
                print("Cannot generate image without complete security configuration. Aborting.")
                return False
        
        # Call the shell script
        print(f"Generating Raspberry Pi image for hive {hive_id}...")
        
        # Run the script
        result = subprocess.run([
            "bash", str(self.generator_script), hive_id
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Error generating image:\n{result.stderr}")
            return False
        else:
            print(result.stdout)
            print("Image generation successful!")
            return True


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate Raspberry Pi images for W4B hives"
    )
    parser.add_argument('--list', action='store_true',
                       help="List all available hives")
    parser.add_argument('--generate', metavar='HIVE_ID',
                       help="Generate an image for the specified hive")
    
    args = parser.parse_args()
    cli = ImageGeneratorCLI()
    
    if args.list:
        hives = cli.list_hives()
        if hives:
            print("Available hives:")
            for hive in hives:
                print(f"  - {hive}")
        else:
            print("No hives found.")
        
    elif args.generate:
        cli.generate_image(args.generate)
        
    else:
        # Interactive mode
        hives = cli.list_hives()
        if not hives:
            print("No hives found. Please create a hive configuration first.")
            return
        
        # Ask which hive to generate an image for
        hive = inquirer.prompt([
            inquirer.List('id',
                message="Select a hive to generate an image for",
                choices=hives)
        ])
        
        cli.generate_image(hive['id'])
            

if __name__ == "__main__":
    main()
