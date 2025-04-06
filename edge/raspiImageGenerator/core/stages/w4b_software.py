#!/usr/bin/env python3
"""
W4B software installation stage for Raspberry Pi image generator.

This stage installs and configures all the W4B software components on the Raspberry Pi image,
including the sensor manager, configuration files, and necessary services.
"""

import os
import sys
import asyncio
import shutil
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from core.stages.base import BuildStage

class W4BSoftwareStage(BuildStage):
    """
    Build stage for installing W4B software components on the Raspberry Pi image.
    
    This stage performs the following operations:
    - Creates necessary directories
    - Installs sensor manager software
    - Creates configuration files
    - Sets up systemd services
    - Creates firstboot scripts
    - Verifies installation
    """
    
    async def execute(self) -> bool:
        """
        Execute the W4B software installation stage.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.logger.info("Starting stage: W4BSoftwareStage")
            
            # Ensure mount points exist in state
            if "root_mount" not in self.state or "boot_mount" not in self.state:
                self.logger.error("Mount points not found in state")
                return False
            
            root_mount = self.state["root_mount"]
            boot_mount = self.state["boot_mount"]
            
            # Critical debugging to diagnose the path issue
            self.logger.info(f"Working with root_mount: {root_mount} (exists: {root_mount.exists()})")
            self.logger.info(f"Working with boot_mount: {boot_mount} (exists: {boot_mount.exists()})")
            
            # Check if validation is accessing the same paths
            if "validation" in self.state["config"]:
                self.logger.info(f"Validation config: {self.state['config']['validation']}")
            
            # Create all necessary directories - with immediate verification
            if not await self._create_directories(root_mount):
                return False
            
            # Verify directories were actually created
            w4b_dir = root_mount / "opt/w4b"
            sensor_dir = root_mount / "opt/w4b/sensorManager"
            config_dir = root_mount / "opt/w4b/config"
            
            self.logger.info(f"After directory creation: w4b_dir exists: {w4b_dir.exists()}")
            self.logger.info(f"After directory creation: sensor_dir exists: {sensor_dir.exists()}")
            self.logger.info(f"After directory creation: config_dir exists: {config_dir.exists()}")
            
            
            # Create all necessary directories - with immediate verification
            if not await self._create_directories(root_mount):
                return False
            
            # Verify directories were actually created
            w4b_dir = root_mount / "opt/w4b"
            sensor_dir = root_mount / "opt/w4b/sensorManager"
            config_dir = root_mount / "opt/w4b/config"
            
            self.logger.info(f"After directory creation: w4b_dir exists: {w4b_dir.exists()}")
            self.logger.info(f"After directory creation: sensor_dir exists: {sensor_dir.exists()}")
            self.logger.info(f"After directory creation: config_dir exists: {config_dir.exists()}")
            
            # Install sensor manager software
            self.logger.info("Installing sensor manager software")
            if not await self._install_sensor_manager(root_mount):
                return False
            
            # Install configuration files
            self.logger.info("Installing configuration files")
            if not await self._install_configurations(root_mount):
                return False
            
            # Create systemd service files
            if not await self._create_systemd_services(root_mount):
                return False
            
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
    
    async def _create_directories(self, root_mount: Path) -> bool:
        """
        Create all necessary directories for W4B software.
        
        Args:
            root_mount: Path to the root filesystem mount point
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Define required directories
            directories = [
                root_mount / "opt/w4b",
                root_mount / "opt/w4b/sensorManager",
                root_mount / "opt/w4b/config",
                root_mount / "opt/w4b/data",
                root_mount / "var/log/w4b",
            ]
            
            # Create each directory
            for directory in directories:
                directory.mkdir(parents=True, exist_ok=True)
                if not directory.exists():
                    self.logger.error(f"Failed to create directory: {directory}")
                    return False
                self.logger.debug(f"Created directory: {directory}")
            
            self.logger.info("All required directories created successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create directories: {str(e)}")
            return False
    
    async def _install_sensor_manager(self, root_mount: Path) -> bool:
        """
        Install the sensor manager software.
        
        Args:
            root_mount: Path to the root filesystem mount point
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Paths for sensor manager files
            sensor_manager_dir = root_mount / "opt/w4b/sensorManager"
            
            # First check if we have source files in the repository
            source_paths = [
                Path(__file__).parent.parent.parent.parent / "sensorManager",
                Path("/home/itsatony/code/w4b_v3/edge/sensorManager")
            ]
            
            # Find source path
            source_path = None
            for path in source_paths:
                if path.exists() and (path / "sensor_data_collector.py").exists():
                    source_path = path
                    self.logger.info(f"Found sensor manager source in: {source_path}")
                    break
            
            # If source found, copy files
            if source_path:
                # Copy sensor_data_collector.py
                collector_source = source_path / "sensor_data_collector.py"
                collector_dest = sensor_manager_dir / "sensor_data_collector.py"
                shutil.copy2(collector_source, collector_dest)
                collector_dest.chmod(0o755)  # Make executable
                self.logger.info(f"Copied sensor collector from: {collector_source}")
                
                # Copy config files if they exist
                config_source = source_path / "sensor_config.yaml"
                if config_source.exists():
                    config_dest = root_mount / "opt/w4b/config/sensor_config.yaml"
                    shutil.copy2(config_source, config_dest)
                    self.logger.info(f"Copied sensor config from: {config_source}")
            else:
                # Create minimal sensor manager implementation
                self.logger.warning("No sensor manager source found, creating minimal implementation")
                await self._create_minimal_sensor_manager(sensor_manager_dir, root_mount)
            
            # Verify files were created
            if not (sensor_manager_dir / "sensor_data_collector.py").exists():
                self.logger.error("Failed to create sensor data collector script")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to install sensor manager: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return False
    
    async def _create_minimal_sensor_manager(self, sensor_manager_dir: Path, root_mount: Path) -> None:
        """
        Create a minimal sensor manager implementation if source files are not available.
        
        Args:
            sensor_manager_dir: Path to the sensor manager directory
            root_mount: Path to the root filesystem mount point
        """
        # Create sensor data collector script
        collector_path = sensor_manager_dir / "sensor_data_collector.py"
        with open(collector_path, 'w') as f:
            f.write("""#!/usr/bin/env python3
