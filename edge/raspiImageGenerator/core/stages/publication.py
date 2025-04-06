#!/usr/bin/env python3
"""
Publication stage for the W4B Raspberry Pi Image Generator.

This module implements the publication stage of the build pipeline,
responsible for moving the compressed image to a web-accessible location
and generating download links.
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from core.stages.base import BuildStage


class PublicationStage(BuildStage):
    """
    Build stage for publishing the generated image.
    
    This stage moves the compressed image to a web-accessible location,
    renames it with appropriate timestamp and version information, and
    generates a download link.
    
    Attributes:
        name (str): Name of the stage
        state (Dict[str, Any]): Shared pipeline state
        logger (logging.Logger): Logger instance
    """
    
    async def execute(self) -> bool:
        """
        Execute the publication stage.
        
        Returns:
            bool: True if publication succeeded, False otherwise
        """
        try:
            # Check if output file exists in state
            if "output_file" not in self.state:
                self.logger.error("No output file found in state")
                return False
                
            # Get the compressed image path
            compressed_image_path = Path(self.state["output_file"])
            if not compressed_image_path.exists():
                self.logger.error(f"Compressed image file not found: {compressed_image_path}")
                return False
                
            # Get hive ID and version
            hive_id = self.state["config"]["hive_id"]
            version = self.state["config"].get("version", "1.0.0")
            
            # Get current timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
            
            # Format new filename
            new_filename = f"{timestamp}_{hive_id}_{version}_image.xz"
            
            # Get server base path from environment or config
            server_base_path = os.environ.get(
                "W4B_IMAGE_SERVER_BASEPATH", 
                self.state["config"].get("server_base_path", "/home/itsatony/srv/")
            )
            
            # Ensure server path exists and ends with a slash
            server_base_path = Path(server_base_path)
            if not server_base_path.exists():
                self.logger.info(f"Creating server base path: {server_base_path}")
                server_base_path.mkdir(parents=True, exist_ok=True)
                
            # Define target path
            target_path = server_base_path / new_filename
            
            # Get download URL base from environment or config
            download_url_base = os.environ.get(
                "W4B_IMAGE_DOWNLOAD_URL_BASE",
                self.state["config"].get("download_url_base", "https://queenb.vaudience.io:14800/files/")
            )
            
            # Ensure URL ends with a slash
            if not download_url_base.endswith('/'):
                download_url_base += '/'
                
            # Define download URL
            download_url = f"{download_url_base}{new_filename}"
            
            # Move the file to the server path
            self.logger.info(f"Moving image to server path: {target_path}")
            shutil.copy2(compressed_image_path, target_path)
            
            # Verify the file was copied successfully
            if not target_path.exists():
                self.logger.error(f"Failed to copy image to server path: {target_path}")
                return False
                
            # Update state with publication info
            self.state["published_image_path"] = str(target_path)
            self.state["download_url"] = download_url
            
            # Generate download link info in multiple formats for different use cases
            self.logger.info("=================================================")
            self.logger.info("Image successfully published!")
            self.logger.info(f"Download URL: {download_url}")
            self.logger.info("For convenient download use:")
            self.logger.info(f"wget {download_url}")
            self.logger.info("=================================================")
            
            return True
            
        except Exception as e:
            self.logger.exception(f"Publication failed: {str(e)}")
            return False
