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

class DownloadStage(BuildStage):
    """
    Build stage for downloading the base Raspberry Pi OS image.
    """
    
    async def execute(self) -> bool:
        try:
            self.logger.info("Starting stage: DownloadStage")
            self.logger.info("Downloading base Raspberry Pi OS image")
            
            base_image_config = self.state["config"]["base_image"]
            version = base_image_config["version"]
            url_template = base_image_config["url_template"]
            
            # Construct the URL
            url = url_template
            if "{version}" in url_template:
                url = url_template.format(version=version)
                
            self.logger.info(f"Image URL: {url}")
            
            # Make sure we're working with the correct builder
            builder = self.state["image_builder"]
            
            # Generate cache path
            cache_path = builder.generate_cache_path(version)
            
            # Ensure the cache directory exists
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            self.logger.info(f"Cache path: {cache_path}")
            
            # Check if image already exists in cache
            if cache_path.exists():
                self.logger.info(f"Image already exists in cache: {cache_path}")
                # Store the image path in the state dictionary under both keys for compatibility
                self.state["base_image_path"] = cache_path
                self.state["image_path"] = cache_path
                return True
            
            # Download the image
            try:
                downloaded_path = await builder.download_image(url, cache_path)
                # Store the image path in the state dictionary under both keys for compatibility
                self.state["base_image_path"] = downloaded_path
                self.state["image_path"] = downloaded_path
                self.logger.info(f"Downloaded image to: {downloaded_path}")
                return True
            except Exception as e:
                self.logger.error(f"Network error during download: {str(e)}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error in download stage: {str(e)}")
            return False
