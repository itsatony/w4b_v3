#!/usr/bin/env python3
"""
Service configuration stage for the W4B Raspberry Pi Image Generator.

This module implements the service configuration stage of the build pipeline,
responsible for setting up systemd services, database configurations, and
other system services.
"""

import asyncio
import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

from core.stages.base import BuildStage
from utils.error_handling import ImageBuildError


class ServiceConfigStage(BuildStage):
    """
    Build stage for configuring system services.
    
    This stage is responsible for setting up systemd services, database
    configurations, and other system services.
    
    Attributes:
        name (str): Name of the stage
        state (Dict[str, Any]): Shared pipeline state
        logger (logging.Logger): Logger instance
        circuit_breaker (CircuitBreaker): Circuit breaker for fault tolerance
    """
    
    async def execute(self) -> bool:
        """
        Execute the service configuration stage.
        
        Returns:
            bool: True if configuration succeeded, False otherwise
        """
        try:
            # Get paths from state
            boot_mount = self.state["boot_mount"]
            root_mount = self.state["root_mount"]
            
            # Configure system services
            services_config = self.state["config"].get("services", {})
            
            # Configure database
            if "database" in services_config:
                await self._configure_database(root_mount, services_config["database"])
            
            # Configure monitoring
            if "monitoring" in services_config:
                await self._configure_monitoring(root_mount, services_config["monitoring"])
            
            # Configure sensor manager
            if "sensor_manager" in services_config:
                await self._configure_sensor_manager(root_mount, services_config["sensor_manager"])
            
            # Configure systemd services
            await self._configure_systemd_services(root_mount)
            
            self.logger.info("Service configuration completed successfully")
            return True
            
        except Exception as e:
            self.logger.exception(f"Service configuration failed: {str(e)}")
            return False
    
    async def _configure_database(self, root_mount: Path, db_config: Dict[str, Any]) -> None:
        """
        Configure database services.
        
        Args:
            root_mount: Path to the root file system
            db_config: Database configuration
        """
        db_type = db_config.get("type", "timescaledb")
        if db_type != "timescaledb":
            self.logger.warning(f"Unsupported database type: {db_type}, only timescaledb is supported")
            return
        
        self.logger.info("Configuring TimescaleDB database")
        
        # Add database configuration to firstboot
        firstboot_path = Path(self.state["boot_mount"]) / "firstboot.sh"
        
        with open(firstboot_path, "r") as f:
            content = f.readlines()
        
        # Find position to insert database configuration (before "Mark setup as complete")
        insert_pos = 0
        for i, line in enumerate(content):
            if "Mark setup as complete" in line:
                insert_pos = i
                break
        
        # Get database configuration
        db_user = db_config.get("username", "hive")
        db_password = db_config.get("password", "changeme")
        db_name = db_config.get("database", "hivedb")
        retention_days = db_config.get("retention_days", 30)
        
        # Create database configuration section
        db_lines = [
            "# Configure TimescaleDB\n",
            "echo \"Configuring TimescaleDB database\"\n",
            
            # Create database and user
            f"sudo -u postgres psql -c \"CREATE ROLE {db_user} WITH LOGIN PASSWORD '{db_password}';\"\n",
            f"sudo -u postgres createdb -O {db_user} {db_name}\n",
            f"sudo -u postgres psql -d {db_name} -c \"CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;\"\n",
            
            # Create sensor data table
            f"sudo -u postgres psql -d {db_name} << 'EOF'\n",
            "CREATE TABLE IF NOT EXISTS sensor_readings (\n",
            "    time TIMESTAMPTZ NOT NULL,\n",
            "    hive_id TEXT NOT NULL,\n",
            "    sensor_id TEXT NOT NULL,\n",
            "    metric_name TEXT NOT NULL,\n",
            "    value DOUBLE PRECISION NOT NULL,\n",
            "    unit TEXT NOT NULL,\n",
            "    status TEXT DEFAULT 'valid'\n",
            ");\n",
            "SELECT create_hypertable('sensor_readings', 'time', if_not_exists => TRUE);\n",
            f"SELECT add_retention_policy('sensor_readings', INTERVAL '{retention_days} days');\n",
            "EOF\n",
            "\n",
            
            # Configure PostgreSQL
            "cat << EOF > /etc/postgresql/13/main/conf.d/timescaledb.conf\n",
            "# TimescaleDB settings\n",
            "shared_preload_libraries = 'timescaledb'\n",
            "timescaledb.telemetry_level=off\n",
            "\n",
            "# Memory settings\n",
            "shared_buffers = 128MB\n",
            "work_mem = 16MB\n",
            "maintenance_work_mem = 64MB\n",
            "effective_cache_size = 256MB\n",
            "\n",
            "# Connection settings\n",
            "max_connections = 20\n",
            "EOF\n",
            
            # Restart PostgreSQL
            "systemctl restart postgresql\n",
            "\n"
        ]
        
        # Insert database lines
        content = content[:insert_pos] + db_lines + content[insert_pos:]
        
        # Write back to file
        with open(firstboot_path, "w") as f:
            f.writelines(content)
    
    async def _configure_monitoring(self, root_mount: Path, monitoring_config: Dict[str, Any]) -> None:
        """
        Configure monitoring services.
        
        Args:
            root_mount: Path to the root file system
            monitoring_config: Monitoring configuration
        """
        if not monitoring_config.get("enabled", True):
            self.logger.info("Monitoring is disabled, skipping monitoring configuration")
            return
        
        self.logger.info("Configuring monitoring services")
        
        # Add monitoring configuration to firstboot
        firstboot_path = Path(self.state["boot_mount"]) / "firstboot.sh"
        
        with open(firstboot_path, "r") as f:
            content = f.readlines()
        
        # Find position to insert monitoring configuration (before "Mark setup as complete")
        insert_pos = 0
        for i, line in enumerate(content):
            if "Mark setup as complete" in line:
                insert_pos = i
                break
        
        # Get monitoring configuration
        metrics_port = monitoring_config.get("metrics_port", 9100)
        
        # Create monitoring configuration section
        monitoring_lines = [
            "# Configure monitoring services\n",
            "echo \"Configuring monitoring services\"\n",
            
            # Set up Node Exporter
            "apt-get install -y prometheus-node-exporter\n",
            f"sed -i 's/ARGS=\"\"/ARGS=\"--web.listen-address=:9100\"/' /etc/default/prometheus-node-exporter\n",
            "systemctl enable prometheus-node-exporter\n",
            "systemctl restart prometheus-node-exporter\n",
            
            # Set up Vector for log collection if configured
            "if [ \"${VECTOR_ENABLED}\" = \"true\" ]; then\n",
            "  echo \"Setting up Vector for log collection\"\n",
            "  apt-get install -y curl\n",
            "  curl -1sLf 'https://repositories.timber.io/public/vector/cfg/setup/bash.deb.sh' | bash\n",
            "  apt-get install -y vector\n",
            "  cat << EOF > /etc/vector/vector.yaml\n",
            "api:\n",
            "  enabled: true\n",
            "  address: 127.0.0.1:8686\n",
            "\n",
            "sources:\n",
            "  journald_source:\n",
            "    type: journald\n",
            "    include_units: [\"prometheus-node-exporter.service\", \"sensor-manager.service\"]\n",
            "\n",
            "  file_source:\n",
            "    type: file\n",
            "    include:\n",
            "      - /var/log/hive/*.log\n",
            "\n",
            "sinks:\n",
            "  prometheus_sink:\n",
            "    type: prometheus_exporter\n",
            "    inputs: [journald_source, file_source]\n",
            "    address: 0.0.0.0:9102\n",
            "EOF\n",
            "  systemctl enable vector\n",
            "  systemctl start vector\n",
            "fi\n",
            "\n"
        ]
        
        # Insert monitoring lines
        content = content[:insert_pos] + monitoring_lines + content[insert_pos:]
        
        # Write back to file
        with open(firstboot_path, "w") as f:
            f.writelines(content)
    
    async def _configure_sensor_manager(self, root_mount: Path, sensor_config: Dict[str, Any]) -> None:
        """
        Configure sensor manager service.
        
        Args:
            root_mount: Path to the root file system
            sensor_config: Sensor manager configuration
        """
        if not sensor_config.get("enabled", True):
            self.logger.info("Sensor manager is disabled, skipping sensor manager configuration")
            return
        
        self.logger.info("Configuring sensor manager service")
        
        # Create service directory
        service_dir = root_mount / "etc/systemd/system"
        service_dir.mkdir(exist_ok=True, parents=True)
        
        # Create sensor manager service
        with open(service_dir / "sensor-manager.service", "w") as f:
            f.write("[Unit]\n")
            f.write("Description=W4B Sensor Manager Service\n")
            f.write("After=network.target postgresql.service\n")
            f.write("Wants=postgresql.service\n")
            f.write("\n")
            f.write("[Service]\n")
            f.write("User=root\n")
            f.write("Group=root\n")
            f.write("WorkingDirectory=/opt/w4b/sensor_manager\n")
            f.write("ExecStart=/usr/bin/python3 /opt/w4b/sensor_manager/sensor_data_collector.py /opt/w4b/sensor_manager/sensor_config.yaml\n")
            f.write("Restart=on-failure\n")
            f.write("RestartSec=10\n")
            f.write("\n")
            f.write("[Install]\n")
            f.write("WantedBy=multi-user.target\n")
        
        # Add sensor manager configuration to firstboot
        firstboot_path = Path(self.state["boot_mount"]) / "firstboot.sh"
        
        with open(firstboot_path, "r") as f:
            content = f.readlines()
        
        # Find position to insert sensor manager configuration (before "Mark setup as complete")
        insert_pos = 0
        for i, line in enumerate(content):
            if "Mark setup as complete" in line:
                insert_pos = i
                break
        
        # Get sensor manager configuration
        auto_start = sensor_config.get("auto_start", True)
        
        # Create sensor manager configuration section
        sensor_lines = [
            "# Configure sensor manager service\n",
            "echo \"Configuring sensor manager service\"\n",
            
            # Create directories
            "mkdir -p /opt/w4b/sensor_manager\n",
            "mkdir -p /var/log/hive\n",
            
            # Set permissions
            "chmod 755 /opt/w4b/sensor_manager\n",
            "chmod 755 /var/log/hive\n",
            
            # Enable and start service if auto_start is true
            "systemctl daemon-reload\n",
            "systemctl enable sensor-manager.service\n",
        ]
        
        if auto_start:
            sensor_lines.append("systemctl start sensor-manager.service\n")
            
        sensor_lines.append("\n")
        
        # Insert sensor manager lines
        content = content[:insert_pos] + sensor_lines + content[insert_pos:]
        
        # Write back to file
        with open(firstboot_path, "w") as f:
            f.writelines(content)
    
    async def _configure_systemd_services(self, root_mount: Path) -> None:
        """
        Configure additional systemd services.
        
        Args:
            root_mount: Path to the root file system
        """
        # Add common systemd service configuration to firstboot
        firstboot_path = Path(self.state["boot_mount"]) / "firstboot.sh"
        
        with open(firstboot_path, "r") as f:
            content = f.readlines()
        
        # Find position to insert systemd configuration (before "Mark setup as complete")
        insert_pos = 0
        for i, line in enumerate(content):
            if "Mark setup as complete" in line:
                insert_pos = i
                break
        
        # Create systemd configuration section
        systemd_lines = [
            "# Configure systemd services\n",
            "echo \"Configuring systemd services\"\n",
            
            # Create a system update service
            "cat << EOF > /etc/systemd/system/system-update.service\n",
            "[Unit]\n",
            "Description=Daily system update\n",
            "After=network.target\n",
            "\n",
            "[Service]\n",
            "Type=oneshot\n",
            "ExecStart=/usr/bin/apt-get update\n",
            "ExecStart=/usr/bin/apt-get -y upgrade\n",
            "\n",
            "[Install]\n",
            "WantedBy=multi-user.target\n",
            "EOF\n",
            "\n",
            
            # Create a timer for the system update service
            "cat << EOF > /etc/systemd/system/system-update.timer\n",
            "[Unit]\n",
            "Description=Run system update daily\n",
            "\n",
            "[Timer]\n",
            "OnCalendar=*-*-* 03:00:00\n",
            "RandomizedDelaySec=1h\n",
            "Persistent=true\n",
            "\n",
            "[Install]\n",
            "WantedBy=timers.target\n",
            "EOF\n",
            "\n",
            
            # Enable the timer
            "systemctl daemon-reload\n",
            "systemctl enable system-update.timer\n",
            "\n"
        ]
        
        # Insert systemd lines
        content = content[:insert_pos] + systemd_lines + content[insert_pos:]
        
        # Write back to file
        with open(firstboot_path, "w") as f:
            f.writelines(content)
