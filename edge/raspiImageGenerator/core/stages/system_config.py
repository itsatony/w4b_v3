#!/usr/bin/env python3
"""
System configuration stage for the W4B Raspberry Pi Image Generator.

This module implements the system configuration stage of the build pipeline,
responsible for setting up basic OS settings like hostname, locale, timezone,
and network configuration.
"""

import asyncio
import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

from core.stages.base import BuildStage
from utils.error_handling import ImageBuildError


class SystemConfigStage(BuildStage):
    """
    Build stage for configuring the base system settings.
    
    This stage is responsible for setting up basic OS configurations like
    hostname, locale, timezone, and network settings.
    
    Attributes:
        name (str): Name of the stage
        state (Dict[str, Any]): Shared pipeline state
        logger (logging.Logger): Logger instance
        circuit_breaker (CircuitBreaker): Circuit breaker for fault tolerance
    """
    
    async def execute(self) -> bool:
        """
        Execute the system configuration stage.
        
        Returns:
            bool: True if configuration succeeded, False otherwise
        """
        try:
            # Get image builder from state
            image_builder = self.state["image_builder"]
            image_path = self.state["image_path"]
            
            # Mount the image
            self.logger.info("Mounting image")
            boot_mount, root_mount = await image_builder.mount_image(image_path)
            
            try:
                # Configure hostname
                await self._configure_hostname(root_mount)
                
                # Configure timezone
                await self._configure_timezone(root_mount)
                
                # Configure locale
                await self._configure_locale(root_mount)
                
                # Configure network
                await self._configure_network(root_mount, boot_mount)
                
                # Create first boot script
                await self._create_firstboot_script(boot_mount, root_mount)
                
                # Update state
                self.state["boot_mount"] = boot_mount
                self.state["root_mount"] = root_mount
                
                self.logger.info("System configuration completed successfully")
                return True
                
            finally:
                # Don't unmount the image here - later stages need access to it
                # We'll unmount in the compression stage (or cleanup)
                pass
            
        except Exception as e:
            self.logger.exception(f"System configuration failed: {str(e)}")
            return False
    
    async def _configure_hostname(self, root_mount: Path) -> None:
        """
        Configure the system hostname.
        
        Args:
            root_mount: Path to the root file system
        """
        # Get hostname from configuration
        hostname_prefix = self.state["config"]["system"]["hostname_prefix"]
        hive_id = self.state["config"]["hive_id"]
        hostname = f"{hostname_prefix}-{hive_id}"
        
        # Write hostname file
        hostname_path = root_mount / "etc/hostname"
        self.logger.info(f"Setting hostname to: {hostname}")
        
        with open(hostname_path, "w") as f:
            f.write(f"{hostname}\n")
        
        # Update hosts file
        hosts_path = root_mount / "etc/hosts"
        with open(hosts_path, "r") as f:
            hosts_content = f.readlines()
        
        # Modify localhost line to include our hostname
        with open(hosts_path, "w") as f:
            for line in hosts_content:
                if line.strip().startswith("127.0.1.1"):
                    f.write(f"127.0.1.1\t{hostname}\n")
                else:
                    f.write(line)
    
    async def _configure_timezone(self, root_mount: Path) -> None:
        """
        Configure the system timezone.
        
        Args:
            root_mount: Path to the root file system
        """
        # Get timezone from configuration
        timezone = self.state["config"]["system"]["timezone"]
        self.logger.info(f"Setting timezone to: {timezone}")
        
        # Create symlink for timezone
        timezone_path = root_mount / "etc/localtime"
        zoneinfo_path = root_mount / "usr/share/zoneinfo" / timezone
        
        # Remove existing symlink or file
        if timezone_path.exists():
            timezone_path.unlink()
        
        # Create relative symlink
        os.symlink(
            os.path.relpath(zoneinfo_path, timezone_path.parent),
            timezone_path
        )
        
        # Write timezone file
        with open(root_mount / "etc/timezone", "w") as f:
            f.write(f"{timezone}\n")
    
    async def _configure_locale(self, root_mount: Path) -> None:
        """
        Configure system locale settings.
        
        Args:
            root_mount: Path to the root file system
        """
        # Get locale from configuration
        locale = self.state["config"]["system"]["locale"]
        keyboard = self.state["config"]["system"]["keyboard"]
        
        self.logger.info(f"Setting locale to: {locale}, keyboard: {keyboard}")
        
        # Configure locale
        locale_gen_path = root_mount / "etc/locale.gen"
        with open(locale_gen_path, "r") as f:
            content = f.readlines()
        
        with open(locale_gen_path, "w") as f:
            for line in content:
                if locale in line and line.startswith("# "):
                    # Uncomment the locale line
                    f.write(line[2:])
                else:
                    f.write(line)
        
        # Set default locale
        with open(root_mount / "etc/default/locale", "w") as f:
            f.write(f'LANG="{locale}"\n')
            f.write(f'LC_ALL="{locale}"\n')
        
        # Configure keyboard
        with open(root_mount / "etc/default/keyboard", "w") as f:
            f.write(f'XKBMODEL="pc105"\n')
            f.write(f'XKBLAYOUT="{keyboard}"\n')
            f.write('XKBVARIANT=""\n')
            f.write('XKBOPTIONS=""\n')
            f.write('BACKSPACE="guess"\n')
    
    async def _configure_network(self, root_mount: Path, boot_mount: Path) -> None:
        """
        Configure network settings.
        
        Args:
            root_mount: Path to the root file system
            boot_mount: Path to the boot partition
        """
        # Enable SSH by default
        ssh_enabled = self.state["config"]["system"]["ssh"]["enabled"]
        if ssh_enabled:
            self.logger.info("Enabling SSH")
            # Create empty ssh file in boot to enable SSH
            ssh_file = boot_mount / "ssh"
            ssh_file.touch()
        
        # Configure network manager for WiFi if needed
        if "wifi" in self.state["config"].get("network", {}):
            wifi_config = self.state["config"]["network"]["wifi"]
            self.logger.info(f"Configuring WiFi for SSID: {wifi_config.get('ssid')}")
            
            # Create netplan configuration
            netplan_dir = root_mount / "etc/netplan"
            netplan_dir.mkdir(exist_ok=True)
            
            with open(netplan_dir / "99-w4b-wifi.yaml", "w") as f:
                f.write("network:\n")
                f.write("  version: 2\n")
                f.write("  wifis:\n")
                f.write("    wlan0:\n")
                f.write("      dhcp4: true\n")
                f.write("      optional: true\n")
                f.write("      access-points:\n")
                f.write(f"        \"{wifi_config['ssid']}\":\n")
                if "password" in wifi_config:
                    f.write(f"          password: \"{wifi_config['password']}\"\n")
    
    async def _create_firstboot_script(self, boot_mount: Path, root_mount: Path) -> None:
        """
        Create first boot initialization script.
        
        This script runs on first boot to complete system setup.
        
        Args:
            boot_mount: Path to the boot partition
            root_mount: Path to the root file system
        """
        self.logger.info("Creating first boot script")
        
        # Create the script
        script_path = boot_mount / "firstboot.sh"
        with open(script_path, "w") as f:
            f.write("#!/bin/bash\n")
            f.write("set -e\n\n")
            f.write(f"echo \"Running first boot setup for hive {self.state['config']['hive_id']}...\"\n\n")
            
            # Update package lists
            f.write("# Update package lists\n")
            f.write("apt-get update\n\n")
            
            # Generate locales
            f.write("# Generate locales\n")
            f.write("locale-gen\n\n")
            
            # Mark setup as complete
            f.write("# Mark setup as complete\n")
            f.write("touch /boot/setup_complete\n")
            f.write("systemctl disable firstboot.service\n")
            f.write("rm /boot/firstboot.sh\n\n")
            
            f.write("echo \"First boot setup completed\"\n")
        
        # Make it executable
        script_path.chmod(0o755)
        
        # Create systemd service to run the script
        service_path = root_mount / "etc/systemd/system/firstboot.service"
        with open(service_path, "w") as f:
            f.write("[Unit]\n")
            f.write(f"Description=First Boot Setup for Hive {self.state['config']['hive_id']}\n")
            f.write("After=network.target\n\n")
            
            f.write("[Service]\n")
            f.write("Type=oneshot\n")
            f.write("ExecStart=/boot/firstboot.sh\n")
            f.write("RemainAfterExit=yes\n\n")
            
            f.write("[Install]\n")
            f.write("WantedBy=multi-user.target\n")
        
        # Enable the service
        services_dir = root_mount / "etc/systemd/system/multi-user.target.wants"
        services_dir.mkdir(exist_ok=True)
        
        # Create symlink to enable the service
        service_link = services_dir / "firstboot.service"
        if not service_link.exists():
            os.symlink("../firstboot.service", service_link)
