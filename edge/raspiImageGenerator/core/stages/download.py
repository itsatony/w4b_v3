#!/usr/bin/env python3
"""
Download stage for the W4B Raspberry Pi Image Generator.

This module implements the first stage of the build pipeline, responsible
for downloading and preparing the base Raspberry Pi OS image.
"""

import asyncio
import os
from pathlib import Path
from typing import Dict, Any, Optional

from core.stages.base import BuildStage
from utils.error_handling import NetworkError, ImageBuildError


class DownloadStage(BuildStage):
    """
    Build stage for downloading the base Raspberry Pi OS image.
    
    This stage is responsible for downloading the base image, verifying its
    checksum, and extracting it for further processing.
    
    Attributes:
        name (str): Name of the stage
        state (Dict[str, Any]): Shared pipeline state
        logger (logging.Logger): Logger instance
        circuit_breaker (CircuitBreaker): Circuit breaker for fault tolerance
    """
    
    async def execute(self) -> bool:
        """
        Execute the download stage.
        
        Returns:
            bool: True if download succeeded, False otherwise
        """
        try:
            # Get image builder from state
            image_builder = self.state["image_builder"]
            
            # Get configuration for this stage
            config = self.get_config()
            
            # Download the base image
            self.logger.info("Downloading base Raspberry Pi OS image")
            compressed_image_path = await image_builder.download_image()
            
            # Extract the image
            self.logger.info("Extracting image")
            image_path = await image_builder.extract_image(compressed_image_path)
            
            # Update state with image path
            self.state["image_path"] = image_path
            self.logger.info(f"Base image ready at: {image_path}")
            
            return True
            
        except NetworkError as e:
            self.logger.error(f"Network error during download: {str(e)}")
            return False
            
        except ImageBuildError as e:
            self.logger.error(f"Image build error: {str(e)}")
            return False
            
        except Exception as e:
            self.logger.exception(f"Unexpected error in download stage: {str(e)}")
            return False
