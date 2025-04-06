#!/usr/bin/env python3
"""
Software installation stage for Raspberry Pi image generator.

This stage prepares firstboot scripts that will install required software
packages when the Raspberry Pi boots for the first time.
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
    Build stage for preparing software installation scripts.
    
    Instead of using QEMU to install packages directly, this stage
    creates firstboot scripts that will run when the Raspberry Pi boots
    for the first time.
    """
    
    async def execute(self) -> bool:
        try:
            self.logger.info("Starting stage: SoftwareInstallStage")
            
            # Check for required state values
            required_keys = ["boot_mount", "root_mount"]
            for key in required_keys:
                if key not in self.state:
                    raise KeyError(f"Missing required state value: {key}")
            
            # Get mount points from state
            boot_mount = self.state["boot_mount"]
            root_mount = self.state["root_mount"]
            
            # Verify mount points exist and are valid
            if not self._verify_mount_points(boot_mount, root_mount):
                raise ValueError(f"Mount points are invalid: boot={boot_mount}, root={root_mount}")
            
            # Get software packages to install
            software_config = self.state["config"].get("software", {})
            system_packages = software_config.get("packages", [])
            python_packages = software_config.get("python_packages", [])
            
            # Create firstboot script
            await self._create_firstboot_script(boot_mount, root_mount, system_packages, python_packages)
            
            # Configure rc.local to run firstboot script
            await self._configure_rc_local(root_mount)
            
            # Create systemd service as backup method
            await self._create_systemd_service(root_mount)
            
            self.logger.info("Software installation scripts created successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Software installation failed: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return False
    
    def _verify_mount_points(self, boot_mount: Path, root_mount: Path) -> bool:
        """Verify that mount points exist and are valid."""
        # Check that paths exist
        if not Path(boot_mount).exists():
            self.logger.error(f"Boot mount point does not exist: {boot_mount}")
            return False
            
        if not Path(root_mount).exists():
            self.logger.error(f"Root mount point does not exist: {root_mount}")
            return False
            
        # Check for essential files/directories that should be in these partitions
        try:
            # Check boot partition (should contain config.txt or cmdline.txt)
            boot_files = list(Path(boot_mount).glob("*"))
            if not boot_files:
                self.logger.error(f"Boot mount point appears empty: {boot_mount}")
                return False
                
            if not (Path(boot_mount) / "config.txt").exists() and not (Path(boot_mount) / "cmdline.txt").exists():
                self.logger.warning(f"Boot mount point may not be valid - missing expected files: {boot_mount}")
                # Continue anyway as this might be a different OS version
                
            # Check root partition (should contain /etc directory)
            if not (Path(root_mount) / "etc").exists():
                self.logger.error(f"Root mount point missing /etc directory: {root_mount}")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error verifying mount points: {str(e)}")
            return False
    
    async def _create_firstboot_script(self, boot_mount: Path, root_mount: Path, 
                                       system_packages: List[str], python_packages: List[str]) -> None:
        """Create firstboot script for software installation."""
        self.logger.info("Creating firstboot installation script")
        
        # Create default packages list if none provided
        if not system_packages:
            system_packages = [
                "git",
                "python3",
                "python3-pip",
                "python3-venv",
                "postgresql",
                "wireguard",
                "prometheus-node-exporter"
            ]
        
        # Create firstboot.sh script in boot partition
        firstboot_path = boot_mount / "firstboot.sh"
        
        with open(firstboot_path, "w") as f:
            f.write("""#!/bin/bash
# W4B First Boot Installation Script
# This script runs on first boot to install required software

# Log everything to a file
exec > /boot/firstboot.log 2>&1

echo "Starting W4B firstboot installation at $(date)"

# Configure APT sources
echo "Configuring APT sources..."
cat > /etc/apt/sources.list << EOF
deb http://deb.debian.org/debian bullseye main contrib non-free
deb http://security.debian.org/debian-security bullseye-security main contrib non-free
deb http://deb.debian.org/debian bullseye-updates main contrib non-free
EOF

# Update package list and upgrade system
echo "Updating package lists..."
apt-get update
apt-get upgrade -y

# Install required packages
echo "Installing system packages..."
DEBIAN_FRONTEND=noninteractive apt-get install -y """)
            f.write(" ".join(system_packages))
            f.write("\n\n")
            
            # Add TimescaleDB repository if needed
            if "postgresql" in " ".join(system_packages) and "timescaledb" in " ".join(system_packages):
                f.write("""
# Configure TimescaleDB repository
echo "Configuring TimescaleDB repository..."
apt-get install -y gnupg postgresql-common apt-transport-https lsb-release wget
/usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y
echo "deb https://packagecloud.io/timescale/timescaledb/debian/ $(lsb_release -c -s) main" > /etc/apt/sources.list.d/timescaledb.list
wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | apt-key add -
apt-get update
apt-get install -y timescaledb-2-postgresql-13
echo "shared_preload_libraries = 'timescaledb'" >> /etc/postgresql/13/main/postgresql.conf
systemctl restart postgresql
""")
            
            # Install Python packages
            if python_packages:
                f.write("# Install Python packages\n")
                f.write("echo \"Installing Python packages...\"\n")
                f.write(f"pip3 install {' '.join(python_packages)}\n\n")
            
            # Create necessary directories
            f.write("""
# Create required directories
echo "Creating W4B directories..."
mkdir -p /opt/w4b/sensor_manager
mkdir -p /opt/w4b/config
mkdir -p /var/log/w4b
chown -R pi:pi /opt/w4b
chown -R pi:pi /var/log/w4b
chmod 755 /opt/w4b/sensor_manager
chmod 755 /var/log/w4b

# Enable required services
echo "Enabling required services..."
systemctl daemon-reload
systemctl enable postgresql
systemctl enable prometheus-node-exporter

# Mark installation as complete
echo "Installation completed at $(date)"
touch /boot/installation_completed

# Remove firstboot script to prevent re-execution
echo "Removing firstboot script..."
rm /boot/firstboot.sh

echo "W4B firstboot installation complete"
exit 0
""")
        
        # Make script executable
        firstboot_path.chmod(0o755)
        self.logger.info(f"Created firstboot script at {firstboot_path}")
    
    async def _configure_rc_local(self, root_mount: Path) -> None:
        """Configure rc.local to run firstboot script on first boot."""
        self.logger.info("Configuring rc.local to run firstboot script")
        
        rc_local_path = root_mount / "etc/rc.local"
        
        # Ensure /etc directory exists
        etc_dir = root_mount / "etc"
        if not etc_dir.exists():
            self.logger.warning(f"Creating missing /etc directory in root mount: {root_mount}")
            etc_dir.mkdir(parents=True, exist_ok=True)
        
        # Create content for rc.local
        rc_local_content = """#!/bin/sh -e
#
# rc.local
#
# This script is executed at the end of each multiuser runlevel.
# Make sure that the script will "exit 0" on success or any other
# value on error.

# Run firstboot script if it exists and hasn't been run before
if [ -f /boot/firstboot.sh ] && [ ! -f /boot/installation_completed ]; then
  echo "Running W4B firstboot installation script..."
  /boot/firstboot.sh
fi

exit 0
"""
        
        # Write or append to rc.local
        with open(rc_local_path, "w") as f:
            f.write(rc_local_content)
        
        # Make rc.local executable
        rc_local_path.chmod(0o755)
        self.logger.info("Configured rc.local to run firstboot script")
    
    async def _create_systemd_service(self, root_mount: Path) -> None:
        """Create systemd service for firstboot as a backup method."""
        self.logger.info("Creating systemd service for firstboot")
        
        systemd_dir = root_mount / "etc/systemd/system"
        systemd_dir.mkdir(parents=True, exist_ok=True)
        
        service_path = systemd_dir / "w4b-firstboot.service"
        with open(service_path, "w") as f:
            f.write("""[Unit]
Description=W4B First Boot Installation
ConditionPathExists=/boot/firstboot.sh
ConditionPathExists=!/boot/installation_completed
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/boot/firstboot.sh
RemainAfterExit=yes
TimeoutSec=1800

[Install]
WantedBy=multi-user.target
""")
        
        # Create symlink to enable the service
        enable_path = root_mount / "etc/systemd/system/multi-user.target.wants/w4b-firstboot.service"
        enable_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Use relative path for symlink
        if not enable_path.exists():
            try:
                os.symlink("../w4b-firstboot.service", enable_path)
            except Exception as e:
                self.logger.warning(f"Failed to create symlink, using alternative method: {e}")
                with open(enable_path, "w") as f:
                    f.write("[Link]\nPath=/etc/systemd/system/w4b-firstboot.service\n")
        
        self.logger.info("Created and enabled systemd service for firstboot")
