#!/usr/bin/env python3
"""
Software installation stage for the W4B Raspberry Pi Image Generator.

This module implements the software installation stage of the build pipeline,
responsible for installing required packages and dependencies.
"""

import asyncio
import os
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional

from core.stages.base import BuildStage
from utils.error_handling import ImageBuildError


class SoftwareInstallStage(BuildStage):
    """
    Build stage for installing required software.
    
    This stage is responsible for installing all required software packages
    and dependencies on the target image.
    
    Attributes:
        name (str): Name of the stage
        state (Dict[str, Any]): Shared pipeline state
        logger (logging.Logger): Logger instance
        circuit_breaker (CircuitBreaker): Circuit breaker for fault tolerance
    """
    
    async def execute(self) -> bool:
        """
        Execute the software installation stage.
        
        Returns:
            bool: True if installation succeeded, False otherwise
        """
        try:
            # Get paths from state
            boot_mount = self.state["boot_mount"]
            root_mount = self.state["root_mount"]
            
            # Install system packages
            await self._install_system_packages(root_mount)
            
            # Install Python packages
            await self._install_python_packages(root_mount)
            
            # Configure package sources
            await self._configure_package_sources(root_mount)
            
            self.logger.info("Software installation completed successfully")
            return True
            
        except Exception as e:
            self.logger.exception(f"Software installation failed: {str(e)}")
            return False
    
    async def _install_system_packages(self, root_mount: Path) -> None:
        """
        Configure required system packages.
        
        This method adds package names to the firstboot script for installation
        during the first boot.
        
        Args:
            root_mount: Path to the root file system
        """
        # Get package list
        packages = self.state["config"]["software"]["packages"]
        if not packages:
            self.logger.info("No system packages specified for installation")
            return
        
        self.logger.info(f"Adding {len(packages)} system packages for installation")
        
        # Generate package list string
        package_list = " ".join(packages)
        
        # Add to firstboot script
        firstboot_path = Path(self.state["boot_mount"]) / "firstboot.sh"
        
        with open(firstboot_path, "r") as f:
            content = f.readlines()
        
        # Find position to insert package installation (before "Mark setup as complete")
        insert_pos = 0
        for i, line in enumerate(content):
            if "Mark setup as complete" in line:
                insert_pos = i
                break
        
        # Create package installation section
        install_lines = [
            "# Install required packages\n",
            f"echo \"Installing system packages: {package_list}\"\n",
            f"apt-get install -y {package_list}\n",
            "\n"
        ]
        
        # Insert installation lines
        content = content[:insert_pos] + install_lines + content[insert_pos:]
        
        # Write back to file
        with open(firstboot_path, "w") as f:
            f.writelines(content)
    
    async def _install_python_packages(self, root_mount: Path) -> None:
        """
        Configure required Python packages.
        
        This method adds pip package installation to the firstboot script.
        
        Args:
            root_mount: Path to the root file system
        """
        # Get Python package list
        python_packages = self.state["config"]["software"].get("python_packages", [])
        if not python_packages:
            self.logger.info("No Python packages specified for installation")
            return
        
        # Get requirements file if specified
        requirements_file = self.state["config"]["software"].get("python_requirements", {}).get("file")
        
        self.logger.info(f"Adding Python packages for installation: {len(python_packages)} packages")
        
        # Add to firstboot script
        firstboot_path = Path(self.state["boot_mount"]) / "firstboot.sh"
        
        with open(firstboot_path, "r") as f:
            content = f.readlines()
        
        # Find position to insert package installation (before "Mark setup as complete")
        insert_pos = 0
        for i, line in enumerate(content):
            if "Mark setup as complete" in line:
                insert_pos = i
                break
        
        # Create pip installation section
        install_lines = [
            "# Install Python packages\n",
            "echo \"Installing Python packages\"\n"
        ]
        
        # Add pip installation if needed
        install_lines.append("apt-get install -y python3-pip\n")
        
        # Add individual packages
        if python_packages:
            package_list = " ".join(python_packages)
            install_lines.append(f"pip3 install {package_list}\n")
        
        # Add requirements file if specified
        if requirements_file:
            # Copy requirements file to boot
            src_requirements = Path(requirements_file)
            if src_requirements.exists():
                dst_requirements = Path(self.state["boot_mount"]) / "requirements.txt"
                shutil.copy(src_requirements, dst_requirements)
                install_lines.append("pip3 install -r /boot/requirements.txt\n")
                install_lines.append("rm /boot/requirements.txt\n")
        
        install_lines.append("\n")
        
        # Insert installation lines
        content = content[:insert_pos] + install_lines + content[insert_pos:]
        
        # Write back to file
        with open(firstboot_path, "w") as f:
            f.writelines(content)
    
    async def _configure_package_sources(self, root_mount: Path) -> None:
        """
        Configure package sources.
        
        Args:
            root_mount: Path to the root file system
        """
        # Example: add TimescaleDB repository if we need it
        if "timescaledb" in " ".join(self.state["config"]["software"].get("packages", [])):
            self.logger.info("Adding TimescaleDB package repository")
            
            # Create apt sources list file for TimescaleDB
            sources_dir = root_mount / "etc/apt/sources.list.d"
            sources_dir.mkdir(exist_ok=True)
            
            with open(sources_dir / "timescaledb.list", "w") as f:
                f.write("deb https://packagecloud.io/timescale/timescaledb/debian/ bullseye main\n")
            
            # Add repository key in firstboot script
            firstboot_path = Path(self.state["boot_mount"]) / "firstboot.sh"
            
            with open(firstboot_path, "r") as f:
                content = f.readlines()
            
            # Find position to insert apt update (beginning of the script, after first few lines)
            insert_pos = 3  # After shebang, set -e, and first echo
            
            # Create repo setup section
            repo_lines = [
                "# Add TimescaleDB repository\n",
                "echo \"Adding TimescaleDB repository\"\n",
                "apt-get install -y gnupg2\n",
                "apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 1005589CB00BBEA3\n",
                "apt-get update\n",
                "\n"
            ]
            
            # Insert repository lines
            content = content[:insert_pos] + repo_lines + content[insert_pos:]
            
            # Write back to file
            with open(firstboot_path, "w") as f:
                f.writelines(content)
