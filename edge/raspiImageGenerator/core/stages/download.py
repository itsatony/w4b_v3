#!/usr/bin/env python3
"""
Download stage for Raspberry Pi image generator.
"""

import os
import sys
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

from core.stages.base import BuildStage
from core.cache_manager import CacheManager

class DownloadStage(BuildStage):
    """
    Build stage for downloading and caching the Raspberry Pi OS image.
    """
    
    async def execute(self) -> bool:
        try:
            self.logger.info("Starting stage: DownloadStage")
            
            # Initialize cache manager with a persistent location
            cache_dir = Path(self.state["config"].get("cache_dir", "/tmp/w4b_image_cache"))
            self.cache_manager = CacheManager(cache_dir)
            
            # Clean cache before starting
            self.cache_manager.clean_cache()
            
            # Get image information
            image_info = self._get_image_info()
            
            # Check if image is already cached
            download_cached, unpacked_cached = self.cache_manager.is_cached(image_info)
            
            if download_cached:
                self.logger.info("Using cached downloaded image")
                download_path = self.cache_manager.get_download_path(image_info)
                self.state["image_path"] = download_path
            else:
                # Download the image if not cached
                self.logger.info("Downloading image")
                download_path = self.cache_manager.get_download_path(image_info)
                download_path.parent.mkdir(parents=True, exist_ok=True)
                
                if not await self._download_image(image_info["url"], download_path):
                    return False
                    
                self.state["image_path"] = download_path
                
                # Save metadata
                self.cache_manager.save_metadata(image_info)
            
            # Extract image if needed
            if self.state["config"]["base_image"].get("compressed", True):
                self.logger.info("Extracting compressed image")
                extracted_path = await self._extract_image(self.state["image_path"])
                if not extracted_path:
                    return False
                
                self.state["image_path"] = extracted_path
            
            # If we need to prepare the image for mounting, do it here
            if unpacked_cached:
                self.logger.info("Using cached unpacked image")
                unpacked_path = self.cache_manager.get_unpacked_path(image_info)
                self.state["cached_unpacked_path"] = unpacked_path
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error in download stage: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return False
    
    def _get_image_info(self) -> Dict[str, Any]:
        """
        Get information about the image for caching purposes.
        
        Returns:
            Dict[str, Any]: Image information
        """
        config = self.state["config"]["base_image"]
        
        return {
            "version": config.get("version", "unknown"),
            "model": config.get("model", "generic"),
            "checksum": config.get("checksum", ""),
            "checksum_type": config.get("checksum_type", "sha256"),
            "url": self._get_image_url(),
            "compressed": config.get("compressed", True)
        }
    
    async def _download_image(self, url: str, path: Path) -> bool:
        """
        Download the image from the given URL to the specified path.
        
        Args:
            url (str): URL of the image to download.
            path (Path): Path to save the downloaded image.
        
        Returns:
            bool: True if download succeeds, False otherwise.
        """
        try:
            self.logger.info(f"Downloading image from {url} to {path}")
            # Simulate download logic here
            await asyncio.sleep(1)  # Simulate async download
            path.touch()  # Simulate file creation
            return True
        except Exception as e:
            self.logger.error(f"Failed to download image: {str(e)}")
            return False
    
    async def _extract_image(self, path: Path) -> Optional[Path]:
        """
        Extract the compressed image.
        
        Args:
            path (Path): Path to the compressed image.
        
        Returns:
            Optional[Path]: Path to the extracted image, or None if extraction fails.
        """
        try:
            self.logger.info(f"Extracting image at {path}")
            # Simulate extraction logic here
            extracted_path = path.with_suffix("")  # Simulate extraction
            extracted_path.touch()  # Simulate file creation
            return extracted_path
        except Exception as e:
            self.logger.error(f"Failed to extract image: {str(e)}")
            return None
    
    def _get_image_url(self) -> str:
        """
        Construct the image URL based on the configuration.
        
        Returns:
            str: Image URL.
        """
        base_image_config = self.state["config"]["base_image"]
        version = base_image_config["version"]
        url_template = base_image_config["url_template"]
        
        if "{version}" in url_template:
            return url_template.format(version=version)
        else:
            return f"{url_template}/{version}"
