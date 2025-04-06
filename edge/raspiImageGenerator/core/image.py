#!/usr/bin/env python3
"""
Disk image management for the W4B Raspberry Pi Image Generator.

This module provides functionality for downloading, mounting, modifying,
and compressing Raspberry Pi OS disk images.
"""

import asyncio
import aiohttp
import hashlib
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union

from utils.error_handling import DiskOperationError, NetworkError, retry


class ImageBuilder:
    """
    Manager for Raspberry Pi OS disk image operations.
    
    This class handles disk image download, verification, mounting,
    modification, and compression operations.
    
    Attributes:
        config (Dict[str, Any]): Configuration dictionary
        work_dir (Path): Working directory
        logger (logging.Logger): Logger instance
        image_path (Optional[Path]): Path to the image file
        boot_mount (Optional[Path]): Path where boot partition is mounted
        root_mount (Optional[Path]): Path where root partition is mounted
        loop_device (Optional[str]): Loop device path
    """
    
    def __init__(self, config: Dict[str, Any], work_dir: Path):
        """
        Initialize the image builder.
        
        Args:
            config: Configuration dictionary
            work_dir: Working directory
        """
        self.config = config
        self.work_dir = work_dir
        self.logger = logging.getLogger("image_builder")
        
        self.image_path = None
        self.boot_mount = None
        self.root_mount = None
        self.loop_device = None

        self.cache_dir = work_dir / "cache"
        self.extracted_cache_dir = self.cache_dir / "extracted"
        self.downloads_cache_dir = self.cache_dir / "downloads"
        
        # Create cache directories if they don't exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.extracted_cache_dir.mkdir(parents=True, exist_ok=True)
        self.downloads_cache_dir.mkdir(parents=True, exist_ok=True)
    
    async def get_base_image(self, url: str, checksum: str = None, checksum_type: str = "sha256") -> Path:
        """
        Get the base image, either from cache or by downloading.
        
        Args:
            url: URL to download from if not cached
            checksum: Optional checksum for verification
            checksum_type: Checksum algorithm (sha256, md5, etc.)
            
        Returns:
            Path to the image
        """
        # Generate a filename based on the URL
        filename = Path(url).name
        download_path = self.downloads_cache_dir / filename
        
        # Check if we have a cached download
        if download_path.exists():
            self.logger.info(f"Found cached download: {download_path}")
            
            # Verify checksum if provided
            if checksum:
                if await self._verify_checksum(download_path, checksum, checksum_type):
                    self.logger.info("Checksum verification passed for cached download")
                else:
                    self.logger.warning("Checksum verification failed for cached download, re-downloading")
                    await self.download_image(url, download_path)
        else:
            # Download the image
            self.logger.info(f"Downloading image from {url}")
            await self.download_image(url, download_path)
            
            # Verify checksum if provided
            if checksum and not await self._verify_checksum(download_path, checksum, checksum_type):
                raise ValueError(f"Checksum verification failed for downloaded image")
        
        # Check if we need to extract the image
        if filename.endswith(".xz"):
            # Check if we have a cached extracted version
            extracted_filename = filename[:-3]  # Remove .xz extension
            extracted_path = self.extracted_cache_dir / extracted_filename
            
            if extracted_path.exists():
                self.logger.info(f"Found cached extracted image: {extracted_path}")
                return extracted_path
            else:
                # Extract the image
                self.logger.info(f"Extracting image: {download_path}")
                extracted_path = await self._extract_image(download_path, extracted_path)
                return extracted_path
        
        # If it's not compressed, just return the downloaded path
        return download_path
    
    async def download_image(self, url: str, output_path: Path) -> Path:
        """
        Download a Raspberry Pi OS image.
        
        Args:
            url: URL to download from
            output_path: Path to save the downloaded file
            
        Returns:
            Path to the downloaded file
        """
        # Ensure parent directories exist
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise ValueError(f"Failed to download image: {response.status} {response.reason}")
                    
                    # Write the response content to file
                    with open(output_path, 'wb') as f:
                        while True:
                            chunk = await response.content.read(1024 * 1024)  # 1MB chunks
                            if not chunk:
                                break
                            f.write(chunk)
            
            return output_path
            
        except Exception as e:
            if output_path.exists():
                output_path.unlink()  # Remove partial download on error
            raise ValueError(f"Image download failed: {str(e)}")
    
    async def _extract_image(self, source_path: Path, target_path: Path) -> Path:
        """Extract a compressed image."""
        # Ensure target directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        if source_path.suffix == ".xz":
            # Use xz to decompress
            process = await asyncio.create_subprocess_exec(
                'xz', '--decompress', '--keep', '--stdout', str(source_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Write output to file
            with open(target_path, 'wb') as f:
                while True:
                    chunk = await process.stdout.read(1024 * 1024)  # 1MB chunks
                    if not chunk:
                        break
                    f.write(chunk)
            
            stderr = await process.stderr.read()
            await process.wait()
            
            if process.returncode != 0:
                raise RuntimeError(f"Failed to extract image: {stderr.decode()}")
            
            return target_path
        else:
            # Just copy the file if it's not compressed
            shutil.copy2(source_path, target_path)
            return target_path
    
    async def _verify_checksum(self, file_path: Path, expected_checksum: str, checksum_type: str = "sha256") -> bool:
        """Verify file checksum."""
        hash_obj = None
        
        if checksum_type == "sha256":
            hash_obj = hashlib.sha256()
        elif checksum_type == "md5":
            hash_obj = hashlib.md5()
        else:
            raise ValueError(f"Unsupported checksum type: {checksum_type}")
        
        with open(file_path, 'rb') as f:
            while True:
                data = f.read(65536)  # 64K chunks
                if not data:
                    break
                hash_obj.update(data)
        
        calculated_checksum = hash_obj.hexdigest()
        return calculated_checksum.lower() == expected_checksum.lower()
    
    async def extract_image(self, image_path: Path) -> Path:
        """
        Extract a compressed Raspberry Pi OS image.
        
        Args:
            image_path: Path to the compressed image
            
        Returns:
            Path: Path to the extracted image
        """
        self.logger.info(f"Extracting image: {image_path}")
        
        # Generate output path
        output_path = self.work_dir / f"raspios_{self.config['hive_id']}.img"
        
        # Check if already extracted
        if output_path.exists():
            self.logger.info(f"Using existing extracted image: {output_path}")
            return output_path
        
        # Extract based on file extension
        if str(image_path).endswith(".xz"):
            self.logger.info("Extracting XZ compressed image")
            
            # Run xz decompression
            cmd = ["xz", "--decompress", "--stdout", str(image_path)]
            
            try:
                with open(output_path, "wb") as f:
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=f,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    _, stderr = await process.communicate()
                    
                    if process.returncode != 0:
                        raise DiskOperationError(
                            f"Image extraction failed with code {process.returncode}: "
                            f"{stderr.decode().strip()}"
                        )
                
                self.logger.info(f"Image extraction complete: {output_path}")
                return output_path
                
            except Exception as e:
                # Remove partial extraction if it exists
                if output_path.exists():
                    output_path.unlink()
                
                raise DiskOperationError(f"Image extraction failed: {str(e)}")
                
        elif str(image_path).endswith(".zip"):
            # TODO: Implement ZIP extraction if needed
            raise NotImplementedError("ZIP extraction not yet implemented")
            
        else:
            # Just copy the file
            shutil.copy(image_path, output_path)
            return output_path
    
    @retry(max_retries=3, delay=1.0, exceptions=(DiskOperationError,))
    async def mount_image(self, image_path: Path) -> Tuple[Path, Path]:
        """
        Mount a Raspberry Pi OS image for modification.
        
        Args:
            image_path: Path to the disk image
            
        Returns:
            Tuple[Path, Path]: Paths to the boot and root partition mounts
            
        Raises:
            DiskOperationError: If mounting fails
        """
        self.logger.info(f"Mounting image: {image_path}")
        
        # Create mount points
        boot_mount = self.work_dir / "boot"
        root_mount = self.work_dir / "rootfs"
        
        boot_mount.mkdir(exist_ok=True)
        root_mount.mkdir(exist_ok=True)
        
        # Create loop device
        try:
            # Find free loop device
            loop_cmd = ["losetup", "-f"]
            process = await asyncio.create_subprocess_exec(
                *loop_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise DiskOperationError(
                    f"Failed to find free loop device: {stderr.decode().strip()}"
                )
            
            loop_device = stdout.decode().strip()
            
            # Set up loop device with partition scanning
            setup_cmd = ["losetup", "-P", loop_device, str(image_path)]
            process = await asyncio.create_subprocess_exec(
                *setup_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            _, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise DiskOperationError(
                    f"Failed to set up loop device: {stderr.decode().strip()}"
                )
            
            self.loop_device = loop_device
            self.logger.info(f"Created loop device: {loop_device}")
            
            # Wait for partition device nodes to appear
            for _ in range(10):  # Wait up to 10 seconds
                if (Path(f"{loop_device}p1").exists() and 
                    Path(f"{loop_device}p2").exists()):
                    break
                await asyncio.sleep(1)
            else:
                raise DiskOperationError(
                    f"Partition device nodes did not appear for {loop_device}"
                )
            
            # Mount boot partition
            boot_cmd = ["mount", f"{loop_device}p1", str(boot_mount)]
            process = await asyncio.create_subprocess_exec(
                *boot_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            _, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise DiskOperationError(
                    f"Failed to mount boot partition: {stderr.decode().strip()}"
                )
            
            self.boot_mount = boot_mount
            self.logger.info(f"Mounted boot partition at {boot_mount}")
            
            # Mount root partition
            root_cmd = ["mount", f"{loop_device}p2", str(root_mount)]
            process = await asyncio.create_subprocess_exec(
                *root_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            _, stderr = await process.communicate()
            
            if process.returncode != 0:
                # Unmount boot and detach loop if root fails
                await self._unmount_partition(boot_mount)
                await self._detach_loop_device(loop_device)
                
                raise DiskOperationError(
                    f"Failed to mount root partition: {stderr.decode().strip()}"
                )
            
            self.root_mount = root_mount
            self.logger.info(f"Mounted root partition at {root_mount}")
            
            return boot_mount, root_mount
            
        except Exception as e:
            # Clean up on failure
            if self.boot_mount:
                await self._unmount_partition(self.boot_mount)
                self.boot_mount = None
            
            if self.root_mount:
                await self._unmount_partition(self.root_mount)
                self.root_mount = None
            
            if self.loop_device:
                await self._detach_loop_device(self.loop_device)
                self.loop_device = None
            
            raise DiskOperationError(f"Failed to mount image: {str(e)}")
    
    async def unmount_image(self) -> None:
        """Unmount any mounted partitions and detach loop devices."""
        self.logger.info("Unmounting image")
        
        # Check if there are mount points in the build state
        if hasattr(self, 'build_state'):
            # Unmount root first (must be in reverse order of mounting)
            if "root_mount" in self.build_state:
                root_mount = self.build_state["root_mount"]
                self.logger.debug(f"Unmounting root partition: {root_mount}")
                try:
                    process = await asyncio.create_subprocess_exec(
                        'umount', str(root_mount),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    _, stderr = await process.communicate()
                    if process.returncode != 0:
                        self.logger.warning(f"Failed to unmount root partition: {stderr.decode()}")
                except Exception as e:
                    self.logger.warning(f"Error unmounting root partition: {str(e)}")
            
            # Then unmount boot
            if "boot_mount" in self.build_state:
                boot_mount = self.build_state["boot_mount"]
                self.logger.debug(f"Unmounting boot partition: {boot_mount}")
                try:
                    process = await asyncio.create_subprocess_exec(
                        'umount', str(boot_mount),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    _, stderr = await process.communicate()
                    if process.returncode != 0:
                        self.logger.warning(f"Failed to unmount boot partition: {stderr.decode()}")
                except Exception as e:
                    self.logger.warning(f"Error unmounting boot partition: {str(e)}")
            
            # Finally detach any loop devices
            if "loop_device" in self.build_state:
                loop_device = self.build_state["loop_device"]
                self.logger.debug(f"Detaching loop device: {loop_device}")
                try:
                    process = await asyncio.create_subprocess_exec(
                        'losetup', '--detach', loop_device,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    _, stderr = await process.communicate()
                    if process.returncode != 0:
                        self.logger.warning(f"Failed to detach loop device: {stderr.decode()}")
                except Exception as e:
                    self.logger.warning(f"Error detaching loop device: {str(e)}")
        
        # Sync filesystem to ensure all changes are written
        await asyncio.create_subprocess_exec('sync')
    
    async def _unmount_partition(self, mount_point: Path) -> None:
        """
        Unmount a partition.
        
        Args:
            mount_point: Mount point to unmount
            
        Raises:
            DiskOperationError: If unmounting fails
        """
        self.logger.info(f"Unmounting partition at {mount_point}")
        
        # Try unmounting with increasing force
        for attempt, options in enumerate([[], ["-l"], ["-f"]]):
            cmd = ["umount"] + options + [str(mount_point)]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            _, stderr = await process.communicate()
            
            if process.returncode == 0:
                self.logger.info(f"Successfully unmounted {mount_point}")
                return
            
            if attempt < 2:  # Don't wait after the last attempt
                self.logger.warning(
                    f"Unmount attempt {attempt + 1} failed: {stderr.decode().strip()}. "
                    f"Trying with more force..."
                )
                await asyncio.sleep(1)
        
        self.logger.error(f"Failed to unmount {mount_point} after multiple attempts")
        raise DiskOperationError(f"Could not unmount {mount_point}")
    
    async def _detach_loop_device(self, loop_device: str) -> None:
        """
        Detach a loop device.
        
        Args:
            loop_device: Loop device to detach
            
        Raises:
            DiskOperationError: If detaching fails
        """
        self.logger.info(f"Detaching loop device {loop_device}")
        
        cmd = ["losetup", "-d", loop_device]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        _, stderr = await process.communicate()
        
        if process.returncode != 0:
            self.logger.error(
                f"Failed to detach loop device: {stderr.decode().strip()}"
            )
            raise DiskOperationError(f"Could not detach loop device {loop_device}")
        
        self.logger.info(f"Successfully detached {loop_device}")
    
    async def compress_image(self, image_path: Path) -> Path:
        """
        Compress a disk image for distribution.
        
        Args:
            image_path: Path to the image to compress
            
        Returns:
            Path: Path to the compressed image
        """
        self.logger.info(f"Compressing image: {image_path}")
        
        # Generate output filename
        timestamp = self.config.get("timestamp", datetime.now().strftime("%Y%m%d-%H%M%S"))
        hive_id = self.config["hive_id"]
        output_filename = f"{timestamp}_{hive_id}.img.xz"
        
        # Get output directory from config or use work_dir
        output_dir = Path(self.config["output"]["directory"])
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = output_dir / output_filename
        
        # Run xz compression
        cmd = ["xz", "--threads=0", "-9", "-c", str(image_path)]
        
        try:
            with open(output_path, "wb") as f:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=f,
                    stderr=asyncio.subprocess.PIPE
                )
                
                _, stderr = await process.communicate()
                
                if process.returncode != 0:
                    raise DiskOperationError(
                        f"Image compression failed with code {process.returncode}: "
                        f"{stderr.decode().strip()}"
                    )
            
            self.logger.info(f"Image compression complete: {output_path}")
            return output_path
            
        except Exception as e:
            # Remove partial compression if it exists
            if output_path.exists():
                output_path.unlink()
            
            raise DiskOperationError(f"Image compression failed: {str(e)}")
    
    async def generate_checksum(self, file_path: Path) -> Dict[str, str]:
        """
        Generate checksums for a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dict[str, str]: Dictionary of hash algorithms to checksums
        """
        self.logger.info(f"Generating checksums for {file_path}")
        
        algorithms = {
            "md5": hashlib.md5(),
            "sha1": hashlib.sha1(),
            "sha256": hashlib.sha256()
        }
        
        # Calculate hashes in chunks
        buffer_size = 65536  # 64KB chunks
        
        with open(file_path, "rb") as f:
            while True:
                data = f.read(buffer_size)
                if not data:
                    break
                for hasher in algorithms.values():
                    hasher.update(data)
        
        checksums = {name: hasher.hexdigest() for name, hasher in algorithms.items()}
        
        return checksums
