#!/usr/bin/env python3
"""
Compression stage for the W4B Raspberry Pi Image Generator.

This module implements the compression stage of the build pipeline,
responsible for unmounting, compressing, and preparing the final image.
"""

import asyncio
import os
import shutil
import json
import datetime  # Ensure datetime is imported here too
from pathlib import Path
from typing import Dict, Any, Optional

from core.stages.base import BuildStage
from utils.error_handling import ImageBuildError


class CompressionStage(BuildStage):
    """
    Build stage for compressing and finalizing the image.
    
    This stage is responsible for unmounting the image, compressing it,
    and preparing it for distribution.
    
    Attributes:
        name (str): Name of the stage
        state (Dict[str, Any]): Shared pipeline state
        logger (logging.Logger): Logger instance
        circuit_breaker (CircuitBreaker): Circuit breaker for fault tolerance
    """
    
    async def execute(self) -> bool:
        """
        Execute the compression stage.
        
        Returns:
            bool: True if compression succeeded, False otherwise
        """
        try:
            # Get image builder from state
            image_builder = self.state["image_builder"]
            image_path = self.state["image_path"]
            
            # Unmount the image
            self.logger.info("Unmounting image")
            await image_builder.unmount_image()
            
            # Update state to reflect unmounting
            self.state["boot_mount"] = None
            self.state["root_mount"] = None
            
            # Compress the image
            self.logger.info("Compressing image")
            output_path = await image_builder.compress_image(image_path)
            
            # Generate checksums
            self.logger.info("Generating checksums")
            checksums = await image_builder.generate_checksum(output_path)
            
            # Update state with compressed image path
            self.state["output_file"] = output_path
            self.state["checksums"] = checksums
            
            # Create metadata file
            await self._create_metadata_file(output_path, checksums)
            
            self.logger.info(f"Compression complete. Output: {output_path}")
            return True
            
        except Exception as e:
            self.logger.exception(f"Compression failed: {str(e)}")
            return False
    
    async def _create_metadata_file(self, output_path: Path, checksums: Dict[str, str]) -> None:
        """
        Create metadata file for the image.
        
        Args:
            output_path: Path to the compressed image
            checksums: Dictionary of checksums
        """
        metadata_path = output_path.with_suffix(".json")
        self.logger.info(f"Creating metadata file: {metadata_path}")
        
        # Create metadata
        metadata = {
            "hive_id": self.state["config"]["hive_id"],
            "version": self.state["config"].get("version", "1.0.0"),
            "created_at": datetime.datetime.now().isoformat(),
            "image_name": output_path.name,
            "image_size": output_path.stat().st_size,
            "checksums": checksums,
            "config": {
                # Include only safe config items (omit passwords, keys, etc.)
                "base_image": self.state["config"].get("base_image", {}),
                "system": {
                    k: v for k, v in self.state["config"].get("system", {}).items()
                    if k not in ["ssh_private_key", "ssh_password"]
                },
                "software": self.state["config"].get("software", {})
            }
        }
        
        # Write metadata file
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