\"\"\"
W4B Sensor Manager - Minimal Implementation
\"\"\"

import time
import logging
import os
import sys
import yaml
import json
from datetime import datetime
from pathlib import Path

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/var/log/w4b/sensor_manager.log')
    ]
)
logger = logging.getLogger('w4b-sensor-manager')

class SensorManager:
    \"\"\"Minimal sensor manager implementation.\"\"\"
    
    def __init__(self, config_path):
        \"\"\"Initialize the sensor manager with configuration.\"\"\"
        self.config_path = config_path
        self.config = {}
        self.sensors = {}
        self.running = False
        
    def load_config(self):
        \"\"\"Load configuration from YAML file.\"\"\"
        try:
            logger.info(f"Loading configuration from {self.config_path}")
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f)
            logger.info(f"Loaded configuration for hive: {self.config.get('hive_id', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"Failed to load configuration: {str(e)}")
            return False
    
    def initialize(self):
        \"\"\"Initialize sensors and services.\"\"\"
        try:
            logger.info("Initializing sensor manager")
            if not self.load_config():
                return False
                
            # Create data directory if it doesn't exist
            data_dir = Path("/opt/w4b/data")
            data_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize sensors (dummy implementation)
            for sensor in self.config.get('sensors', []):
                sensor_id = sensor.get('id', 'unknown')
                sensor_type = sensor.get('type', 'unknown')
                logger.info(f"Initializing sensor: {sensor_id} (type: {sensor_type})")
                self.sensors[sensor_id] = {
                    'type': sensor_type,
                    'last_value': None,
                    'last_read': None,
                    'config': sensor
                }
            
            logger.info(f"Initialized {len(self.sensors)} sensors")
            return True
        except Exception as e:
            logger.error(f"Initialization error: {str(e)}")
            return False
    
    def run(self):
        \"\"\"Run the main sensor collection loop.\"\"\"
        try:
            logger.info("Starting sensor collection")
            self.running = True
            
            while self.running:
                current_time = datetime.now().isoformat()
                logger.info(f"Collection cycle at {current_time}")
                
                # Collect data from each sensor (dummy implementation)
                for sensor_id, sensor in self.sensors.items():
                    try:
                        # Generate dummy value between 20-25 degrees
                        import random
                        value = round(20 + 5 * random.random(), 2)
                        
                        # Simulate sensor reading
                        logger.info(f"Sensor {sensor_id} reading: {value}")
                        
                        # Update sensor state
                        sensor['last_value'] = value
                        sensor['last_read'] = current_time
                        
                        # Write to log file as placeholder for database
                        data_file = Path(f"/opt/w4b/data/{sensor_id}_data.log")
                        with open(data_file, 'a') as f:
                            f.write(f"{current_time},{value}\\n")
                    except Exception as e:
                        logger.error(f"Error reading sensor {sensor_id}: {str(e)}")
                
                # Sleep according to configuration
                collection_interval = self.config.get('collectors', {}).get('interval', 60)
                logger.info(f"Sleeping for {collection_interval} seconds")
                time.sleep(collection_interval)
        except KeyboardInterrupt:
            logger.info("Stopping due to keyboard interrupt")
        except Exception as e:
            logger.error(f"Unexpected error in collection loop: {str(e)}")
        finally:
            self.running = False
            logger.info("Sensor collection stopped")
            
    def stop(self):
        \"\"\"Stop the sensor manager.\"\"\"
        logger.info("Stopping sensor manager")
        self.running = False

def main():
    \"\"\"Main entry point.\"\"\"
    logger.info("Starting W4B Sensor Manager")
    
    # Get config path from arguments or use default
    config_path = "/opt/w4b/config/sensor_config.yaml"
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    
    if not os.path.exists(config_path):
        logger.error(f"Configuration file not found: {config_path}")
        return 1
    
    try:
        # Create and initialize sensor manager
        manager = SensorManager(config_path)
        if not manager.initialize():
            logger.error("Failed to initialize sensor manager")
            return 1
        
        # Run collection loop
        manager.run()
    except KeyboardInterrupt:
        logger.info("Shutting down due to keyboard interrupt...")
    except Exception as e:
        logger.error(f"Critical error: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
""")
        collector_path.chmod(0o755)
        
        # Create default sensor config if it doesn't exist
        config_dir = root_mount / "opt/w4b/config"
        config_path = config_dir / "sensor_config.yaml"
        if not config_path.exists():
            with open(config_path, 'w') as f:
                f.write(f"""# W4B Sensor Configuration - Minimal Default
version: 1.0.0
hive_id: "{self.state['config']['hive_id']}"
timezone: "{self.state['config']['system']['timezone']}"

collectors:
  base_path: /opt/w4b/collectors
  interval: 60
  timeout: 30

storage:
  type: timescaledb
  host: localhost
  port: 5432
  database: hivedb
  user: hiveuser
  password: changeme
  retention_days: 30

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
      level: INFO
      handlers: [console, file]
      propagate: false

metrics:
  prometheus:
    enabled: true
    port: 9100
""")
            self.logger.info("Created default sensor configuration")
            
        # Create systemd service file
        self._create_service_file(sensor_manager_dir)
        
    def _create_service_file(self, sensor_manager_dir: Path) -> None:
        """
        Create the systemd service file for the sensor manager.
        
        Args:
            sensor_manager_dir: Path to the sensor manager directory
        """
        service_file = sensor_manager_dir / "sensor_manager.service"
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
        self.logger.info("Created sensor manager service file")
    
    async def _install_configurations(self, root_mount: Path) -> bool:
        """
        Install configuration files.
        
        Args:
            root_mount: Path to the root filesystem mount point
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            config_dir = root_mount / "opt/w4b/config"
            sensor_config = config_dir / "sensor_config.yaml"
            
            # Skip if config already exists (e.g., copied from source)
            if sensor_config.exists():
                self.logger.info("Sensor configuration already exists, skipping creation")
                return True
            
            # Create sensor configuration
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
                
            self.logger.info("Created sensor configuration file")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to install configurations: {str(e)}")
            return False
    
    async def _create_systemd_services(self, root_mount: Path) -> bool:
        """
        Create systemd service files.
        
        Args:
            root_mount: Path to the root filesystem mount point
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure systemd directory exists
            systemd_dir = root_mount / "etc/systemd/system"
            systemd_dir.mkdir(parents=True, exist_ok=True)
            
            # Source service file path
            service_source_path = root_mount / "opt/w4b/sensorManager/sensor_manager.service"
            
            # If service file doesn't exist, create it
            if not service_source_path.exists():
                sensor_manager_dir = root_mount / "opt/w4b/sensorManager"
                self._create_service_file(sensor_manager_dir)
            
            # Create symlink in systemd directory
            service_dest_path = systemd_dir / "sensor_manager.service"
            
            # Make sure source file exists now
            if not service_source_path.exists():
                self.logger.error(f"Service file does not exist: {service_source_path}")
                return False
            
            # Create symlink or copy file
            try:
                # Remove existing symlink/file if it exists
                if service_dest_path.exists():
                    service_dest_path.unlink()
                
                # Try to create symlink first
                os.symlink(service_source_path, service_dest_path)
                self.logger.info(f"Created symlink to service file: {service_dest_path}")
            except Exception as e:
                # Fall back to copying file
                self.logger.warning(f"Failed to create symlink, copying service file instead: {str(e)}")
                shutil.copy2(service_source_path, service_dest_path)
                self.logger.info(f"Copied service file to: {service_dest_path}")
            
            # Verify file exists
            if not service_dest_path.exists():
                self.logger.error(f"Service file not installed: {service_dest_path}")
                return False
                
            self.logger.info("Created systemd service files")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create systemd services: {str(e)}")
            return False
    
    async def _create_firstboot_scripts(self, boot_mount: Path, root_mount: Path) -> bool:
        """
        Create first boot scripts.
        
        Args:
            boot_mount: Path to the boot partition mount point
            root_mount: Path to the root filesystem mount point
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create firstboot script on boot partition
            firstboot_path = boot_mount / "firstboot.sh"
            
            with open(firstboot_path, 'w') as f:
                f.write("""#!/bin/bash
# W4B firstboot setup script

# Create log directory if it doesn't exist
mkdir -p /var/log/w4b
chown -R pi:pi /var/log/w4b

# Ensure all W4B directories have correct permissions
chown -R pi:pi /opt/w4b

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

# Self-cleanup
echo "First boot setup completed, removing script"
rm /boot/firstboot.sh
""")
            
            # Make it executable
            firstboot_path.chmod(0o755)
            
            # Modify rc.local to run firstboot script
            rc_local_path = root_mount / "etc/rc.local"
            
            # Handle existing rc.local
            if rc_local_path.exists():
                with open(rc_local_path, 'r') as f:
                    content = f.read()
                
                # Add firstboot script execution if not already there
                if "firstboot.sh" not in content:
                    # Insert before 'exit 0' if it exists, otherwise append
                    if "exit 0" in content:
                        content = content.replace(
                            "exit 0", 
                            "\n# Run firstboot script if exists\nif [ -f /boot/firstboot.sh ]; then\n  /boot/firstboot.sh\nfi\n\nexit 0"
                        )
                    else:
                        content += "\n# Run firstboot script if exists\nif [ -f /boot/firstboot.sh ]; then\n  /boot/firstboot.sh\nfi\n\nexit 0\n"
                    
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
                
            self.logger.info("Created firstboot scripts")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create firstboot scripts: {str(e)}")
            return False
    
    async def _set_permissions(self, root_mount: Path) -> None:
        """
        Set correct permissions for installed files.
        
        Args:
            root_mount: Path to the root filesystem mount point
        """
        try:
            # Set ownership for W4B directory
            w4b_dir = root_mount / "opt/w4b"
            
            # Use chown command to set ownership to pi user
            process = await asyncio.create_subprocess_exec(
                'chown', '-R', '1000:1000', str(w4b_dir),  # 1000:1000 is pi:pi on Raspberry Pi
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                self.logger.warning(f"Failed to set ownership of {w4b_dir}: {stderr.decode()}")
            else:
                self.logger.info(f"Set ownership of {w4b_dir} to pi:pi")
                
            # Set ownership for log directory
            log_dir = root_mount / "var/log/w4b"
            if log_dir.exists():
                process = await asyncio.create_subprocess_exec(
                    'chown', '-R', '1000:1000', str(log_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                if process.returncode != 0:
                    self.logger.warning(f"Failed to set ownership of {log_dir}: {stderr.decode()}")
                else:
                    self.logger.info(f"Set ownership of {log_dir} to pi:pi")
                    
        except Exception as e:
            self.logger.warning(f"Error setting permissions: {str(e)}")
    
    def _verify_installation(self, root_mount: Path, boot_mount: Path) -> bool:
        """
        Verify that all required files and services were installed correctly.
        
        Args:
            root_mount: Path to the root filesystem mount point
            boot_mount: Path to the boot partition mount point
            
        Returns:
            bool: True if verification passes, False otherwise
        """
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
