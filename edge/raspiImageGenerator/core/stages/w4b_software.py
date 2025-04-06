#!/usr/bin/env python3
"""
W4B software installation stage for Raspberry Pi image generator.

This stage prepares W4B-specific software and configurations that will
be set up during the firstboot process.
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
    Build stage for preparing W4B software components on the Raspberry Pi image.
    
    This stage focuses on:
    1. Copying minimal sensor manager code to the image
    2. Creating configuration templates
    3. Enhancing firstboot scripts with W4B-specific setup
    """
    
    async def execute(self) -> bool:
        try:
            self.logger.info("Starting stage: W4BSoftwareStage")
            
            # Ensure mount points exist in state
            if "root_mount" not in self.state or "boot_mount" not in self.state:
                self.logger.error("Mount points not found in state")
                return False
            
            root_mount = self.state["root_mount"]
            boot_mount = self.state["boot_mount"]
            
            # Create all necessary directories
            if not await self._create_directories(root_mount):
                return False
            
            # Copy W4B configuration files
            if not await self._copy_config_files(root_mount):
                return False
            
            # Copy minimal sensor manager implementation
            if not await self._prepare_sensor_manager(root_mount):
                return False
            
            # Enhance firstboot script with W4B-specific setup
            if not await self._enhance_firstboot_script(boot_mount, root_mount):
                return False
            
            self.logger.info("W4B software preparation completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"W4B software preparation failed: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return False
    
    async def _create_directories(self, root_mount: Path) -> bool:
        """Create necessary directories for W4B software."""
        try:
            # Define required directories
            directories = [
                root_mount / "opt/w4b",
                root_mount / "opt/w4b/sensorManager",
                root_mount / "opt/w4b/config",
                root_mount / "opt/w4b/data",
                root_mount / "var/log/w4b"
            ]
            
            # Create each directory
            for directory in directories:
                directory.mkdir(parents=True, exist_ok=True)
                self.logger.debug(f"Created directory: {directory}")
            
            self.logger.info("All required directories created successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create directories: {str(e)}")
            return False
    
    async def _copy_config_files(self, root_mount: Path) -> bool:
        """Copy W4B configuration files to the image."""
        try:
            config_dir = root_mount / "opt/w4b/config"
            
            # Create sensor configuration YAML
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
            
            # Create environment file
            env_dir = root_mount / "etc/w4b"
            env_dir.mkdir(exist_ok=True, parents=True)
            
            env_file = env_dir / "env"
            with open(env_file, 'w') as f:
                f.write(f"""# W4B Environment Configuration
HIVE_ID={self.state['config']['hive_id']}
TIMEZONE={self.state['config']['system']['timezone']}
LOCATION={self.state['config'].get('location', 'Unknown')}
PROMETHEUS_PORT=9100
DB_USER=hiveuser
DB_PASSWORD=changeme
DB_NAME=hivedb
""")
            
            self.logger.info("W4B configuration files created successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create configuration files: {str(e)}")
            return False
    
    async def _prepare_sensor_manager(self, root_mount: Path) -> bool:
        """Prepare minimal sensor manager implementation."""
        try:
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
            
            # If source found, create small placeholder with instructions
            collector_script = sensor_manager_dir / "sensor_data_collector.py"
            with open(collector_script, "w") as f:
                f.write("""#!/usr/bin/env python3
\"\"\"
W4B Sensor Manager - Placeholder Implementation
This will be replaced during firstboot with the actual implementation.
\"\"\"

import time
import logging
import os
import sys
import json
from datetime import datetime

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

def main():
    logger.info("W4B Sensor Manager Placeholder")
    logger.info("This placeholder will be replaced during firstboot")
    
    # Create a sample data file to demonstrate functionality
    os.makedirs("/opt/w4b/data", exist_ok=True)
    with open("/opt/w4b/data/sample_data.json", "w") as f:
        f.write(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "message": "Placeholder sensor manager is running"
        }, indent=2))
    
    while True:
        logger.info("Placeholder sensor manager running...")
        time.sleep(60)

if __name__ == "__main__":
    main()
""")
            
            # Make script executable
            collector_script.chmod(0o755)
            
            # Create service file with consistent naming
            service_file = sensor_manager_dir / "w4b-sensor-manager.service"
            with open(service_file, "w") as f:
                f.write("""[Unit]
Description=W4B Sensor Manager
After=network.target postgresql.service

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/w4b/sensorManager
ExecStart=/usr/bin/python3 /opt/w4b/sensorManager/sensor_data_collector.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
""")
            
            self.logger.info("Prepared sensor manager placeholder")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to prepare sensor manager: {str(e)}")
            return False
    
    async def _enhance_firstboot_script(self, boot_mount: Path, root_mount: Path) -> bool:
        """Enhance firstboot script with W4B-specific setup."""
        try:
            firstboot_path = boot_mount / "firstboot.sh"
            
            if not firstboot_path.exists():
                self.logger.error("Firstboot script not found, cannot enhance")
                return False
            
            # Read existing script
            with open(firstboot_path, "r") as f:
                content = f.readlines()
            
            # Find position to insert W4B setup (before cleanup/removal section)
            insert_pos = 0
            for i, line in enumerate(content):
                if "Remove firstboot script" in line or "rm /boot/firstboot.sh" in line:
                    insert_pos = i
                    break
            
            # If no removal section found, append to end
            if insert_pos == 0:
                insert_pos = len(content) - 1
            
            # Create W4B-specific setup section
            w4b_setup = [
                "# W4B-specific setup\n",
                "echo \"Setting up W4B components...\"\n\n",
                
                "# Clone or update W4B repository if needed\n",
                "if [ ! -d /opt/w4b/repo ]; then\n",
                "  echo \"Cloning W4B repository...\"\n",
                "  mkdir -p /opt/w4b/repo\n",
                "  git clone https://github.com/itsatony/w4b_v3.git /opt/w4b/repo\n",
                "else\n",
                "  echo \"Updating W4B repository...\"\n",
                "  cd /opt/w4b/repo\n",
                "  git pull\n",
                "fi\n\n",
                
                "# Set up symbolic link for environment file\n",
                "ln -sf /etc/w4b/env /opt/w4b/.env\n\n",
                
                "# Copy sensor manager from repository to installation directory\n",
                "echo \"Installing sensor manager...\"\n",
                "cp -R /opt/w4b/repo/edge/sensorManager/* /opt/w4b/sensorManager/\n",
                "chmod 755 /opt/w4b/sensorManager/sensor_data_collector.py\n\n",
                
                "# Install service with consistent naming\n",
                "echo \"Installing W4B services...\"\n",
                "cp /opt/w4b/sensorManager/w4b-sensor-manager.service /etc/systemd/system/\n",
                "systemctl daemon-reload\n",
                "systemctl enable w4b-sensor-manager.service\n",
                "systemctl start w4b-sensor-manager.service\n\n",
                
                "# Set up database for sensor data\n",
                "echo \"Setting up sensor database...\"\n",
                "source /etc/w4b/env\n",
                "sudo -u postgres psql -c \"CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';\"\n",
                "sudo -u postgres psql -c \"CREATE DATABASE $DB_NAME OWNER $DB_USER;\"\n",
                "sudo -u postgres psql -d $DB_NAME -c \"CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;\"\n",
                "sudo -u postgres psql -d $DB_NAME -c \"\n",
                "CREATE TABLE IF NOT EXISTS sensor_data (\n",
                "    time TIMESTAMPTZ NOT NULL,\n",
                "    hive_id TEXT NOT NULL,\n",
                "    sensor_id TEXT NOT NULL,\n",
                "    metric_name TEXT NOT NULL,\n",
                "    value DOUBLE PRECISION NOT NULL,\n",
                "    unit TEXT NOT NULL,\n",
                "    status TEXT DEFAULT 'valid'\n",
                ");\n",
                "SELECT create_hypertable('sensor_data', 'time', if_not_exists => TRUE);\"\n\n"
            ]
            
            # Insert W4B setup section
            content = content[:insert_pos] + w4b_setup + content[insert_pos:]
            
            # Write enhanced script back to file
            with open(firstboot_path, "w") as f:
                f.writelines(content)
            
            self.logger.info("Enhanced firstboot script with W4B-specific setup")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to enhance firstboot script: {str(e)}")
            return False
