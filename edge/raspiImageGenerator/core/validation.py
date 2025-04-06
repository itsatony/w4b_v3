#!/usr/bin/env python3
"""
Image validation utilities for the W4B Raspberry Pi Image Generator.

This module provides functionality for validating the generated Raspberry Pi images
to ensure they meet all requirements and are ready for deployment.
"""

import asyncio
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union

from utils.error_handling import ValidationError


class ImageValidator:
    """
    Validator for Raspberry Pi images.
    
    This class provides methods for validating generated images to ensure
    they meet all requirements and are properly configured.
    
    Attributes:
        logger (logging.Logger): Logger instance
    """
    
    def __init__(self):
        """Initialize the image validator."""
        self.logger = logging.getLogger("validator")
    
    async def validate_image(
        self,
        image_path: Path,
        boot_mount: Optional[Path] = None,
        root_mount: Optional[Path] = None,
        validation_types: Optional[List[str]] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate a Raspberry Pi image.
        
        Args:
            image_path: Path to the image file
            boot_mount: Optional path to boot partition mount point
            root_mount: Optional path to root partition mount point
            validation_types: Types of validation to perform
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (success, validation results)
        """
        if validation_types is None:
            validation_types = ["structure", "files", "services"]
        
        self.logger.info(f"Validating image: {image_path}")
        
        results = {
            "success": True,
            "image_path": str(image_path),
            "validations": {}
        }
        
        # Run all requested validations
        for validation_type in validation_types:
            func_name = f"_validate_{validation_type}"
            if hasattr(self, func_name):
                try:
                    self.logger.info(f"Running {validation_type} validation")
                    validation_func = getattr(self, func_name)
                    success, validation_result = await validation_func(
                        image_path, boot_mount, root_mount
                    )
                    
                    results["validations"][validation_type] = {
                        "success": success,
                        "results": validation_result
                    }
                    
                    if not success:
                        results["success"] = False
                        
                except Exception as e:
                    self.logger.exception(f"Error during {validation_type} validation: {str(e)}")
                    results["validations"][validation_type] = {
                        "success": False,
                        "error": str(e)
                    }
                    results["success"] = False
            else:
                self.logger.warning(f"Unknown validation type: {validation_type}")
        
        return results["success"], results
    
    async def _validate_structure(
        self,
        image_path: Path,
        boot_mount: Optional[Path],
        root_mount: Optional[Path]
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate the image structure.
        
        Args:
            image_path: Path to the image file
            boot_mount: Path to boot partition mount point
            root_mount: Path to root partition mount point
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (success, validation results)
        """
        results = {
            "image_exists": image_path.exists(),
            "image_size": image_path.stat().st_size if image_path.exists() else 0,
            "boot_mounted": boot_mount is not None and boot_mount.exists(),
            "root_mounted": root_mount is not None and root_mount.exists(),
        }
        
        # Check partitions are accessible
        if boot_mount and boot_mount.exists():
            kernel_files = list(boot_mount.glob("vmlinuz*"))
            results["kernel_found"] = len(kernel_files) > 0
        else:
            results["kernel_found"] = False
        
        if root_mount and root_mount.exists():
            results["etc_found"] = (root_mount / "etc").exists()
            results["bin_found"] = (root_mount / "bin").exists()
        else:
            results["etc_found"] = False
            results["bin_found"] = False
        
        # Calculate success
        success = all([
            results["image_exists"],
            results["image_size"] > 0,
            results["boot_mounted"] or boot_mount is None,
            results["root_mounted"] or root_mount is None,
            results["kernel_found"] or boot_mount is None,
            results["etc_found"] or root_mount is None,
            results["bin_found"] or root_mount is None
        ])
        
        return success, results
    
    async def _validate_files(
        self,
        image_path: Path,
        boot_mount: Optional[Path],
        root_mount: Optional[Path]
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate required files exist in the image.
        
        Args:
            image_path: Path to the image file
            boot_mount: Path to boot partition mount point
            root_mount: Path to root partition mount point
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (success, validation results)
        """
        results = {
            "required_files": {},
            "missing_files": []
        }
        
        # Check boot files
        if boot_mount and boot_mount.exists():
            boot_files = ["config.txt", "cmdline.txt", "bootcode.bin"]
            for file_name in boot_files:
                file_path = boot_mount / file_name
                exists = file_path.exists()
                results["required_files"][f"boot/{file_name}"] = exists
                if not exists:
                    results["missing_files"].append(f"boot/{file_name}")
        
        # Check root files
        if root_mount and root_mount.exists():
            root_files = [
                "etc/hostname",
                "etc/hosts",
                "etc/fstab",
                "etc/passwd",
                "etc/shadow"
            ]
            for file_name in root_files:
                file_path = root_mount / file_name
                exists = file_path.exists()
                results["required_files"][file_name] = exists
                if not exists:
                    results["missing_files"].append(file_name)
        
        # Calculate success
        success = len(results["missing_files"]) == 0
        
        return success, results
    
    async def _validate_services(
        self,
        image_path: Path,
        boot_mount: Optional[Path],
        root_mount: Optional[Path]
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate service configurations in the image.
        
        Args:
            image_path: Path to the image file
            boot_mount: Path to boot partition mount point
            root_mount: Path to root partition mount point
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (success, validation results)
        """
        results = {
            "required_services": {},
            "missing_services": []
        }
        
        # List of services that should be enabled
        services = [
            "ssh",
            "firstboot"
        ]
        
        if root_mount and root_mount.exists():
            systemd_dir = root_mount / "etc/systemd/system"
            wants_dir = systemd_dir / "multi-user.target.wants"
            
            for service_name in services:
                service_file = f"{service_name}.service"
                service_path = systemd_dir / service_file
                service_link = wants_dir / service_file
                
                # Check if service exists
                service_exists = service_path.exists()
                results["required_services"][f"{service_name}_exists"] = service_exists
                
                # Check if service is enabled
                service_enabled = service_link.exists()
                results["required_services"][f"{service_name}_enabled"] = service_enabled
                
                if not service_exists:
                    results["missing_services"].append(f"{service_name} (missing)")
                elif not service_enabled:
                    results["missing_services"].append(f"{service_name} (not enabled)")
        
        # Calculate success
        success = len(results["missing_services"]) == 0
        
        return success, results
