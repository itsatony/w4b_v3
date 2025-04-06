#!/usr/bin/env python3
"""
System configuration stage for Raspberry Pi image generator.
"""

import os
import sys
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from core.stages.base import BuildStage

class SystemConfigStage(BuildStage):
    """
    Build stage for configuring the base system settings of the image.
    """
    
    async def execute(self) -> bool:
        try:
            self.logger.info("Starting stage: SystemConfigStage")
            
            # Get the image path from state, looking for either base_image_path or image_path
            if "base_image_path" in self.state:
                image_path = self.state["base_image_path"]
                self.logger.debug(f"Using base_image_path: {image_path}")
            elif "image_path" in self.state:
                image_path = self.state["image_path"]
                self.logger.debug(f"Using image_path: {image_path}")
            else:
                raise KeyError("Neither 'image_path' nor 'base_image_path' found in state")
            
            # Check if image needs extraction (if it's an .xz file)
            if str(image_path).endswith('.xz'):
                self.logger.info("Image is compressed, extracting first...")
                extracted_path = await self._extract_image(image_path)
                self.state["image_path"] = extracted_path
            else:
                # Store the image path in the state dictionary under both keys for compatibility
                self.state["image_path"] = image_path
            
            # Now we're guaranteed to have image_path in the state
            self.logger.info(f"Configuring system settings for image: {self.state['image_path']}")
            
            # Mount the image partitions
            boot_mount, root_mount = await self._mount_image(self.state["image_path"])
            
            # Store mount points in state for other stages to use
            self.state["boot_mount"] = boot_mount
            self.state["root_mount"] = root_mount
            
            # Configure system settings
            await self._configure_system(boot_mount, root_mount)
            
            return True
            
        except Exception as e:
            self.logger.error(f"System configuration failed: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            
            # Make sure to unmount if we failed
            if "boot_mount" in self.state and "root_mount" in self.state:
                await self._unmount_image(self.state["boot_mount"], self.state["root_mount"])
                
            return False
    
    async def _extract_image(self, compressed_path: Path) -> Path:
        """Extract the compressed image."""
        self.logger.info(f"Extracting image: {compressed_path}")
        
        # Determine output path (remove .xz extension)
        output_path = Path(str(compressed_path).replace('.xz', ''))
        
        # Run xz to decompress
        process = await asyncio.create_subprocess_exec(
            'xz', '--decompress', '--keep', str(compressed_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise RuntimeError(f"Failed to extract image: {stderr.decode()}")
        
        self.logger.info(f"Extracted image to: {output_path}")
        return output_path
    
    async def _mount_image(self, image_path: Path) -> Tuple[Path, Path]:
        """
        Mount the boot and root partitions of the Raspberry Pi image.
        
        Returns:
            Tuple[Path, Path]: Paths to the boot and root mount points
        """
        self.logger.info(f"Mounting image partitions for: {image_path}")
        
        # Create mount points in work directory
        work_dir = Path(os.path.dirname(image_path)).parent
        boot_mount = work_dir / "boot"
        root_mount = work_dir / "rootfs"
        
        # Create directories if they don't exist
        boot_mount.mkdir(exist_ok=True)
        root_mount.mkdir(exist_ok=True)
        
        # Set up loop device for the image
        loop_process = await asyncio.create_subprocess_exec(
            'losetup', '--find', '--show', '--partscan', str(image_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await loop_process.communicate()
        if loop_process.returncode != 0:
            raise RuntimeError(f"Failed to set up loop device: {stderr.decode()}")
        
        loop_device = stdout.decode().strip()
        self.state["loop_device"] = loop_device
        
        # Mount boot partition (typically partition 1)
        boot_process = await asyncio.create_subprocess_exec(
            'mount', f"{loop_device}p1", str(boot_mount),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await boot_process.communicate()
        if boot_process.returncode != 0:
            # Clean up loop device
            await asyncio.create_subprocess_exec('losetup', '--detach', loop_device)
            raise RuntimeError(f"Failed to mount boot partition: {stderr.decode()}")
        
        # Mount root partition (typically partition 2)
        root_process = await asyncio.create_subprocess_exec(
            'mount', f"{loop_device}p2", str(root_mount),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await root_process.communicate()
        if root_process.returncode != 0:
            # Clean up boot mount and loop device
            await asyncio.create_subprocess_exec('umount', str(boot_mount))
            await asyncio.create_subprocess_exec('losetup', '--detach', loop_device)
            raise RuntimeError(f"Failed to mount root partition: {stderr.decode()}")
        
        self.logger.info(f"Mounted boot partition at: {boot_mount}")
        self.logger.info(f"Mounted root partition at: {root_mount}")
        
        return boot_mount, root_mount
    
    async def _unmount_image(self, boot_mount: Path, root_mount: Path) -> None:
        """Unmount image partitions and clean up loop device."""
        self.logger.info("Unmounting image partitions")
        
        # Unmount root partition
        await asyncio.create_subprocess_exec('umount', str(root_mount))
        
        # Unmount boot partition
        await asyncio.create_subprocess_exec('umount', str(boot_mount))
        
        # Detach loop device if it exists in state
        if "loop_device" in self.state:
            await asyncio.create_subprocess_exec('losetup', '--detach', self.state["loop_device"])
    
    async def _configure_system(self, boot_mount: Path, root_mount: Path) -> None:
        """Configure system settings on the mounted image."""
        self.logger.info("Configuring system settings")
        
        # Get configuration from state
        config = self.state["config"]
        system_config = config.get("system", {})
        
        # Configure hostname
        hostname = f"{system_config.get('hostname_prefix', 'hive')}-{config['hive_id']}"
        hostname_path = root_mount / "etc/hostname"
        with open(hostname_path, 'w') as f:
            f.write(f"{hostname}\n")
        
        # Configure timezone
        timezone = system_config.get("timezone", "UTC")
        await self._set_timezone(root_mount, timezone)
        
        # Configure locale
        locale = system_config.get("locale", "en_US.UTF-8")
        await self._set_locale(root_mount, locale)
        
        # Configure keyboard layout
        keyboard = system_config.get("keyboard", "us")
        await self._set_keyboard(root_mount, keyboard)
        
        # Configure SSH
        ssh_config = system_config.get("ssh", {})
        if ssh_config.get("enabled", True):
            await self._configure_ssh(boot_mount, root_mount, ssh_config)
    
    async def _set_timezone(self, root_mount: Path, timezone: str) -> None:
        """Set the timezone in the mounted image."""
        self.logger.info(f"Setting timezone to: {timezone}")
        
        # Create symlink to timezone file
        timezone_path = root_mount / "etc/localtime"
        timezone_src = f"../usr/share/zoneinfo/{timezone}"
        
        # Remove existing symlink if it exists
        if timezone_path.exists():
            timezone_path.unlink()
        
        # Create new symlink
        timezone_path.symlink_to(timezone_src)
        
        # Write timezone to /etc/timezone
        with open(root_mount / "etc/timezone", 'w') as f:
            f.write(f"{timezone}\n")
    
    async def _set_locale(self, root_mount: Path, locale: str) -> None:
        """Set the locale in the mounted image."""
        self.logger.info(f"Setting locale to: {locale}")
        
        # Write locale to /etc/default/locale
        with open(root_mount / "etc/default/locale", 'w') as f:
            f.write(f'LANG="{locale}"\n')
            f.write(f'LC_ALL="{locale}"\n')
        
        # Enable locale in /etc/locale.gen
        locale_gen_path = root_mount / "etc/locale.gen"
        with open(locale_gen_path, 'r') as f:
            lines = f.readlines()
        
        with open(locale_gen_path, 'w') as f:
            for line in lines:
                if line.strip().startswith(f"# {locale}") or line.strip() == f"# {locale}":
                    f.write(f"{locale} UTF-8\n")
                else:
                    f.write(line)
    
    async def _set_keyboard(self, root_mount: Path, keyboard: str) -> None:
        """Set the keyboard layout in the mounted image."""
        self.logger.info(f"Setting keyboard layout to: {keyboard}")
        
        keyboard_config_path = root_mount / "etc/default/keyboard"
        if keyboard_config_path.exists():
            with open(keyboard_config_path, 'r') as f:
                lines = f.readlines()
            
            with open(keyboard_config_path, 'w') as f:
                for line in lines:
                    if line.startswith('XKBLAYOUT='):
                        f.write(f'XKBLAYOUT="{keyboard}"\n')
                    else:
                        f.write(line)
    
    async def _configure_ssh(self, boot_mount: Path, root_mount: Path, ssh_config: Dict[str, Any]) -> None:
        """Configure SSH settings in the mounted image."""
        self.logger.info("Configuring SSH")
        
        # Enable SSH by creating ssh file in boot partition
        ssh_file = boot_mount / "ssh"
        if not ssh_file.exists():
            ssh_file.touch()
        
        # Configure SSH server settings
        sshd_config_path = root_mount / "etc/ssh/sshd_config"
        if sshd_config_path.exists():
            # Read current config
            with open(sshd_config_path, 'r') as f:
                lines = f.readlines()
            
            # Update settings
            password_auth = "yes" if ssh_config.get("password_auth", False) else "no"
            port = ssh_config.get("port", 22)
            root_login = "yes" if ssh_config.get("allow_root", False) else "no"
            
            # Write updated config
            with open(sshd_config_path, 'w') as f:
                for line in lines:
                    if line.strip().startswith("PasswordAuthentication "):
                        f.write(f"PasswordAuthentication {password_auth}\n")
                    elif line.strip().startswith("Port "):
                        f.write(f"Port {port}\n")
                    elif line.strip().startswith("PermitRootLogin "):
                        f.write(f"PermitRootLogin {root_login}\n")
                    else:
                        f.write(line)
