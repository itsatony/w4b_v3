#!/usr/bin/env python3
"""
Software installation stage for Raspberry Pi image generator.
"""

import os
import sys
import asyncio
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional

from core.stages.base import BuildStage

class SoftwareInstallStage(BuildStage):
    """
    Build stage for installing software on the Raspberry Pi image.
    """
    
    async def execute(self) -> bool:
        try:
            self.logger.info("Starting stage: SoftwareInstallStage")
            
            # Ensure we have access to mounted filesystem
            if "root_mount" not in self.state or "boot_mount" not in self.state:
                self.logger.error("Root or boot mount points not found in state")
                return False
                
            root_mount = self.state["root_mount"]
            
            # Setup for chroot environment
            if not await self._setup_chroot(root_mount):
                self.logger.error("Failed to set up chroot environment")
                return False
            
            # Configure APT sources
            self.logger.info("Configuring APT sources")
            if not await self._configure_apt_sources(root_mount):
                self.logger.warning("APT source configuration failed, but continuing")
            
            # Install required packages
            self.logger.info(f"Installing {len(self.packages)} system packages")
            if not await self._install_packages(root_mount):
                self.logger.error("Package installation failed")
                return False
            
            # Clean up chroot environment
            await self._cleanup_chroot(root_mount)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Software installation failed: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return False
    
    async def _setup_chroot(self, root_mount: Path) -> bool:
        """
        Set up chroot environment for ARM architecture.
        
        Args:
            root_mount: Path to the mounted root filesystem
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Find qemu-arm-static on the host system
            qemu_paths = [
                "/usr/bin/qemu-arm-static",
                "/usr/local/bin/qemu-arm-static"
            ]
            
            qemu_host_path = None
            for path in qemu_paths:
                if Path(path).exists():
                    qemu_host_path = path
                    break
                    
            if not qemu_host_path:
                self.logger.error("qemu-arm-static not found on host system")
                self.logger.info("Installing qemu-user-static on host system")
                
                # Try to install qemu-user-static if it's not found
                try:
                    install_result = await asyncio.create_subprocess_exec(
                        'sudo', 'apt', 'update',
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    await install_result.communicate()
                    
                    install_result = await asyncio.create_subprocess_exec(
                        'sudo', 'apt', 'install', '-y', 'qemu-user-static',
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    await install_result.communicate()
                    
                    if install_result.returncode != 0:
                        self.logger.error("Failed to install qemu-user-static")
                        return False
                        
                    # Check if it's now available
                    for path in qemu_paths:
                        if Path(path).exists():
                            qemu_host_path = path
                            break
                            
                    if not qemu_host_path:
                        self.logger.error("qemu-arm-static still not found after installation")
                        return False
                except Exception as e:
                    self.logger.error(f"Failed to install qemu-user-static: {str(e)}")
                    return False
            
            # Create target directory if it doesn't exist
            target_dir = root_mount / "usr" / "bin"
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy qemu-arm-static to target
            qemu_target_path = target_dir / "qemu-arm-static"
            self.logger.info(f"Copying qemu-arm-static from {qemu_host_path} to {qemu_target_path}")
            import shutil
            shutil.copy2(qemu_host_path, qemu_target_path)
            
            # Make it executable
            os.chmod(qemu_target_path, 0o755)
            
            # Set up essential mounts for chroot
            mounts = [
                ("proc", root_mount / "proc", "proc"),
                ("sys", root_mount / "sys", "sysfs"),
                ("dev", root_mount / "dev", "devtmpfs"),
                ("dev/pts", root_mount / "dev/pts", "devpts")
            ]
            
            for name, mount_point, fs_type in mounts:
                # Create mount point if it doesn't exist
                if not mount_point.exists():
                    mount_point.mkdir(parents=True, exist_ok=True)
                    
                # Mount filesystem
                self.logger.debug(f"Mounting {name} at {mount_point}")
                mount_result = await asyncio.create_subprocess_exec(
                    'mount', '-t', fs_type, name, str(mount_point),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await mount_result.communicate()
                
                if mount_result.returncode != 0:
                    self.logger.warning(f"Failed to mount {name}: {stderr.decode()}")
            
            # Copy resolv.conf for network access
            shutil.copy2("/etc/resolv.conf", root_mount / "etc" / "resolv.conf")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting up chroot environment: {str(e)}")
            return False
    
    async def _cleanup_chroot(self, root_mount: Path) -> None:
        """
        Clean up chroot environment.
        
        Args:
            root_mount: Path to the mounted root filesystem
        """
        try:
            # Unmount filesystems in reverse order
            mounts = [
                (root_mount / "dev/pts"),
                (root_mount / "dev"),
                (root_mount / "sys"),
                (root_mount / "proc")
            ]
            
            for mount_point in mounts:
                self.logger.debug(f"Unmounting {mount_point}")
                unmount_result = await asyncio.create_subprocess_exec(
                    'umount', str(mount_point),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await unmount_result.communicate()
                
        except Exception as e:
            self.logger.warning(f"Error cleaning up chroot environment: {str(e)}")
    
    async def _run_in_chroot(self, root_mount: Path, command: str) -> bool:
        """
        Run a command in the chroot environment.
        
        Args:
            root_mount: Path to the mounted root filesystem
            command: Command to run
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Use a shell script to ensure proper environment
            script_content = f"""#!/bin/bash
set -e
export DEBIAN_FRONTEND=noninteractive
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
{command}
"""
            # Create script file in target filesystem
            script_path = root_mount / "tmp" / "install_script.sh"
            with open(script_path, "w") as f:
                f.write(script_content)
                
            # Make script executable
            os.chmod(script_path, 0o755)
            
            # Run the script in chroot
            self.logger.debug(f"Running in chroot: {command}")
            chroot_result = await asyncio.create_subprocess_exec(
                'chroot', str(root_mount), '/tmp/install_script.sh',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await chroot_result.communicate()
            
            # Log output
            if stdout:
                self.logger.debug(f"Command output: {stdout.decode()}")
            if stderr:
                self.logger.debug(f"Command error: {stderr.decode()}")
            
            return chroot_result.returncode == 0
            
        except Exception as e:
            self.logger.error(f"Error running command in chroot: {str(e)}")
            return False
    
    async def _configure_apt_sources(self, root_mount: Path) -> bool:
        """Configure APT sources"""
        try:
            # Write APT sources configuration
            sources_list = root_mount / "etc/apt/sources.list"
            with open(sources_list, "w") as f:
                f.write("""deb http://deb.debian.org/debian bookworm main contrib non-free
deb http://security.debian.org/debian-security bookworm-security main contrib non-free
deb http://deb.debian.org/debian bookworm-updates main contrib non-free
""")
            
            # Update APT
            if not await self._run_in_chroot(root_mount, "apt update"):
                self.logger.warning("APT update failed")
                return False
                
            return True
            
        except Exception as e:
            self.logger.warning(f"APT source configuration failed: {str(e)}")
            return False
    
    async def _install_packages(self, root_mount: Path) -> bool:
        """Install required packages"""
        try:
            # Install packages
            packages_str = " ".join(self.packages)
            install_cmd = f"apt install -y {packages_str}"
            
            if not await self._run_in_chroot(root_mount, install_cmd):
                self.logger.error("Package installation failed")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Package installation failed: {str(e)}")
            return False
