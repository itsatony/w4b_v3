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
        Get the path where the unpacked image should be stored.
        
        Args:
            image_info: Dictionary containing image information
            
        Returns:
            Path: Path for the unpacked image
        """
        cache_key = self.get_cache_key(image_info)
        return self.unpacked_dir / cache_key
    
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
        
        download_cached = download_path.exists() and self._validate_download(download_path, image_info)
        unpacked_cached = unpacked_path.exists() and self._validate_unpacked(unpacked_path)
        
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
        if not path.exists() or path.stat().st_size == 0:
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
        Validate an unpacked image directory.
        
        Args:
            path: Path to the unpacked directory
            
        Returns:
            bool: True if valid, False otherwise
        """
        # Check for essential directories
        if not path.exists():
            return False
            
        essential_dirs = ["boot", "rootfs"]
        for dir_name in essential_dirs:
            if not (path / dir_name).exists() or not (path / dir_name).is_dir():
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
