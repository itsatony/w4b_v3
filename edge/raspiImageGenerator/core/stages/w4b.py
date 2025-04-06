#!/usr/bin/env python3
"""
W4B software installation stage for the W4B Raspberry Pi Image Generator.

This module implements the W4B software installation stage of the build pipeline,
responsible for installing the W4B software components like sensor manager,
configuration files, and sample data.
"""

import asyncio
import os
import shutil
import glob
from pathlib import Path
from typing import Dict, Any, Optional, List

from core.stages.base import BuildStage
from utils.error_handling import ImageBuildError


class W4BSoftwareStage(BuildStage):
    """
    Build stage for installing W4B software.
    
    This stage is responsible for installing the W4B software components
    like sensor manager, configuration files, and sample data.
    
    Attributes:
        name (str): Name of the stage
        state (Dict[str, Any]): Shared pipeline state
        logger (logging.Logger): Logger instance
        circuit_breaker (CircuitBreaker): Circuit breaker for fault tolerance
    """
    
    async def execute(self) -> bool:
        """
        Execute the W4B software installation stage.
        
        Returns:
            bool: True if installation succeeded, False otherwise
        """
        try:
            # Get paths from state
            boot_mount = self.state["boot_mount"]
            root_mount = self.state["root_mount"]
            
            # Install W4B software components
            await self._install_sensor_manager(root_mount)
            
            # Install configuration files
            await self._install_configuration_files(root_mount)
            
            # Install sample data
            await self._install_sample_data(root_mount)
            
            self.logger.info("W4B software installation completed successfully")
            return True
            
        except Exception as e:
            self.logger.exception(f"W4B software installation failed: {str(e)}")
            return False
    
    async def _install_sensor_manager(self, root_mount: Path) -> None:
        """
        Install sensor manager software.
        
        Args:
            root_mount: Path to the root file system
        """
        self.logger.info("Installing sensor manager software")
        
        # Get repo root
        repo_root = Path(__file__).parents[5]  # Go up 5 levels from core/stages/w4b.py
        
        # Create target directory
        target_dir = root_mount / "opt/w4b/sensor_manager"
        target_dir.mkdir(exist_ok=True, parents=True)
        
        # Copy sensor manager code
        sensor_manager_src = repo_root / "edge/sensorManager"
        sensor_manager_files = [
            "sensor_data_collector.py",
            "sensor_config.yaml",
        ]
        
        for file in sensor_manager_files:
            src_path = sensor_manager_src / file
            if src_path.exists():
                dst_path = target_dir / file
                shutil.copy(src_path, dst_path)
                self.logger.info(f"Copied {src_path} to {dst_path}")
        
        # Create sensor implementation directory
        sensors_dir = target_dir / "sensors"
        sensors_dir.mkdir(exist_ok=True)
        
        # Create __init__.py for sensors package
        with open(sensors_dir / "__init__.py", "w") as f:
            f.write('"""Sensor implementations for W4B Sensor Manager."""\n')
        
        # Create dummy sensor implementations for different types
        sensor_types = [
            ("temperature.py", "temperature"),
            ("humidity.py", "humidity"),
            ("weight.py", "weight"),
            ("pressure.py", "pressure"),
            ("light.py", "light"),
            ("sound.py", "sound"),
            ("image.py", "image"),
            ("rain.py", "rain"),
            ("wind.py", "wind"),
            ("dust.py", "dust"),
        ]
        
        for file_name, sensor_type in sensor_types:
            # Create sensor implementation with dummy pattern-based data
            with open(sensors_dir / file_name, "w") as f:
                f.write(f'"""W4B {sensor_type} sensor implementation."""\n\n')
                f.write('import random\n')
                f.write('import math\n')
                f.write('import asyncio\n')
                f.write('from datetime import datetime, timezone\n')
                f.write('from typing import Dict, Any, Optional\n\n')
                
                # Create sensor class
                f.write(f'class {sensor_type.capitalize()}Sensor:\n')
                f.write('    """W4B sensor implementation for {sensor_type}."""\n\n')
                
                # Constructor
                f.write('    def __init__(self, sensor_id: str, interface_config: Dict[str, Any], '
                        'calibration_config: Dict[str, Any]):\n')
                f.write('        """Initialize the sensor with configuration."""\n')
                f.write('        self.sensor_id = sensor_id\n')
                f.write('        self.interface_config = interface_config\n')
                f.write('        self.calibration_config = calibration_config\n')
                f.write('        self.initialized = False\n\n')
                
                # Initialize method
                f.write('    async def initialize(self) -> bool:\n')
                f.write('        """Initialize the sensor hardware."""\n')
                f.write('        # Simulate hardware initialization\n')
                f.write('        await asyncio.sleep(0.5)\n')
                f.write('        self.initialized = True\n')
                f.write('        return True\n\n')
                
                # Read method with pattern-based dummy data based on type
                f.write('    async def read(self) -> Dict[str, Any]:\n')
                f.write('        """Read sensor data."""\n')
                f.write('        if not self.initialized:\n')
                f.write('            await self.initialize()\n\n')
                
                f.write('        # Get current hour for time-based patterns\n')
                f.write('        now = datetime.now(timezone.utc)\n')
                f.write('        hour = now.hour\n')
                f.write('        minute = now.minute\n')
                f.write('        day_of_year = now.timetuple().tm_yday\n\n')
                
                # Generate appropriate pattern based on sensor type
                if sensor_type == "temperature":
                    f.write('        # Temperature follows a daily cycle with random variations\n')
                    f.write('        # Base pattern: cooler at night, warmer during day\n')
                    f.write('        base_temp = 20.0  # baseline temperature\n')
                    f.write('        daily_variation = 8.0 * math.sin(math.pi * (hour - 6) / 12)  # peak at noon, low at midnight\n')
                    f.write('        seasonal_variation = 5.0 * math.sin(math.pi * (day_of_year - 80) / 182.5)  # peak in summer\n')
                    f.write('        noise = random.uniform(-0.5, 0.5)  # random noise\n')
                    f.write('        value = base_temp + daily_variation + seasonal_variation + noise\n\n')
                    
                    f.write('        # Apply calibration\n')
                    f.write('        offset = self.calibration_config.get("offset", 0.0)\n')
                    f.write('        scale = self.calibration_config.get("scale", 1.0)\n')
                    f.write('        value = (value * scale) + offset\n\n')
                    
                    f.write('        return {\n')
                    f.write('            "timestamp": now.isoformat(),\n')
                    f.write('            "name": "temperature",\n')
                    f.write('            "value": round(value, 2),\n')
                    f.write('            "unit": "celsius"\n')
                    f.write('        }\n')
                    
                elif sensor_type == "humidity":
                    f.write('        # Humidity follows inverse of temperature pattern with random variations\n')
                    f.write('        # Base pattern: higher at night, lower during day\n')
                    f.write('        base_humidity = 60.0  # baseline humidity\n')
                    f.write('        daily_variation = -15.0 * math.sin(math.pi * (hour - 6) / 12)  # low at noon, high at midnight\n')
                    f.write('        seasonal_variation = -5.0 * math.sin(math.pi * (day_of_year - 80) / 182.5)  # low in summer\n')
                    f.write('        noise = random.uniform(-3.0, 3.0)  # random noise\n')
                    f.write('        value = base_humidity + daily_variation + seasonal_variation + noise\n')
                    f.write('        value = max(10.0, min(95.0, value))  # clamp between 10% and 95%\n\n')
                    
                    f.write('        # Apply calibration\n')
                    f.write('        offset = self.calibration_config.get("offset", 0.0)\n')
                    f.write('        scale = self.calibration_config.get("scale", 1.0)\n')
                    f.write('        value = (value * scale) + offset\n\n')
                    
                    f.write('        return {\n')
                    f.write('            "timestamp": now.isoformat(),\n')
                    f.write('            "name": "humidity",\n')
                    f.write('            "value": round(value, 1),\n')
                    f.write('            "unit": "percent"\n')
                    f.write('        }\n')
                    
                elif sensor_type == "weight":
                    f.write('        # Weight simulates a beehive with gradual changes and bee activity\n')
                    f.write('        base_weight = 30000.0  # baseline weight in grams (30kg)\n')
                    f.write('        # Daily variations as bees leave/return to hive\n')
                    f.write('        if 6 <= hour < 20:  # daytime activity\n')
                    f.write('            activity = -500.0 * math.sin(math.pi * (hour - 6) / 14)  # min weight around noon\n')
                    f.write('        else:  # nighttime - stable\n')
                    f.write('            activity = 0.0\n')
                    f.write('        # Seasonal variations - honey increases during season\n')
                    f.write('        seasonal = 2000.0 * math.sin(math.pi * (day_of_year - 100) / 150) if 100 <= day_of_year <= 250 else 0.0\n')
                    f.write('        noise = random.uniform(-50.0, 50.0)  # random noise\n')
                    f.write('        value = base_weight + activity + seasonal + noise\n\n')
                    
                    f.write('        # Apply calibration\n')
                    f.write('        tare = self.calibration_config.get("tare", 0.0)\n')
                    f.write('        scale_factor = self.calibration_config.get("scale_factor", 1.0)\n')
                    f.write('        value = (value - tare) * scale_factor\n\n')
                    
                    f.write('        return {\n')
                    f.write('            "timestamp": now.isoformat(),\n')
                    f.write('            "name": "weight",\n')
                    f.write('            "value": round(value, 0),\n')
                    f.write('            "unit": "grams"\n')
                    f.write('        }\n')
                    
                else:
                    # Generic sensor pattern
                    f.write('        # Generate simulated data with realistic patterns\n')
                    f.write('        base_value = 50.0  # baseline value\n')
                    f.write('        daily_variation = 20.0 * math.sin(math.pi * (hour - 6) / 12)  # daily cycle\n')
                    f.write('        noise = random.uniform(-5.0, 5.0)  # random noise\n')
                    f.write('        value = base_value + daily_variation + noise\n')
                    f.write('        value = max(0.0, value)  # ensure non-negative\n\n')
                    
                    f.write('        # Apply simple calibration\n')
                    f.write('        offset = self.calibration_config.get("offset", 0.0)\n')
                    f.write('        scale = self.calibration_config.get("scale", 1.0)\n')
                    f.write('        value = (value * scale) + offset\n\n')
                    
                    f.write('        return {\n')
                    f.write('            "timestamp": now.isoformat(),\n')
                    f.write('            "name": "' + sensor_type + '",\n')
                    f.write('            "value": round(value, 2),\n')
                    f.write('            "unit": "units"\n')
                    f.write('        }\n')
                
                # Additional methods
                f.write('\n    async def calibrate(self) -> bool:\n')
                f.write('        """Perform sensor calibration."""\n')
                f.write('        # Simulate calibration process\n')
                f.write('        await asyncio.sleep(1.0)\n')
                f.write('        return True\n\n')
                
                f.write('    async def validate(self) -> bool:\n')
                f.write('        """Validate sensor functionality."""\n')
                f.write('        # Simulate validation\n')
                f.write('        await asyncio.sleep(0.2)\n')
                f.write('        return True\n\n')
                
                f.write('    def get_metadata(self) -> Dict[str, Any]:\n')
                f.write('        """Get sensor metadata."""\n')
                f.write('        return {\n')
                f.write('            "id": self.sensor_id,\n')
                f.write('            "type": "' + sensor_type + '",\n')
                f.write('            "model": "W4B Dummy ' + sensor_type.capitalize() + '",\n')
                f.write('            "interface": self.interface_config,\n')
                f.write('            "calibration": self.calibration_config,\n')
                f.write('            "status": "active" if self.initialized else "inactive"\n')
                f.write('        }\n\n')
                
                f.write('    async def cleanup(self) -> None:\n')
                f.write('        """Clean up resources."""\n')
                f.write('        self.initialized = False\n')
        
        # Create utilities directory and files
        utils_dir = target_dir / "utils"
        utils_dir.mkdir(exist_ok=True)
        
        # Create __init__.py for utils package
        with open(utils_dir / "__init__.py", "w") as f:
            f.write('"""Utility functions for W4B Sensor Manager."""\n')
        
        # Create sample utility modules
        with open(utils_dir / "calibration.py", "w") as f:
            f.write('"""Calibration utilities for sensors."""\n\n')
            f.write('from typing import Dict, Any, List, Callable, Optional\n\n')
            
            f.write('def apply_calibration(value: float, calibration: Dict[str, Any]) -> float:\n')
            f.write('    """Apply calibration to sensor reading."""\n')
            f.write('    method = calibration.get("method", "linear")\n\n')
            
            f.write('    if method == "linear":\n')
            f.write('        scale = calibration.get("scale", 1.0)\n')
            f.write('        offset = calibration.get("offset", 0.0)\n')
            f.write('        return (value * scale) + offset\n\n')
            
            f.write('    elif method == "polynomial":\n')
            f.write('        coefficients = calibration.get("coefficients", [0.0, 1.0])\n')
            f.write('        result = 0.0\n')
            f.write('        for i, coef in enumerate(reversed(coefficients)):\n')
            f.write('            result += coef * (value ** i)\n')
            f.write('        return result\n\n')
            
            f.write('    elif method == "offset":\n')
            f.write('        offset = calibration.get("offset", 0.0)\n')
            f.write('        return value + offset\n\n')
            
            f.write('    elif method == "scale":\n')
            f.write('        scale = calibration.get("scale", 1.0)\n')
            f.write('        return value * scale\n\n')
            
            f.write('    return value  # No calibration\n')
        
        with open(utils_dir / "validation.py", "w") as f:
            f.write('"""Validation utilities for sensor readings."""\n\n')
            f.write('from typing import Dict, Any, Optional\n\n')
            
            f.write('def validate_reading(reading: Dict[str, Any], bounds: Dict[str, Any]) -> bool:\n')
            f.write('    """Validate sensor reading against bounds."""\n')
            f.write('    if "value" not in reading:\n')
            f.write('        return False\n\n')
            
            f.write('    value = reading["value"]\n')
            f.write('    min_value = bounds.get("min", float("-inf"))\n')
            f.write('    max_value = bounds.get("max", float("inf"))\n\n')
            
            f.write('    return min_value <= value <= max_value\n\n')
            
            f.write('def validate_change_rate(current: float, previous: float, max_change: float) -> bool:\n')
            f.write('    """Validate rate of change between readings."""\n')
            f.write('    if previous is None:\n')
            f.write('        return True\n\n')
            
            f.write('    change = abs(current - previous)\n')
            f.write('    return change <= max_change\n')
        
        # Set execute permissions on Python files
        sensor_collector_path = target_dir / "sensor_data_collector.py"
        if sensor_collector_path.exists():
            sensor_collector_path.chmod(0o755)
    
    async def _install_configuration_files(self, root_mount: Path) -> None:
        """
        Install configuration files.
        
        Args:
            root_mount: Path to the root file system
        """
        self.logger.info("Installing configuration files")
        
        # Create sensor configuration directory
        config_dir = root_mount / "opt/w4b/config"
        config_dir.mkdir(exist_ok=True, parents=True)
        
        # Get hive ID from configuration
        hive_id = self.state["config"].get("hive_id", "unknown")
        
        # Create environment file with substitutions
        env_path = root_mount / "etc/w4b/env"
        env_dir = env_path.parent
        env_dir.mkdir(exist_ok=True)
        
        with open(env_path, "w") as f:
            f.write(f"# W4B Environment Configuration\n")
            f.write(f"HIVE_ID={hive_id}\n")
            f.write(f"TIMEZONE={self.state['config']['system'].get('timezone', 'UTC')}\n")
            f.write(f"LOCATION={self.state['config'].get('location', 'Unknown')}\n")
            f.write(f"VECTOR_ENABLED=false\n")
            f.write(f"PROMETHEUS_PORT=9100\n")
            
            # Add database credentials
            db_config = self.state["config"].get("services", {}).get("database", {})
            db_user = db_config.get("username", "hive")
            db_password = db_config.get("password", "changeme")
            db_name = db_config.get("database", "hivedb")
            
            f.write(f"DB_USER={db_user}\n")
            f.write(f"DB_PASSWORD={db_password}\n")
            f.write(f"DB_NAME={db_name}\n")
        
        # Create .env file symlink in sensor manager directory
        env_symlink = root_mount / "opt/w4b/sensor_manager/.env"
        os.symlink("/etc/w4b/env", env_symlink)
        
        # Update firstboot script to load environment variables
        firstboot_path = Path(self.state["boot_mount"]) / "firstboot.sh"
        
        with open(firstboot_path, "r") as f:
            content = f.readlines()
        
        # Find the beginning of the script (after shebang and set -e)
        insert_pos = 0
        for i, line in enumerate(content):
            if line.startswith("echo ") and "first boot setup" in line.lower():
                insert_pos = i
                break
            elif i >= 3:  # If we don't find it in the first few lines, insert after line 3
                insert_pos = 3
                break
        
        # Create environment loading section
        env_lines = [
            "# Load environment variables\n",
            "if [ -f /etc/w4b/env ]; then\n",
            "  echo \"Loading W4B environment variables\"\n",
            "  set -a\n",
            "  . /etc/w4b/env\n",
            "  set +a\n",
            "fi\n",
            "\n"
        ]
        
        # Insert environment lines
        content = content[:insert_pos] + env_lines + content[insert_pos:]
        
        # Write back to file
        with open(firstboot_path, "w") as f:
            f.writelines(content)
    
    async def _install_sample_data(self, root_mount: Path) -> None:
        """
        Install sample data.
        
        Args:
            root_mount: Path to the root file system
        """
        # Create sample data directory
        data_dir = root_mount / "opt/w4b/sample_data"
        data_dir.mkdir(exist_ok=True, parents=True)
        
        self.logger.info("Sample data directory created")
