#!/usr/bin/env python3
"""
W4B software installation stage for Raspberry Pi image generator.
"""

import os
import sys
import asyncio
import shutil
import json
from pathlib import Path
from typing import Dict, Any, Optional

from core.stages.base import BuildStage

class W4BSoftwareStage(BuildStage):
    """
    Build stage for installing W4B software.
    """
    
    async def execute(self) -> bool:
        try:
            self.logger.info("Starting stage: W4BSoftwareStage")
            
            # Ensure mount points exist in state
            if "root_mount" not in self.state or "boot_mount" not in self.state:
                raise KeyError("Mount points not found in state")
            
            root_mount = self.state["root_mount"]
            boot_mount = self.state["boot_mount"]
            
            self.logger.debug(f"Root mount: {root_mount}")
            self.logger.debug(f"Boot mount: {boot_mount}")
            
            # Create W4B directories with verification
            w4b_dir = root_mount / "opt/w4b"
            sensor_manager_dir = w4b_dir / "sensorManager"
            config_dir = w4b_dir / "config"
            data_dir = w4b_dir / "data"
            
            # Create directories
            for directory in [w4b_dir, sensor_manager_dir, config_dir, data_dir]:
                directory.mkdir(parents=True, exist_ok=True)
                if not directory.exists():
                    self.logger.error(f"Failed to create directory: {directory}")
                    return False
                self.logger.debug(f"Created directory: {directory}")
                
            # Install sensor manager software
            self.logger.info("Installing sensor manager software")
            if not await self._install_sensor_manager(sensor_manager_dir):
                return False
            
            # Install configuration files
            self.logger.info("Installing configuration files")
            if not await self._install_configurations(config_dir):
                return False
            
            # Create systemd service files
            if not await self._create_systemd_services(root_mount, sensor_manager_dir):
                return False
            
            # Create sample data directory
            data_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info("Sample data directory created")
            
            # Create firstboot scripts
            if not await self._create_firstboot_scripts(boot_mount, root_mount):
                return False
            
            # Set proper permissions
            await self._set_permissions(root_mount)
            
            # Verify all required files exist
            if not self._verify_installation(root_mount, boot_mount):
                return False
            
            self.logger.info("W4B software installation completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"W4B software installation failed: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return False
    
    async def _install_sensor_manager(self, install_dir: Path) -> bool:
        """Install sensor manager code to the image."""
        try:
            # Check if we have sensor_data_collector.py in the repository
            repo_file = Path(__file__).parent.parent.parent.parent / "sensorManager/sensor_data_collector.py"
            
            if repo_file.exists():
                # Copy from repository
                collector_dest = install_dir / "sensor_data_collector.py"
                shutil.copy2(repo_file, collector_dest)
                collector_dest.chmod(0o755)  # Make executable
                self.logger.info(f"Copied sensor collector from repository: {repo_file}")
            else:
                # Create minimal sensor collector if repository file not found
                self._create_minimal_sensor_manager(install_dir)
                self.logger.info("Created minimal sensor manager")
            
            # Create the service file regardless of sensor manager source
            service_file = install_dir / "sensor_manager.service"
            with open(service_file, 'w') as f:
                f.write("""[Unit]
Description=W4B Sensor Manager
After=network.target postgresql.service

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/w4b/sensorManager
ExecStart=/usr/bin/python3 /opt/w4b/sensorManager/sensor_data_collector.py /opt/w4b/config/sensor_config.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
""")
            service_file.chmod(0o644)
            
            # Verify file exists
            if not (install_dir / "sensor_data_collector.py").exists():
                self.logger.error(f"Sensor collector file not created: {install_dir / 'sensor_data_collector.py'}")
                return False
                
            if not service_file.exists():
                self.logger.error(f"Service file not created: {service_file}")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to install sensor manager: {str(e)}")
            return False
    
    def _create_minimal_sensor_manager(self, install_dir: Path) -> None:
        """Create minimal sensor manager if no source code available."""
        sensor_script = install_dir / "sensor_data_collector.py"
        
        # Create minimal sensor collector script
        with open(sensor_script, 'w') as f:
            f.write("""#!/usr/bin/env python3
import time
import logging
import os
import sys
import yaml
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('w4b-sensor-manager')

def main():
    logger.info("Starting W4B Sensor Manager")
    
    config_path = "/opt/w4b/config/sensor_config.yaml"
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    
    if not os.path.exists(config_path):
        logger.error(f"Configuration file not found: {config_path}")
        return 1
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        logger.info(f"Loaded configuration for hive: {config.get('hive_id', 'unknown')}")
        
        # Simple placeholder service
        while True:
            logger.info("Sensor manager running...")
            time.sleep(60)
    
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
""")
        
        # Make it executable
        sensor_script.chmod(0o755)
    
    async def _install_configurations(self, config_dir: Path) -> bool:
        """Install configuration files to the image."""
        try:
            # Create sensor configuration
            sensor_config = config_dir / "sensor_config.yaml"
            
            with open(sensor_config, 'w') as f:
                f.write(f"""# W4B Sensor Configuration
version: 1.0.0
hive_id: "{self.state['config']['hive_id']}"
timezone: "{self.state['config']['system']['timezone']}"

collectors:
  base_path: /opt/w4b/collectors
  interval: {self.state['config'].get('services', {}).get('sensor_manager', {}).get('config', {}).get('interval', 60)}
  timeout: 30

storage:
  type: timescaledb
  host: localhost
  port: 5432
  database: {self.state['config'].get('services', {}).get('database', {}).get('database', 'hivedb')}
  user: {self.state['config'].get('services', {}).get('database', {}).get('username', 'hiveuser')}
  password: {self.state['config'].get('services', {}).get('database', {}).get('password', 'changeme')}
  retention_days: {self.state['config'].get('services', {}).get('database', {}).get('retention_days', 30)}

sensors:
  - id: temp_01
    name: "Temperature Sensor 1"
    type: temperature
    enabled: true
    interface:
      type: w1
      address: "28-*"
    collection:
      interval: 60
      retries: 3
    metrics:
      - name: temperature
        unit: celsius
        precision: 1

logging:
  version: 1
  formatters:
    standard:
      format: '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
  handlers:
    console:
      class: logging.StreamHandler
      formatter: standard
      level: INFO
    file:
      class: logging.handlers.RotatingFileHandler
      formatter: standard
      level: DEBUG
      filename: /var/log/w4b/sensors.log
      maxBytes: 10485760
      backupCount: 5
  loggers:
    sensors:
      level: {self.state['config'].get('services', {}).get('sensor_manager', {}).get('config', {}).get('logging', {}).get('level', 'INFO')}
      handlers: [console, file]
      propagate: false

metrics:
  prometheus:
    enabled: true
    port: 9100
""")
            
            # Verify file exists
            if not sensor_config.exists():
                self.logger.error(f"Sensor config file not created: {sensor_config}")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to install configurations: {str(e)}")
            return False
    
    async def _create_systemd_services(self, root_mount: Path, sensor_manager_dir: Path) -> bool:
        """Create systemd service files."""
        try:
            # Ensure systemd directory exists
            systemd_dir = root_mount / "etc/systemd/system"
            systemd_dir.mkdir(parents=True, exist_ok=True)
            
            # Get sensor manager service file path
            service_source_path = sensor_manager_dir / "sensor_manager.service"
            
            # Create symlink in systemd directory
            service_dest_path = systemd_dir / "sensor_manager.service"
            
            # Ensure the target service file exists first
            if not service_source_path.exists():
                self.logger.error(f"Source service file not found: {service_source_path}")
                return False
            
            # Create symlink or copy the file if symlink creation fails
            try:
                if service_dest_path.exists():
                    service_dest_path.unlink()
                
                # First try to create a symlink
                os.symlink(service_source_path, service_dest_path)
                self.logger.info(f"Created symlink to service file: {service_dest_path}")
            except Exception as e:
                self.logger.warning(f"Failed to create symlink, copying service file instead: {str(e)}")
                # If symlink fails, copy the file
                shutil.copy2(service_source_path, service_dest_path)
                self.logger.info(f"Copied service file to: {service_dest_path}")
            
            # Create log directory
            log_dir = root_mount / "var/log/w4b"
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # Verify files exist
            if not service_dest_path.exists():
                self.logger.error(f"Service file not installed: {service_dest_path}")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create systemd services: {str(e)}")
            return False
    
    async def _create_firstboot_scripts(self, boot_mount: Path, root_mount: Path) -> bool:
        """Create firstboot scripts for setting up services."""
        try:
            # Create firstboot script
            firstboot_path = boot_mount / "firstboot.sh"
            
            with open(firstboot_path, 'w') as f:
                f.write("""#!/bin/bash
# W4B firstboot setup script

# Create log directory if it doesn't exist
mkdir -p /var/log/w4b
chown -R pi:pi /var/log/w4b

# Enable and start services
systemctl daemon-reload
systemctl enable sensor_manager.service
systemctl start sensor_manager.service

# Set up database if PostgreSQL is installed
if [ -f /usr/bin/psql ]; then
    # Create database and user
    sudo -u postgres psql -c "CREATE USER hiveuser WITH PASSWORD 'changeme';"
    sudo -u postgres psql -c "CREATE DATABASE hivedb OWNER hiveuser;"
    
    # Enable TimescaleDB extension if available
    sudo -u postgres psql -d hivedb -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"
    
    # Create hypertable for sensor data
    sudo -u postgres psql -d hivedb -c "
    CREATE TABLE IF NOT EXISTS sensor_data (
        time TIMESTAMPTZ NOT NULL,
        hive_id TEXT NOT NULL,
        sensor_id TEXT NOT NULL,
        metric_name TEXT NOT NULL,
        value DOUBLE PRECISION NOT NULL,
        unit TEXT NOT NULL,
        status TEXT DEFAULT 'valid'
    );
    SELECT create_hypertable('sensor_data', 'time', if_not_exists => TRUE);"
fi

# Remove this script after execution
rm /boot/firstboot.sh
""")
            
            # Make it executable
            firstboot_path.chmod(0o755)
            
            # Modify rc.local to run firstboot script
            rc_local_path = root_mount / "etc/rc.local"
            
            if rc_local_path.exists():
                with open(rc_local_path, 'r') as f:
                    content = f.read()
                
                if "firstboot.sh" not in content:
                    # Add firstboot script execution before exit 0
                    content = content.replace("exit 0", "\n# Run firstboot script if exists\nif [ -f /boot/firstboot.sh ]; then\n  /boot/firstboot.sh\nfi\n\nexit 0")
                    
                    with open(rc_local_path, 'w') as f:
                        f.write(content)
            else:
                # Create rc.local if it doesn't exist
                with open(rc_local_path, 'w') as f:
                    f.write("""#!/bin/bash
# W4B rc.local file

# Run firstboot script if exists
if [ -f /boot/firstboot.sh ]; then
  /boot/firstboot.sh
fi

exit 0
""")
                
                # Make it executable
                rc_local_path.chmod(0o755)
            
            # Verify files exist
            if not firstboot_path.exists():
                self.logger.error(f"Firstboot script not created: {firstboot_path}")
                return False
                
            if not rc_local_path.exists():
                self.logger.error(f"rc.local file not created: {rc_local_path}")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create firstboot scripts: {str(e)}")
            return False
    
    async def _set_permissions(self, root_mount: Path) -> None:
        """Set correct permissions for installed files."""
        try:
            # Set ownership for W4B directory
            w4b_dir = root_mount / "opt/w4b"
            
            # Set proper permissions using chown command
            # Note: This is a shell command that runs on the host, not in the chroot
            process = await asyncio.create_subprocess_exec(
                'chown', '-R', '1000:1000', str(w4b_dir),  # 1000:1000 is typically pi:pi
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                self.logger.warning(f"Failed to set ownership: {stderr.decode()}")
                
            # Make sure log directory has correct permissions too
            log_dir = root_mount / "var/log/w4b"
            if log_dir.exists():
                process = await asyncio.create_subprocess_exec(
                    'chown', '-R', '1000:1000', str(log_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                if process.returncode != 0:
                    self.logger.warning(f"Failed to set log directory ownership: {stderr.decode()}")
                    
        except Exception as e:
            self.logger.warning(f"Error setting permissions: {str(e)}")
    
    def _verify_installation(self, root_mount: Path, boot_mount: Path) -> bool:
        """Verify that all required files and services were installed correctly."""
        required_files = [
            root_mount / "opt/w4b/sensorManager/sensor_data_collector.py",
            root_mount / "opt/w4b/sensorManager/sensor_manager.service",
            root_mount / "opt/w4b/config/sensor_config.yaml",
            root_mount / "etc/systemd/system/sensor_manager.service",
            boot_mount / "firstboot.sh"
        ]
        
        required_dirs = [
            root_mount / "opt/w4b",
            root_mount / "opt/w4b/sensorManager",
            root_mount / "opt/w4b/config",
            root_mount / "opt/w4b/data",
            root_mount / "var/log/w4b"
        ]
        
        # Verify directories
        for directory in required_dirs:
            if not directory.exists():
                self.logger.error(f"Required directory not found: {directory}")
                return False
                
        # Verify files
        for file_path in required_files:
            if not file_path.exists():
                self.logger.error(f"Required file not found: {file_path}")
                return False
                
        self.logger.info("All required files and directories verified")
        return True
