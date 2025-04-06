#!/usr/bin/env python3
"""
Cache manager for Raspberry Pi image generator.

This module handles caching of downloaded images and unpacked filesystems
to improve performance and reduce network usage.
"""

import os
import shutil
import hashlib
import logging
import time
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

class CacheManager:
    """
    Manages caching of downloaded images and unpacked filesystems.
    
    The cache uses a deterministic directory structure based on image properties
    to enable efficient reuse across multiple runs.
    """
    
    def __init__(self, base_dir: Path, max_age_days: int = 30, max_size_gb: int = 20):
        """
        Initialize the cache manager.
        
        Args:
            base_dir: Base directory for the cache
            max_age_days: Maximum age of cache entries in days
            max_size_gb: Maximum size of the cache in GB
        """
        self.base_dir = base_dir
        self.max_age_days = max_age_days
        self.max_size_gb = max_size_gb
        self.logger = logging.getLogger("cache_manager")
        
        # Ensure cache directories exist
        self.downloads_dir = base_dir / "downloads"
        self.unpacked_dir = base_dir / "unpacked"
        self.metadata_dir = base_dir / "metadata"
        
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.unpacked_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
    
    def get_cache_key(self, image_info: Dict[str, Any]) -> str:
        """
        Generate a deterministic cache key based on image properties.
        
        Args:
            image_info: Dictionary containing image information
            
        Returns:
            str: Cache key for the image
        """
        # Create a hash from version and checksum
        version = image_info.get("version", "unknown")
        checksum = image_info.get("checksum", "")
        model = image_info.get("model", "generic")
        
        # Create a unique but deterministic key
        key_parts = f"{version}_{model}_{checksum}"
        return hashlib.md5(key_parts.encode()).hexdigest()
    
    def get_download_path(self, image_info: Dict[str, Any]) -> Path:
        """
        Get the path where the downloaded image should be stored.
        
        Args:
            image_info: Dictionary containing image information
            
        Returns:
            Path: Path for the downloaded image
        """
        cache_key = self.get_cache_key(image_info)
        filename = os.path.basename(image_info.get("url", "image.img"))
        return self.downloads_dir / cache_key / filename
    
    def get_unpacked_path(self, image_info: Dict[str, Any]) -> Path:
        """
        Get the path to the unpacked (extracted) image.
        
        Args:
            image_info: Dictionary containing image information
            
        Returns:
            Path: Path to the unpacked image
        """
        # Unpacked image path does not have the compression extension
        download_path = self.get_download_path(image_info)
        return download_path.with_suffix("")  # Remove file extension
    
    def is_cached(self, image_info: Dict[str, Any]) -> Tuple[bool, bool]:
        """
        Check if image is already cached.
        
        Args:
            image_info: Dictionary containing image information
            
        Returns:
            Tuple[bool, bool]: (is_download_cached, is_unpacked_cached)
        """
        download_path = self.get_download_path(image_info)
        unpacked_path = self.get_unpacked_path(image_info)
        
        # Check if download file exists and is valid
        download_cached = download_path.exists() and self._validate_download(download_path, image_info)
        
        # Check if unpacked file exists and is valid
        unpacked_cached = unpacked_path.exists() and self._validate_unpacked(unpacked_path)
        
        # Log caching status
        if download_cached:
            self.logger.info(f"Download cached: {download_path}")
        if unpacked_cached:
            self.logger.info(f"Unpacked cached: {unpacked_path}")
        
        # If the downloaded file exists but is invalid, clean it up
        if download_path.exists() and not download_cached:
            self.logger.warning(f"Found corrupt cached file: {download_path}, removing it")
            try:
                download_path.unlink()
            except Exception as e:
                self.logger.error(f"Failed to remove corrupt cache file: {str(e)}")
        
        # If the unpacked directory exists but is invalid, clean it up
        if unpacked_path.exists() and not unpacked_cached:
            self.logger.warning(f"Found corrupt cached unpacked file: {unpacked_path}, removing it")
            try:
                unpacked_path.unlink()
            except Exception as e:
                self.logger.error(f"Failed to remove corrupt cache file: {str(e)}")
        
        return download_cached, unpacked_cached
    
    def _validate_download(self, path: Path, image_info: Dict[str, Any]) -> bool:
        """
        Validate a downloaded image file.
        
        Args:
            path: Path to the downloaded file
            image_info: Dictionary containing image information
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not path.exists():
            return False
            
        file_size = path.stat().st_size
        if file_size == 0:
            self.logger.warning(f"Cached file is empty: {path}")
            return False
            
        self.logger.info(f"Cached file size: {file_size / (1024*1024):.2f} MB")
        
        # Validate file signature for compressed formats
        if path.suffix.lower() == '.xz':
            try:
                with open(path, 'rb') as f:
                    header = f.read(6)
                    
                if len(header) < 6 or header[0] != 0xFD or header[1:6] != b'7zXZ\x00':
                    self.logger.warning(f"Cached XZ file has invalid header: {path}")
                    return False
            except Exception as e:
                self.logger.warning(f"Failed to validate XZ header: {str(e)}")
                return False
        
        # If checksum is provided, verify it
        checksum = image_info.get("checksum")
        checksum_type = image_info.get("checksum_type", "sha256")
        
        if checksum:
            calc_checksum = self._calculate_checksum(path, checksum_type)
            if calc_checksum != checksum:
                self.logger.warning(f"Checksum mismatch for {path}: expected {checksum}, got {calc_checksum}")
                return False
        
        return True
    
    def _validate_unpacked(self, path: Path) -> bool:
        """
        Validate an unpacked image file.
        
        Args:
            path: Path to the unpacked file
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not path.exists():
            return False
            
        file_size = path.stat().st_size
        if file_size == 0:
            self.logger.warning(f"Unpacked file is empty: {path}")
            return False
            
        self.logger.info(f"Unpacked file size: {file_size / (1024*1024):.2f} MB")
        
        # Basic validation for image files - check for boot sector signature
        try:
            with open(path, 'rb') as f:
                boot_sector = f.read(512)
                if len(boot_sector) >= 512:
                    # Look for the boot sector signature (0x55, 0xAA at offset 510-511)
                    if boot_sector[510:512] != b'\x55\xAA':
                        self.logger.warning(f"Unpacked file doesn't have a valid boot sector signature: {path}")
                        return False
                else:
                    self.logger.warning(f"Unpacked file too small for boot sector: {path}")
                    return False
        except Exception as e:
            self.logger.warning(f"Failed to validate boot sector: {str(e)}")
            return False
        
        return True
    
    def _calculate_checksum(self, path: Path, algorithm: str = "sha256") -> str:
        """
        Calculate checksum for a file.
        
        Args:
            path: Path to the file
            algorithm: Checksum algorithm to use
            
        Returns:
            str: Calculated checksum
        """
        hash_func = getattr(hashlib, algorithm, hashlib.sha256)()
        
        with open(path, "rb") as f:
            # Read in chunks to avoid loading large files into memory
            for chunk in iter(lambda: f.read(4096), b""):
                hash_func.update(chunk)
                
        return hash_func.hexdigest()
    
    def clean_cache(self) -> None:
        """
        Clean the cache based on age and size limits.
        """
        self.logger.info("Cleaning cache...")
        
        # Delete old entries
        self._clean_old_entries()
        
        # Check total size and remove oldest entries if needed
        self._enforce_size_limit()
        
        self.logger.info("Cache cleaning completed")
    
    def _clean_old_entries(self) -> None:
        """
        Delete cache entries older than max_age_days.
        """
        now = time.time()
        max_age_seconds = self.max_age_days * 24 * 60 * 60
        
        # Check downloads
        for entry in self.downloads_dir.glob("*/*"):
            if entry.is_file() and entry.stat().st_mtime < (now - max_age_seconds):
                self.logger.info(f"Removing old download: {entry}")
                entry.unlink()
                
                # Remove parent directory if empty
                parent = entry.parent
                if not any(parent.iterdir()):
                    parent.rmdir()
        
        # Check unpacked
        for entry in self.unpacked_dir.glob("*"):
            if entry.is_dir() and entry.stat().st_mtime < (now - max_age_seconds):
                self.logger.info(f"Removing old unpacked image: {entry}")
                shutil.rmtree(entry, ignore_errors=True)
    
    def _enforce_size_limit(self) -> None:
        """
        Enforce the maximum cache size by removing oldest entries.
        """
        # Get total size
        total_size = self._get_cache_size()
        max_size_bytes = self.max_size_gb * 1024 * 1024 * 1024
        
        if total_size <= max_size_bytes:
            return
            
        # List entries by modification time
        entries = []
        
        # Downloads
        for entry in self.downloads_dir.glob("*/*"):
            if entry.is_file():
                entries.append((entry, entry.stat().st_mtime, entry.stat().st_size))
        
        # Unpacked
        for entry in self.unpacked_dir.glob("*"):
            if entry.is_dir():
                size = sum(f.stat().st_size for f in entry.glob("**/*") if f.is_file())
                entries.append((entry, entry.stat().st_mtime, size))
        
        # Sort by modification time (oldest first)
        entries.sort(key=lambda x: x[1])
        
        # Remove entries until we're under the limit
        for entry, mtime, size in entries:
            if total_size <= max_size_bytes:
                break
                
            self.logger.info(f"Removing to enforce size limit: {entry}")
            if entry.is_file():
                entry.unlink()
                
                # Remove parent directory if empty
                parent = entry.parent
                if not any(parent.iterdir()):
                    parent.rmdir()
            else:
                shutil.rmtree(entry, ignore_errors=True)
                
            total_size -= size
    
    def _get_cache_size(self) -> int:
        """
        Calculate the total size of the cache in bytes.
        
        Returns:
            int: Cache size in bytes
        """
        total_size = 0
        
        # Downloads
        for entry in self.downloads_dir.glob("**/*"):
            if entry.is_file():
                total_size += entry.stat().st_size
        
        # Unpacked
        for entry in self.unpacked_dir.glob("**/*"):
            if entry.is_file():
                total_size += entry.stat().st_size
        
        return total_size
    
    def save_metadata(self, image_info: Dict[str, Any]) -> None:
        """
        Save metadata for a cached image.
        
        Args:
            image_info: Dictionary containing image information
        """
        cache_key = self.get_cache_key(image_info)
        metadata_path = self.metadata_dir / f"{cache_key}.json"
        
        import json
        with open(metadata_path, "w") as f:
            json.dump(image_info, f, indent=2)
    
    def get_metadata(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a cached image.
        
        Args:
            cache_key: Cache key for the image
            
        Returns:
            Optional[Dict[str, Any]]: Image metadata if available
        """
        metadata_path = self.metadata_dir / f"{cache_key}.json"
        
        if not metadata_path.exists():
            return None
            
        import json
        with open(metadata_path, "r") as f:
            return json.load(f)
    
    def unpack_image(self, image_info: Dict[str, Any], image_path: Path) -> Optional[Path]:
        """
        Unpack an image to a directory structure for easier manipulation.
        
        Args:
            image_info: Dictionary containing image information
            image_path: Path to the downloaded image
            
        Returns:
            Optional[Path]: Path to the unpacked directory if successful, None otherwise
        """
        try:
            cache_key = self.get_cache_key(image_info)
            unpacked_path = self.get_unpacked_path(image_info)
            
            # Check if already unpacked
            if self._validate_unpacked(unpacked_path):
                self.logger.info(f"Using cached unpacked image: {unpacked_path}")
                return unpacked_path
                
            # Create directories
            unpacked_path.mkdir(parents=True, exist_ok=True)
            boot_dir = unpacked_path / "boot"
            rootfs_dir = unpacked_path / "rootfs"
            boot_dir.mkdir(exist_ok=True)
            rootfs_dir.mkdir(exist_ok=True)
            
            # Set up loop device
            self.logger.info(f"Setting up loop device for: {image_path}")
            loop_result = subprocess.run(
                ['losetup', '-f', '--show', str(image_path)],
                capture_output=True, text=True, check=True
            )
            loop_device = loop_result.stdout.strip()
            
            try:
                # Ensure partitions are detected
                subprocess.run(['partprobe', loop_device], check=True)
                
                # Wait a moment for partitions to be available
                time.sleep(1)
                
                # Determine partition devices
                boot_part = f"{loop_device}p1"
                root_part = f"{loop_device}p2"
                
                # Check if partitions exist with this naming scheme
                if not Path(boot_part).exists() or not Path(root_part).exists():
                    # Try alternate naming (without 'p')
                    boot_part = f"{loop_device}1"
                    root_part = f"{loop_device}2"
                    
                    # If still not found, try kpartx
                    if not Path(boot_part).exists() or not Path(root_part).exists():
                        self.logger.info("Using kpartx to map partitions")
                        subprocess.run(['kpartx', '-av', loop_device], check=True)
                        loop_name = os.path.basename(loop_device)
                        boot_part = f"/dev/mapper/{loop_name}p1"
                        root_part = f"/dev/mapper/{loop_name}p2"
                
                # Mount and copy boot partition
                self.logger.info(f"Copying boot partition from {boot_part} to {boot_dir}")
                temp_mount = Path("/tmp/w4b_temp_mount")
                temp_mount.mkdir(exist_ok=True)
                
                try:
                    subprocess.run(['mount', boot_part, str(temp_mount)], check=True)
                    subprocess.run(['cp', '-a', f"{temp_mount}/.", str(boot_dir)], check=True)
                finally:
                    subprocess.run(['umount', str(temp_mount)], check=False)
                
                # Mount and copy root partition
                self.logger.info(f"Copying root partition from {root_part} to {rootfs_dir}")
                try:
                    subprocess.run(['mount', root_part, str(temp_mount)], check=True)
                    subprocess.run(['cp', '-a', f"{temp_mount}/.", str(rootfs_dir)], check=True)
                finally:
                    subprocess.run(['umount', str(temp_mount)], check=False)
                    
                # Clean up
                if temp_mount.exists():
                    temp_mount.rmdir()
                    
            finally:
                # Detach loop device
                subprocess.run(['losetup', '-d', loop_device], check=False)
            
            self.logger.info(f"Successfully unpacked image to: {unpacked_path}")
            return unpacked_path
            
        except Exception as e:
            self.logger.error(f"Failed to unpack image: {str(e)}")
            return None
