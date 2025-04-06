"""
Image Builder for Raspberry Pi OS
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any

class ImageBuilder:
    """
    Builds and modifies Raspberry Pi OS images.
    """
    
    def __init__(self, config: Dict[str, Any], state: Dict[str, Any]):
        self.config = config
        self.state = state
        self.logger = logging.getLogger("ImageBuilder")
        self.using_cache = False

    async def mount_image(self) -> bool:
        """
        Mount the image to modify it.
        
        Returns:
            bool: True if successful, False otherwise
        """
        # Check if we have a cached unpacked image
        if "cached_unpacked_path" in self.state:
            self.logger.info("Using cached unpacked filesystem")
            cached_path = Path(self.state["cached_unpacked_path"])
            
            # Set mount points from cache
            self.state["boot_mount"] = cached_path / "boot"
            self.state["root_mount"] = cached_path / "rootfs"
            
            # Verify the mount points are valid
            if not self._verify_mount_points():
                self.logger.error("Cached mount points are invalid, falling back to regular mounting")
                return await self._mount_image_regular()
                
            self.using_cache = True
            return True
        else:
            # No cache available, use regular mounting
            return await self._mount_image_regular()
    
    async def _mount_image_regular(self) -> bool:
        """
        Mount the image using regular loopback mounting.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            image_path = Path(self.state["image_path"])
            boot_mount = Path(self.state["boot_mount"])
            root_mount = Path(self.state["root_mount"])
            
            # Ensure mount directories exist
            boot_mount.mkdir(parents=True, exist_ok=True)
            root_mount.mkdir(parents=True, exist_ok=True)
            
            # Mount the image
            self.logger.info(f"Mounting image: {image_path}")
            os.system(f"mount -o loop,offset=1048576 {image_path} {root_mount}")
            os.system(f"mount -o loop,offset=524288 {image_path} {boot_mount}")
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to mount image: {str(e)}")
            return False
    
    def _verify_mount_points(self) -> bool:
        """
        Verify that mount points are valid.
        
        Returns:
            bool: True if valid, False otherwise
        """
        boot_mount = self.state.get("boot_mount")
        root_mount = self.state.get("root_mount")
        
        if not boot_mount or not root_mount:
            return False
            
        # Check for essential directories/files
        if not (Path(boot_mount) / "config.txt").exists():
            return False
            
        if not (Path(root_mount) / "etc").exists() or not (Path(root_mount) / "usr").exists():
            return False
            
        return True
    
    async def unmount_image(self) -> bool:
        """
        Unmount the image after modification.
        
        Returns:
            bool: True if successful, False otherwise
        """
        # If we're using a cached unpacked image, no need to unmount
        if self.using_cache:
            self.logger.info("Using cached image, no unmounting needed")
            return True
        
        try:
            boot_mount = Path(self.state["boot_mount"])
            root_mount = Path(self.state["root_mount"])
            
            # Unmount the image
            self.logger.info("Unmounting image")
            os.system(f"umount {root_mount}")
            os.system(f"umount {boot_mount}")
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to unmount image: {str(e)}")
            return False