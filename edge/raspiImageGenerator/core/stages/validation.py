#!/usr/bin/env python3
"""
Validation stage for Raspberry Pi image generator.
"""

import os
import sys
import asyncio
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from core.stages.base import BuildStage

class ValidationStage(BuildStage):
    """
    Build stage for validating the generated image.
    """
    
    async def execute(self) -> bool:
        try:
            self.logger.info("Starting stage: ValidationStage")
            
            # Ensure we have an image path
            if "image_path" not in self.state:
                raise KeyError("No image path found in state")
                
            if "root_mount" not in self.state or "boot_mount" not in self.state:
                raise KeyError("Mount points not found in state")
                
            image_path = self.state["image_path"]
            root_mount = self.state["root_mount"]
            boot_mount = self.state["boot_mount"]
            
            validation_types = self.state["config"].get("validation", {}).get("types", ["structure", "files", "services"])
            
            self.logger.info(f"Validating image with types: {validation_types}")
            self.logger.info(f"Validating image: {image_path}")
            
            # Run validations
            validation_results = {}
            for validation_type in validation_types:
                self.logger.info(f"Running {validation_type} validation")
                method_name = f"_validate_{validation_type}"
                if hasattr(self, method_name) and callable(getattr(self, method_name)):
                    validation_function = getattr(self, method_name)
                    success, message = await validation_function()
                    validation_results[validation_type] = {
                        "success": success,
                        "message": message
                    }
                    if not success:
                        self.logger.error(f"{validation_type} validation failed: {message}")
                else:
                    self.logger.warning(f"Validation type {validation_type} not implemented")
            
            # Check if all validations passed
            all_passed = all(result["success"] for result in validation_results.values())
            
            if all_passed:
                self.logger.info("All validations passed successfully")
                return True
            else:
                # Log detailed validation failures
                self.logger.error("Image validation failed")
                for validation_type, result in validation_results.items():
                    if not result["success"]:
                        self.logger.error(f"{validation_type} validation failed: {result['message']}")
                return False
                
        except Exception as e:
            self.logger.error(f"Validation failed: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return False
    
    async def _validate_structure(self) -> Tuple[bool, str]:
        """Validate the image structure."""
        try:
            # Ensure mount points exist in state
            if "root_mount" not in self.state or "boot_mount" not in self.state:
                return False, "Mount points not found in state"
            
            root_mount = self.state["root_mount"]
            boot_mount = self.state["boot_mount"]
            
            # Debug output to show actual paths
            self.logger.info(f"Validation using root_mount: {root_mount}")
            self.logger.info(f"Validation using boot_mount: {boot_mount}")
            
            # First check if directories exist on the filesystem
            essential_dirs = [
                root_mount / "etc",
                root_mount / "etc/systemd",
                root_mount / "etc/systemd/system",
                root_mount / "home/pi",
                root_mount / "opt/w4b",
                root_mount / "opt/w4b/sensorManager",
                root_mount / "opt/w4b/config",
                boot_mount
            ]
            
            # Debug each directory
            for directory in essential_dirs:
                self.logger.debug(f"Checking directory: {directory} (exists: {directory.exists()})")
            
            missing_dirs = []
            for directory in essential_dirs:
                if not directory.is_dir():
                    # Try to list the parent directory to debug
                    parent = directory.parent
                    if parent.exists():
                        self.logger.debug(f"Parent dir {parent} contents: {[str(x) for x in parent.iterdir()]}")
                    missing_dirs.append(str(directory))
            
            if missing_dirs:
                return False, f"Essential directories not found: {', '.join(missing_dirs)}"
            
            return True, "Structure validation passed"
        except Exception as e:
            self.logger.error(f"Exception during structure validation: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return False, f"Structure validation error: {str(e)}"
    
    async def _validate_files(self) -> Tuple[bool, str]:
        """Validate essential files in the image."""
        try:
            # Ensure mount points exist in state
            if "root_mount" not in self.state or "boot_mount" not in self.state:
                return False, "Mount points not found in state"
            
            root_mount = self.state["root_mount"]
            boot_mount = self.state["boot_mount"]
            
            # Define essential files to check
            essential_files = [
                root_mount / "etc/hostname",
                root_mount / "etc/wireguard/wg0.conf",
                boot_mount / "firstboot.sh",
                root_mount / "opt/w4b/config/sensor_config.yaml",
                root_mount / "opt/w4b/sensorManager/sensor_data_collector.py"
            ]
            
            missing_files = []
            for file_path in essential_files:
                if not file_path.exists():
                    missing_files.append(str(file_path))
                    self.logger.debug(f"Missing file: {file_path}")
            
            if missing_files:
                return False, f"Essential files not found: {', '.join(missing_files)}"
            
            return True, "Files validation passed"
        except Exception as e:
            return False, f"Files validation error: {str(e)}"
    
    async def _validate_services(self) -> Tuple[bool, str]:
        """Validate system services in the image."""
        try:
            # Ensure mount points exist in state
            if "root_mount" not in self.state:
                return False, "Root mount point not found in state"
            
            root_mount = self.state["root_mount"]
            
            # Define essential services to check - use correct service names
            essential_services = [
                "opt/w4b/sensorManager/w4b-sensor-manager.service",
                "etc/systemd/system/w4b-firstboot.service"  # Created by software_install.py
            ]
            
            # Add potential alternate service files
            alternate_services = [
                "etc/systemd/system/sensor-manager.service",  # Created by services.py
            ]
            
            # Debug: List all systemd service files in the image
            self.logger.debug("Listing all service files in the image:")
            service_dir = root_mount / "etc/systemd/system"
            if service_dir.exists():
                for service_file in service_dir.glob("*.service"):
                    self.logger.debug(f"Found service file: {service_file.relative_to(root_mount)}")
            
            # Check for required services
            missing_services = []
            for service_path in essential_services:
                full_path = root_mount / service_path
                if not full_path.exists():
                    # Check if any of the alternate services exist instead
                    alternate_found = False
                    for alt_service in alternate_services:
                        alt_path = root_mount / alt_service
                        if alt_path.exists():
                            self.logger.info(f"Found alternate service: {alt_service} instead of {service_path}")
                            alternate_found = True
                            break
                    
                    if not alternate_found:
                        missing_services.append(service_path)
                        self.logger.debug(f"Missing service: {full_path}")
            
            if missing_services:
                return False, f"Essential services not found: {', '.join(missing_services)}"
            
            return True, "Services validation passed"
        except Exception as e:
            return False, f"Services validation error: {str(e)}"
