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
    
    async def download_image(self) -> Path:
        """
        Download a Raspberry Pi OS image.
        
        Returns:
            Path: Path to the downloaded image
            
        Raises:
            NetworkError: If download fails
        """
        cache_dir = self.work_dir / "cache"
        cache_dir.mkdir(exist_ok=True)
        
        # Get image URL
        base_image_config = self.config["base_image"]
        version = base_image_config["version"]
        url_template = base_image_config["url_template"]
        url = url_template.format(version=version)
        
        self.logger.info(f"Downloading Raspberry Pi OS image from {url}")
        
        # Generate cache path
        cache_filename = f"raspios_{version}.img.xz"
        cache_path = cache_dir / cache_filename
        
        # Check if already downloaded
        if cache_path.exists():
            self.logger.info(f"Using cached image: {cache_path}")
            
            # Verify checksum if provided
            if base_image_config.get("checksum"):
                if await self._verify_checksum(cache_path, base_image_config["checksum"]):
                    self.logger.info("Checksum verification passed")
                else:
                    self.logger.warning("Checksum verification failed, redownloading")
                    cache_path.unlink()
                    return await self.download_image()
                    
            return cache_path
        
        # Download the image
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise NetworkError(
                            f"Failed to download image: HTTP {response.status}"
                        )
                    
                    # Download with progress tracking
                    total_size = int(response.headers.get("content-length", 0))
                    downloaded = 0
                    
                    with open(cache_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # Log progress every 10%
                            if total_size > 0:
                                progress = downloaded / total_size * 100
                                if progress % 10 < 0.1:  # Log at ~0%, ~10%, ~20%, etc.
                                    self.logger.info(
                                        f"Download progress: {progress:.1f}% "
                                        f"({downloaded/(1024*1024):.1f} MB / "
                                        f"{total_size/(1024*1024):.1f} MB)"
                                    )
            
            self.logger.info(f"Download complete: {cache_path}")
            
            # Verify checksum if provided
            if base_image_config.get("checksum"):
                if await self._verify_checksum(cache_path, base_image_config["checksum"]):
                    self.logger.info("Checksum verification passed")
                else:
                    self.logger.warning("Checksum verification failed, redownloading")
                    cache_path.unlink()
                    return await self.download_image()
            
            return cache_path
            
        except Exception as e:
            # Remove partial download if it exists
            if cache_path.exists():
                cache_path.unlink()
            
            raise NetworkError(f"Image download failed: {str(e)}")
    
    async def _verify_checksum(self, file_path: Path, expected_checksum: str) -> bool:
        """
        Verify the checksum of a file.
        
        Args:
            file_path: Path to the file
            expected_checksum: Expected checksum
            
        Returns:
            bool: True if checksum matches, False otherwise
        """
        self.logger.info(f"Verifying checksum of {file_path}")
        
        # Determine hash algorithm from checksum length
        if len(expected_checksum) == 32:
            hasher = hashlib.md5()
        elif len(expected_checksum) == 40:
            hasher = hashlib.sha1()
        elif len(expected_checksum) == 64:
            hasher = hashlib.sha256()
        else:
            hasher = hashlib.sha256()
        
        # Calculate hash in chunks to avoid loading entire file into memory
        buffer_size = 65536  # 64KB chunks
        
        with open(file_path, "rb") as f:
            while True:
                data = f.read(buffer_size)
                if not data:
                    break
                hasher.update(data)
        
        actual_checksum = hasher.hexdigest()
        
        return actual_checksum.lower() == expected_checksum.lower()
    
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
        """
        Unmount a previously mounted disk image.
        
        Raises:
            DiskOperationError: If unmounting fails
        """
        self.logger.info("Unmounting image")
        
        # Unmount partitions
        if self.root_mount:
            await self._unmount_partition(self.root_mount)
            self.root_mount = None
        
        if self.boot_mount:
            await self._unmount_partition(self.boot_mount)
            self.boot_mount = None
        
        # Detach loop device
        if self.loop_device:
            await self._detach_loop_device(self.loop_device)
            self.loop_device = None
    
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
