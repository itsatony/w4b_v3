"""
Image Builder for Raspberry Pi OS
"""

import os
import logging
import asyncio
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
        Mount the image using robust loop device handling.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Force detach any existing loop devices for this image
            await self._force_detach_existing_loops(self.state["image_path"])
            
            # Use losetup with -P flag to force kernel to scan partition table
            result = await asyncio.create_subprocess_exec(
                'losetup', '-P', '-f', '--show', str(self.state["image_path"]),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                self.logger.error(f"Failed to set up loop device: {stderr.decode().strip()}")
                return False
            
            self.loop_device = stdout.decode().strip()
            if not self.loop_device:
                self.logger.error("Failed to get loop device path")
                return False
                
            self.logger.info(f"Loop device: {self.loop_device}")
            
            # Wait for partitions to be recognized (important!)
            self.logger.info("Waiting for kernel to recognize partitions...")
            await asyncio.sleep(2)
            
            # Debug: List the loop device partitions
            self._debug_partitions(self.loop_device)
            
            # Create mount points
            self.boot_mount = Path(f"/tmp/w4b_mount_{os.getpid()}_boot")
            self.root_mount = Path(f"/tmp/w4b_mount_{os.getpid()}_root")
            
            self.boot_mount.mkdir(parents=True, exist_ok=True)
            self.root_mount.mkdir(parents=True, exist_ok=True)
            
            # Find partitions using multiple methods
            boot_part, root_part = await self._find_partitions(self.loop_device)
            
            if not boot_part or not root_part:
                self.logger.error("Failed to find partitions")
                await self._cleanup_loop_device(self.loop_device)
                return False
                
            # Mount boot partition
            self.logger.info(f"Mounting boot partition: {boot_part} -> {self.boot_mount}")
            boot_result = await asyncio.create_subprocess_exec(
                'mount', boot_part, str(self.boot_mount),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            boot_stdout, boot_stderr = await boot_result.communicate()
            
            if boot_result.returncode != 0:
                self.logger.error(f"Failed to mount boot partition: {boot_stderr.decode().strip()}")
                await self._cleanup_loop_device(self.loop_device)
                return False
            
            # Mount root partition
            self.logger.info(f"Mounting root partition: {root_part} -> {self.root_mount}")
            root_result = await asyncio.create_subprocess_exec(
                'mount', root_part, str(self.root_mount),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            root_stdout, root_stderr = await root_result.communicate()
            
            if root_result.returncode != 0:
                self.logger.error(f"Failed to mount root partition: {root_stderr.decode().strip()}")
                # Clean up boot mount
                await asyncio.create_subprocess_exec('umount', str(self.boot_mount))
                await self._cleanup_loop_device(self.loop_device)
                return False
            
            # Store mount points in state
            self.state["boot_mount"] = self.boot_mount
            self.state["root_mount"] = self.root_mount
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to mount image: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            
            # Clean up any resources
            if hasattr(self, 'loop_device') and self.loop_device:
                await self._cleanup_loop_device(self.loop_device)
            return False
    
    async def _force_detach_existing_loops(self, image_path: Path) -> None:
        """Forcibly detach any existing loop devices for this image"""
        try:
            # Find if the image is already attached to a loop device
            result = await asyncio.create_subprocess_exec(
                'losetup', '-j', str(image_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            
            if stdout:
                attached_loops = stdout.decode().strip().split('\n')
                for line in attached_loops:
                    if not line:
                        continue
                        
                    # Extract loop device path
                    loop_dev = line.split(':')[0]
                    self.logger.info(f"Detaching existing loop device: {loop_dev}")
                    
                    # Try to detach the loop device
                    await asyncio.create_subprocess_exec(
                        'losetup', '-d', loop_dev,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
        except Exception as e:
            self.logger.warning(f"Error detaching existing loop devices: {str(e)}")

    def _debug_partitions(self, loop_device: str) -> None:
        """Debug partitions of the loop device"""
        try:
            self.logger.info(f"Debugging partitions for {loop_device}")
            
            # List device nodes
            import glob
            partitions = glob.glob(f"{loop_device}*")
            self.logger.info(f"Found partition nodes: {partitions}")
            
            # Run fdisk to show partition table
            os.system(f"fdisk -l {loop_device} > /tmp/fdisk_debug.txt")
            with open('/tmp/fdisk_debug.txt', 'r') as f:
                self.logger.info(f"Partition table:\n{f.read()}")
        except Exception as e:
            self.logger.warning(f"Error debugging partitions: {str(e)}")

    async def _find_partitions(self, loop_device: str) -> tuple:
        """Find partitions using multiple methods"""
        # Try different partition naming schemes
        boot_part = None
        root_part = None
        
        # List of partition naming schemes to try
        naming_schemes = [
            (f"{loop_device}p1", f"{loop_device}p2"),      # loop0p1, loop0p2
            (f"{loop_device}1", f"{loop_device}2"),        # loop01, loop02
        ]
        
        # Try each naming scheme
        for boot_candidate, root_candidate in naming_schemes:
            self.logger.info(f"Checking partition naming scheme: {boot_candidate}, {root_candidate}")
            if Path(boot_candidate).exists() and Path(root_candidate).exists():
                boot_part = boot_candidate
                root_part = root_candidate
                return boot_part, root_part
        
        # If we're here, we need to try kpartx
        self.logger.info("Standard partition naming not found, trying kpartx")
        kpartx_result = await asyncio.create_subprocess_exec(
            'kpartx', '-avs', loop_device,  # Added -s for sync mode
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        kpartx_stdout, kpartx_stderr = await kpartx_result.communicate()
        
        self.logger.info(f"kpartx output: {kpartx_stdout.decode()}")
        if kpartx_stderr:
            self.logger.info(f"kpartx stderr: {kpartx_stderr.decode()}")
        
        # Wait for device mapper to create nodes
        await asyncio.sleep(3)
        
        # Check device mapper nodes
        loop_name = os.path.basename(loop_device)
        mapper_candidates = [
            (f"/dev/mapper/{loop_name}p1", f"/dev/mapper/{loop_name}p2"),
            (f"/dev/mapper/{loop_name.replace('loop', '')}p1", f"/dev/mapper/{loop_name.replace('loop', '')}p2"),
            (f"/dev/mapper/loop{loop_name.replace('loop', '')}p1", f"/dev/mapper/loop{loop_name.replace('loop', '')}p2")
        ]
        
        for boot_candidate, root_candidate in mapper_candidates:
            self.logger.info(f"Checking mapper devices: {boot_candidate}, {root_candidate}")
            if Path(boot_candidate).exists() and Path(root_candidate).exists():
                boot_part = boot_candidate
                root_part = root_candidate
                return boot_part, root_part
        
        # Last resort: try to find any device mapper partitions
        mapper_dir = Path("/dev/mapper")
        if mapper_dir.exists():
            self.logger.info("Searching for any usable mapper devices...")
            mapper_devices = list(mapper_dir.glob("*"))
            self.logger.info(f"Found mapper devices: {mapper_devices}")
            
            # Look for devices that might be our partitions
            potential_boots = [d for d in mapper_devices if "p1" in d.name or d.name.endswith("1")]
            for potential_boot in potential_boots:
                potential_root = Path(str(potential_boot).replace("p1", "p2").replace("1", "2"))
                if potential_root.exists():
                    self.logger.info(f"Found potential mapper devices: {potential_boot}, {potential_root}")
                    boot_part = str(potential_boot)
                    root_part = str(potential_root)
                    return boot_part, root_part
        
        # Nothing worked, give up
        return None, None

    async def _cleanup_loop_device(self, loop_device: str) -> None:
        """Clean up loop device resources"""
        try:
            # First clean up kpartx mappings if they exist
            self.logger.info("Cleaning up kpartx mappings...")
            kpartx_result = await asyncio.create_subprocess_exec(
                'kpartx', '-d', loop_device,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            kpartx_stdout, kpartx_stderr = await kpartx_result.communicate()
            
            if kpartx_stderr:
                self.logger.info(f"kpartx cleanup stderr: {kpartx_stderr.decode()}")
            
            # Now detach the loop device
            self.logger.info(f"Detaching loop device: {loop_device}")
            detach_result = await asyncio.create_subprocess_exec(
                'losetup', '-d', loop_device,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await detach_result.communicate()
            
            if detach_result.returncode != 0:
                self.logger.warning(f"Failed to detach loop device: {stderr.decode()}")
        except Exception as e:
            self.logger.warning(f"Error cleaning up loop device: {str(e)}")

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