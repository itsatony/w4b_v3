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
            
            # Ensure mount points exist
            if "image_path" not in self.state:
                self.logger.error("Image path not found in state")
                return False
            
            image_path = self.state["image_path"]
            self.logger.info(f"Configuring system settings for image: {image_path}")
            
            # Setup loop device (required for cached images)
            self.logger.info(f"Setting up loop device for: {image_path}")
            if not await self._setup_loop_device(image_path):
                self.logger.error("Failed to setup loop device")
                return False
            
            # Now mount image partitions
            self.logger.info(f"Mounting image partitions for: {image_path}")
            if not await self._mount_image_partitions():
                self.logger.error("Failed to mount image partitions")
                return False
            
            # Configure system settings
            await self._configure_system(self.boot_mount, self.root_mount)
            
            return True
            
        except Exception as e:
            self.logger.error(f"System configuration failed: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return False
        finally:
            # Make sure we cleanup loop device and mounts if we're not using cached mounts
            if getattr(self, "using_loop_device", False) and not getattr(self, "using_cached_mounts", False):
                await self._cleanup_mounts()
    
    async def _setup_loop_device(self, image_path: Path) -> bool:
        """
        Set up loop device for the image with enhanced validation.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if we're using cached unpacked image
            if "cached_unpacked_path" in self.state:
                self.logger.info("Using cached unpacked image, no need for loop device")
                self.using_cached_mounts = True
                return True
            
            # Validate the image file first
            if not await self._validate_image_file(image_path):
                return False
            
            # Force detach any existing loop device with this image
            await self._force_detach_existing_loops(image_path)
            
            # First try using losetup with better options
            self.logger.info(f"Setting up loop device for: {image_path}")
            result = await asyncio.create_subprocess_exec(
                'losetup', '--partscan', '--find', '--show', str(image_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                self.logger.error(f"Failed to set up loop device: {stderr.decode().strip()}")
                return False
            
            self.loop_device = stdout.decode().strip()
            if not self.loop_device:
                self.logger.error("Failed to get loop device path")
                return False
                
            self.logger.info(f"Loop device: {self.loop_device}")
            self.using_loop_device = True
            
            # Wait longer to ensure kernel has time to recognize partitions
            self.logger.info("Waiting for partitions to be recognized...")
            await asyncio.sleep(5)  # Increased wait time
            
            # Get detailed information about the loop device
            await self._debug_loop_device(self.loop_device)
            
            # Try to find the partitions
            boot_part, root_part = await self._find_partitions(self.loop_device, image_path)
            
            if not boot_part or not root_part:
                self.logger.error("Failed to identify partitions in the image")
                await self._cleanup_loop_device(self.loop_device)
                return False
            
            self.boot_partition = boot_part
            self.root_partition = root_part
            
            self.logger.info(f"Using partitions: Boot={self.boot_partition}, Root={self.root_partition}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting up loop device: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            
            if hasattr(self, 'loop_device') and self.loop_device:
                await self._cleanup_loop_device(self.loop_device)
            return False

    async def _validate_image_file(self, image_path: Path) -> bool:
        """
        Validate the image file before attempting to mount it.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            self.logger.info(f"Validating image file: {image_path}")
            
            # Check if file exists
            if not image_path.exists():
                self.logger.error(f"Image file does not exist: {image_path}")
                return False
                
            # Check file size
            file_size = image_path.stat().st_size
            if file_size < 1024 * 1024:  # At least 1MB
                self.logger.error(f"Image file too small ({file_size} bytes): {image_path}")
                return False
                
            self.logger.info(f"Image file size: {file_size / (1024*1024):.2f} MB")
            
            # Check file type with the 'file' command
            file_result = await asyncio.create_subprocess_exec(
                "file", str(image_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            file_stdout, _ = await file_result.communicate()
            file_output = file_stdout.decode()
            
            self.logger.info(f"File type: {file_output.strip()}")
            
            # Basic validation - should contain boot sector in output for disk images
            if "boot sector" not in file_output.lower() and "dos/mbr boot sector" not in file_output.lower():
                self.logger.warning(f"File may not be a valid disk image: {file_output}")
                # We'll continue anyway but with a warning
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to validate image file: {str(e)}")
            return False

    async def _debug_loop_device(self, loop_device: str) -> None:
        """
        Get detailed information about a loop device for debugging.
        
        Args:
            loop_device: Path to the loop device
        """
        try:
            # Get loop device info
            losetup_result = await asyncio.create_subprocess_exec(
                'losetup', '-a',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await losetup_result.communicate()
            
            self.logger.info(f"Loop device status:\n{stdout.decode()}")
            if stderr:
                self.logger.warning(f"Loop device stderr: {stderr.decode()}")
            
            # Try to print partition table with sfdisk
            sfdisk_result = await asyncio.create_subprocess_exec(
                'sfdisk', '-l', loop_device,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            sfdisk_stdout, sfdisk_stderr = await sfdisk_result.communicate()
            
            if sfdisk_stdout:
                self.logger.info(f"Partition table (sfdisk):\n{sfdisk_stdout.decode()}")
            
            if sfdisk_stderr:
                self.logger.info(f"sfdisk stderr: {sfdisk_stderr.decode()}")
                
                # If sfdisk fails, try fdisk as a fallback
                fdisk_result = await asyncio.create_subprocess_exec(
                    'fdisk', '-l', loop_device,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                fdisk_stdout, fdisk_stderr = await fdisk_result.communicate()
                
                if fdisk_stdout:
                    self.logger.info(f"Partition table (fdisk):\n{fdisk_stdout.decode()}")
                
                if fdisk_stderr:
                    self.logger.warning(f"fdisk stderr: {fdisk_stderr.decode()}")
                    
        except Exception as e:
            self.logger.warning(f"Error during loop device debugging: {str(e)}")

    async def _find_partitions(self, loop_device: str, image_path: Path) -> tuple:
        """
        Find partitions using multiple methods with better error handling.
        
        Args:
            loop_device: Path to the loop device
            image_path: Path to the original image file
            
        Returns:
            tuple: (boot_partition, root_partition) or (None, None) on failure
        """
        try:
            # Try to force kernel to scan the partition table
            partprobe_result = await asyncio.create_subprocess_exec(
                'partprobe', '-s', loop_device,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await partprobe_result.communicate()
            
            if stdout:
                self.logger.info(f"Partprobe output: {stdout.decode()}")
            
            if stderr:
                self.logger.warning(f"Partprobe stderr: {stderr.decode()}")
                
            # Alternative approach - try to recreate the loop device with partscan
            if partprobe_result.returncode != 0:
                self.logger.info("Trying to recreate loop device with --partscan")
                detach_result = await asyncio.create_subprocess_exec(
                    'losetup', '-d', loop_device,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await detach_result.communicate()
                
                recreate_result = await asyncio.create_subprocess_exec(
                    'losetup', '--partscan', '-f', '--show', str(image_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await recreate_result.communicate()
                
                if recreate_result.returncode == 0:
                    new_loop_device = stdout.decode().strip()
                    if new_loop_device:
                        self.logger.info(f"Recreated loop device: {new_loop_device}")
                        loop_device = new_loop_device
                        # Wait for partitions to be recognized
                        await asyncio.sleep(3)
                
            # Try standard partition naming schemes
            naming_schemes = [
                # Standard p1/p2 naming
                (f"{loop_device}p1", f"{loop_device}p2"),
                # Alternative 1/2 naming
                (f"{loop_device}1", f"{loop_device}2")
            ]
            
            for boot_part, root_part in naming_schemes:
                self.logger.info(f"Checking for partitions: {boot_part}, {root_part}")
                if Path(boot_part).exists() and Path(root_part).exists():
                    self.logger.info(f"Found partitions: {boot_part}, {root_part}")
                    return boot_part, root_part
            
            # If standard approach fails, try more aggressive methods
            self.logger.info("No partitions found with standard naming, trying advanced methods")
            
            # Method 1: Try using kpartx
            self.logger.info("Trying kpartx to create partition mappings")
            kpartx_result = await asyncio.create_subprocess_exec(
                'kpartx', '-avs', loop_device,  # Added -s for sync mode
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            kpartx_stdout, kpartx_stderr = await kpartx_result.communicate()
            
            if kpartx_stdout:
                self.logger.info(f"kpartx stdout: {kpartx_stdout.decode()}")
            
            if kpartx_stderr:
                self.logger.info(f"kpartx stderr: {kpartx_stderr.decode()}")
                
                # If kpartx reports read errors, the image file might be corrupt
                if "read error" in kpartx_stderr.decode():
                    self.logger.error("Image file appears to be corrupt or incomplete. Try redownloading.")
                    return None, None
            
            # Wait for device mapper to create nodes
            await asyncio.sleep(3)
            
            # Check device mapper nodes
            loop_basename = os.path.basename(loop_device)
            mapper_candidates = [
                (f"/dev/mapper/{loop_basename}p1", f"/dev/mapper/{loop_basename}p2"),
                (f"/dev/mapper/loop{loop_basename.replace('loop', '')}p1", 
                 f"/dev/mapper/loop{loop_basename.replace('loop', '')}p2")
            ]
            
            for boot_part, root_part in mapper_candidates:
                self.logger.info(f"Checking mapper devices: {boot_part}, {root_part}")
                if Path(boot_part).exists() and Path(root_part).exists():
                    self.logger.info(f"Found mapper devices: {boot_part}, {root_part}")
                    return boot_part, root_part
            
            # Method 2: Last resort - try using a different approach like loop-control
            # List available devices for debugging
            self._debug_list_devices()
            
            # Failed to find partitions
            self.logger.error("Failed to identify partitions in the image")
            return None, None
            
        except Exception as e:
            self.logger.error(f"Error finding partitions: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return None, None

    async def _force_detach_existing_loops(self, image_path: Path) -> None:
        """Forcibly detach any existing loop devices for this image"""
        try:
            # Find if the image is already attached to a loop device
            result = await asyncio.create_subprocess_exec(
                'losetup', '-j', str(image_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            
            if stdout:
                attached_loops = stdout.decode().strip().split('\n')
                for line in attached_loops:
                    if not line:
                        continue
                        
                    # Extract loop device path
                    loop_dev = line.split(':')[0]
                    self.logger.info(f"Detaching existing loop device: {loop_dev}")
                    
                    # Detach the loop device
                    await asyncio.create_subprocess_exec(
                        'losetup', '-d', loop_dev,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
        except Exception as e:
            self.logger.warning(f"Error detaching existing loop devices: {str(e)}")

    async def _verify_partitions(self, loop_device: str) -> None:
        """Verify the partition table of the image"""
        try:
            # Use fdisk to list partitions
            fdisk_result = await asyncio.create_subprocess_exec(
                'fdisk', '-l', loop_device,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await fdisk_result.communicate()
            
            self.logger.info(f"Partition table for {loop_device}:")
            self.logger.info(stdout.decode())
            
            if stderr:
                self.logger.warning(f"fdisk stderr: {stderr.decode()}")
        except Exception as e:
            self.logger.warning(f"Error verifying partitions: {str(e)}")

    def _debug_list_devices(self) -> None:
        """List devices for debugging purposes"""
        try:
            # List /dev
            import glob
            devices = glob.glob('/dev/loop*') + glob.glob('/dev/mapper/*')
            self.logger.info(f"Available devices: {devices}")
            
            # List block devices
            os.system('lsblk > /tmp/lsblk_debug.txt')
            with open('/tmp/lsblk_debug.txt', 'r') as f:
                self.logger.info(f"Block devices:\n{f.read()}")
        except Exception as e:
            self.logger.warning(f"Error listing devices: {str(e)}")

    async def _cleanup_loop_device(self, loop_device: str) -> None:
        """Clean up loop device resources"""
        try:
            # Try to detach the loop device
            self.logger.info(f"Detaching loop device: {loop_device}")
            
            # First try to clean up kpartx mappings if they exist
            kpartx_result = await asyncio.create_subprocess_exec(
                'kpartx', '-d', loop_device,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await kpartx_result.communicate()
            
            # Now detach the loop device
            detach_result = await asyncio.create_subprocess_exec(
                'losetup', '-d', loop_device,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await detach_result.communicate()
            
            if detach_result.returncode != 0:
                self.logger.warning(f"Failed to detach loop device: {stderr.decode()}")
        except Exception as e:
            self.logger.warning(f"Error cleaning up loop device: {str(e)}")

    async def _mount_image_partitions(self) -> bool:
        """
        Mount the image partitions.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if we're using cached unpacked image
            if "cached_unpacked_path" in self.state:
                self.boot_mount = self.state["boot_mount"]
                self.root_mount = self.state["root_mount"]
                self.logger.info(f"Using cached mounts: boot={self.boot_mount}, root={self.root_mount}")
                return True
            
            # Create mount points
            self.boot_mount = Path("/tmp/w4b_mnt_boot")
            self.root_mount = Path("/tmp/w4b_mnt_root")
            
            self.boot_mount.mkdir(parents=True, exist_ok=True)
            self.root_mount.mkdir(parents=True, exist_ok=True)
            
            # Mount boot partition
            boot_result = await asyncio.create_subprocess_exec(
                'mount', self.boot_partition, str(self.boot_mount),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            boot_stdout, boot_stderr = await boot_result.communicate()
            
            if boot_result.returncode != 0:
                self.logger.error(f"Failed to mount boot partition: {boot_stderr.decode().strip()}")
                return False
            
            # Mount root partition 
            root_result = await asyncio.create_subprocess_exec(
                'mount', self.root_partition, str(self.root_mount),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            root_stdout, root_stderr = await root_result.communicate()
            
            if root_result.returncode != 0:
                self.logger.error(f"Failed to mount root partition: {root_stderr.decode().strip()}")
                # Unmount boot if we failed to mount root
                await asyncio.create_subprocess_exec('umount', str(self.boot_mount))
                return False
            
            # Store mount points in state
            self.state["boot_mount"] = self.boot_mount
            self.state["root_mount"] = self.root_mount
            
            self.logger.info(f"Mounted boot partition at: {self.boot_mount}")
            self.logger.info(f"Mounted root partition at: {self.root_mount}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error mounting partitions: {str(e)}")
            return False
    
    async def _cleanup_mounts(self) -> None:
        """Clean up mounts and loop device."""
        try:
            if hasattr(self, 'boot_mount') and self.boot_mount.exists():
                self.logger.info(f"Unmounting boot partition: {self.boot_mount}")
                await asyncio.create_subprocess_exec('umount', str(self.boot_mount))
                
            if hasattr(self, 'root_mount') and self.root_mount.exists():
                self.logger.info(f"Unmounting root partition: {self.root_mount}")
                await asyncio.create_subprocess_exec('umount', str(self.root_mount))
                
            if hasattr(self, 'loop_device') and self.loop_device:
                self.logger.info(f"Detaching loop device: {self.loop_device}")
                await asyncio.create_subprocess_exec('losetup', '-d', self.loop_device)
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")
    
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
