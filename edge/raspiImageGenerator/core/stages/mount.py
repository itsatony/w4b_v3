"""
Mount stage for Raspberry Pi image generator.
"""

import os
import sys
import asyncio
from pathlib import Path
from typing import Dict, Any

from core.stages.base import BuildStage

class MountStage(BuildStage):
    """
    Build stage for mounting the Raspberry Pi OS image.
    """
    
    async def execute(self) -> bool:
        try:
            self.logger.info("Starting stage: MountStage")
            
            # Check if we have a cached unpacked path from previous stage
            if "cached_unpacked_path" in self.state:
                # Use cached paths
                cached_path = self.state["cached_unpacked_path"]
                self.state["boot_mount"] = cached_path / "boot"
                self.state["root_mount"] = cached_path / "rootfs"
                
                self.logger.info(f"Using cached mount points: boot={self.state['boot_mount']}, root={self.state['root_mount']}")
                
                # Verify the mount points are valid
                if not self._verify_mount_points():
                    self.logger.error("Cached mount points are invalid")
                    return False
                
                # We're using cache, no actual mounting needed
                return True
            
            # Regular mounting logic
            image_path = self.state.get("image_path")
            if not image_path or not Path(image_path).exists():
                self.logger.error("Image path is missing or invalid")
                return False
            
            boot_mount = Path("/mnt/boot")
            root_mount = Path("/mnt/rootfs")
            
            # Ensure mount points exist
            boot_mount.mkdir(parents=True, exist_ok=True)
            root_mount.mkdir(parents=True, exist_ok=True)
            
            # Mount the image
            self.logger.info(f"Mounting image: {image_path}")
            if not await self._mount_image(image_path, boot_mount, root_mount):
                self.logger.error("Failed to mount image")
                return False
            
            self.state["boot_mount"] = boot_mount
            self.state["root_mount"] = root_mount
            
            return True
            
        except Exception as e:
            self.logger.error(f"Mount stage failed: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return False
    
    async def _mount_image(self, image_path: Path, boot_mount: Path, root_mount: Path) -> bool:
        """
        Mount the Raspberry Pi OS image.
        
        Args:
            image_path (Path): Path to the image file.
            boot_mount (Path): Path to the boot mount point.
            root_mount (Path): Path to the root filesystem mount point.
        
        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            # Mount boot partition
            self.logger.info("Mounting boot partition")
            os.system(f"mount -o loop,offset=4194304 {image_path} {boot_mount}")
            
            # Mount root filesystem
            self.logger.info("Mounting root filesystem")
            os.system(f"mount -o loop,offset=10485760 {image_path} {root_mount}")
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to mount image: {str(e)}")
            return False
    
    def _verify_mount_points(self) -> bool:
        """
        Verify that mount points are valid.
        
        Returns:
            bool: True if valid, False otherwise.
        """
        boot_mount = self.state.get("boot_mount")
        root_mount = self.state.get("root_mount")
        
        if not boot_mount or not root_mount:
            return False
            
        # Check for essential directories/files
        if not (boot_mount / "config.txt").exists():
            return False
            
        if not (root_mount / "etc").exists() or not (root_mount / "usr").exists():
            return False
            
        return True