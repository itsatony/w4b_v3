#!/usr/bin/env python3
"""
Software installation stage for Raspberry Pi image generator.
"""

import os
import sys
import asyncio
import shutil
from pathlib import Path
from typing import Dict, Any, List

from core.stages.base import BuildStage

class SoftwareInstallStage(BuildStage):
    """
    Build stage for installing software packages on the image.
    """
    
    async def execute(self) -> bool:
        try:
            self.logger.info("Starting stage: SoftwareInstallStage")
            
            # Check for required state values
            required_keys = ["image_path", "boot_mount", "root_mount"]
            for key in required_keys:
                if key not in self.state:
                    raise KeyError(f"Missing required state value: {key}")
            
            # Get mount points from state
            boot_mount = self.state["boot_mount"]
            root_mount = self.state["root_mount"]
            
            # Get software packages to install
            software_config = self.state["config"].get("software", {})
            system_packages = software_config.get("packages", [])
            python_packages = software_config.get("python_packages", [])
            
            # Add repositories and install packages
            await self._configure_apt_sources(root_mount)
            await self._install_packages(root_mount, system_packages)
            await self._install_python_packages(root_mount, python_packages)
            
            # Copy additional files
            await self._copy_additional_files(boot_mount, root_mount)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Software installation failed: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return False
    
    async def _configure_apt_sources(self, root_mount: Path) -> None:
        """Configure APT sources and update packages."""
        self.logger.info("Configuring APT sources")
        
        # Update package lists using chroot
        update_cmd = [
            'chroot', str(root_mount),
            'apt-get', 'update', '-y'
        ]
        
        process = await asyncio.create_subprocess_exec(
            *update_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            self.logger.warning(f"APT update failed: {stderr.decode()}")
            self.logger.debug(f"APT update stdout: {stdout.decode()}")
    
    async def _install_packages(self, root_mount: Path, packages: List[str]) -> None:
        """Install system packages using APT."""
        if not packages:
            self.logger.info("No system packages to install")
            return
        
        self.logger.info(f"Installing {len(packages)} system packages")
        
        # Prepare for install by copying qemu-arm-static
        qemu_src = "/usr/bin/qemu-arm-static"
        qemu_dest = root_mount / "usr/bin/qemu-arm-static"
        
        if os.path.exists(qemu_src) and not qemu_dest.exists():
            shutil.copy2(qemu_src, qemu_dest)
        
        # Install packages using chroot
        install_cmd = [
            'chroot', str(root_mount),
            'apt-get', 'install', '-y'
        ] + packages
        
        process = await asyncio.create_subprocess_exec(
            *install_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            self.logger.warning(f"Package installation failed: {stderr.decode()}")
            self.logger.debug(f"Package installation stdout: {stdout.decode()}")
    
    async def _install_python_packages(self, root_mount: Path, packages: List[str]) -> None:
        """Install Python packages using pip."""
        if not packages:
            self.logger.info("No Python packages to install")
            return
        
        self.logger.info(f"Installing {len(packages)} Python packages")
        
        # Install packages using chroot and pip
        install_cmd = [
            'chroot', str(root_mount),
            'pip3', 'install'
        ] + packages
        
        process = await asyncio.create_subprocess_exec(
            *install_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            self.logger.warning(f"Python package installation failed: {stderr.decode()}")
            self.logger.debug(f"Python package installation stdout: {stdout.decode()}")
    
    async def _copy_additional_files(self, boot_mount: Path, root_mount: Path) -> None:
        """Copy additional files to the image."""
        self.logger.info("Copying additional files to the image")
        
        # Create required directories
        config_dir = root_mount / "opt/w4b/config"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy sensor manager files if available
        src_dir = Path(__file__).parent.parent.parent / "files/sensorManager"
        if src_dir.exists():
            dest_dir = root_mount / "opt/w4b/sensorManager"
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy files
            for item in src_dir.glob("**/*"):
                if item.is_file():
                    rel_path = item.relative_to(src_dir)
                    dest_path = dest_dir / rel_path
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest_path)
