#!/usr/bin/env python3
"""
W4B Raspberry Pi Image Generator

A Python-based tool for creating customized Raspberry Pi OS images for
hive monitoring edge devices with all required software, security
settings, and connectivity options pre-configured.
"""

import argparse
import asyncio
import logging
import os
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

import yaml

from core.config import ConfigManager
from core.image import ImageBuilder
from core.pipeline import BuildPipeline
from core.validation import ImageValidator
from utils.logging_setup import configure_logging


class ImageGenerator:
    """
    Main class for the W4B Raspberry Pi Image Generator.
    
    This class serves as the entry point for the image generation process,
    handling command-line arguments, configuration loading, and orchestrating
    the multi-stage build pipeline.
    """
    
    def __init__(self):
        """Initialize the image generator."""
        self.logger = logging.getLogger("image_generator")
        self.config_manager = None
        self.build_id = str(uuid.uuid4())[:8]
        self.timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.work_dir = None
        self.parsed_args = None
    
    def parse_arguments(self) -> argparse.Namespace:
        """
        Parse command-line arguments.
        
        Returns:
            argparse.Namespace: Parsed arguments
        """
        parser = argparse.ArgumentParser(
            description="W4B Raspberry Pi Image Generator",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        
        # Basic configuration options
        parser.add_argument("--hive-id", help="ID of the hive to generate an image for")
        parser.add_argument("--config-file", help="Path to YAML configuration file")
        parser.add_argument("--output-dir", help="Directory to store generated images")
        
        # Image configuration
        parser.add_argument("--raspios-version", help="Version of Raspberry Pi OS to use")
        parser.add_argument("--pi-model", choices=["3", "4", "5"], help="Raspberry Pi model")
        
        # System configuration
        parser.add_argument("--timezone", help="Default timezone")
        parser.add_argument("--hostname-prefix", help="Prefix for hostname")
        
        # Network configuration
        parser.add_argument("--vpn-server", help="WireGuard VPN server endpoint")
        parser.add_argument("--download-server", help="Server URL for downloads")
        
        # Misc options
        parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
        parser.add_argument("--debug", action="store_true", help="Enable debug mode")
        parser.add_argument("--validate-only", action="store_true", 
                            help="Only validate the configuration without generating an image")
        parser.add_argument("--skip-validation", action="store_true",
                            help="Skip validation of the generated image")
        
        self.parsed_args = parser.parse_args()
        return self.parsed_args
    
    def setup_environment(self) -> None:
        """
        Set up the environment for image generation.
        
        This creates working directories and configures logging.
        """
        args = self.parsed_args
        
        # Configure logging
        log_level = logging.DEBUG if args.debug else (
            logging.INFO if args.verbose else logging.WARNING
        )
        configure_logging(log_level)
        
        # Create working directory
        self.work_dir = Path(tempfile.mkdtemp(prefix=f"w4b_image_{self.build_id}_"))
        self.logger.info(f"Created working directory: {self.work_dir}")
        
        # Create output directory if it doesn't exist
        if args.output_dir:
            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Output directory: {output_dir}")
    
    async def load_configuration(self) -> None:
        """
        Load and validate configuration from file or arguments.
        """
        args = self.parsed_args
        
        self.config_manager = ConfigManager(
            config_file=args.config_file,
            hive_id=args.hive_id,
            cli_args=vars(args)
        )
        
        # Load configuration from file/environment/defaults
        await self.config_manager.load()
        
        # Validate the configuration
        if not self.config_manager.validate():
            self.logger.error("Configuration validation failed")
            sys.exit(1)
            
        # If validation only mode, exit successfully after validation
        if args.validate_only:
            self.logger.info("Configuration validated successfully")
            sys.exit(0)
    
    async def run_pipeline(self) -> bool:
        """
        Run the image generation pipeline.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create the pipeline with all build stages
            pipeline = BuildPipeline(
                config=self.config_manager.config,
                work_dir=self.work_dir,
                build_id=self.build_id,
                timestamp=self.timestamp
            )
            
            # Run the pipeline
            success = await pipeline.run()
            
            if success:
                self.logger.info("Image generation completed successfully")
                return True
            else:
                self.logger.error("Image generation failed")
                return False
                
        except Exception as e:
            self.logger.exception(f"Error during image generation: {str(e)}")
            return False
    
    async def cleanup(self) -> None:
        """
        Clean up resources after image generation.
        """
        # In debug mode, keep the working directory
        if not self.parsed_args.debug and self.work_dir and self.work_dir.exists():
            import shutil
            self.logger.info(f"Cleaning up working directory: {self.work_dir}")
            shutil.rmtree(self.work_dir)

    async def run(self) -> int:
        """
        Main method to run the image generator.
        
        Returns:
            int: Exit code (0 for success, non-zero for error)
        """
        try:
            self.parse_arguments()
            self.setup_environment()
            await self.load_configuration()
            
            success = await self.run_pipeline()
            
            if not success:
                return 1
                
            return 0
            
        except Exception as e:
            self.logger.exception(f"Unhandled error: {str(e)}")
            return 1
            
        finally:
            await self.cleanup()


async def main() -> int:
    """
    Entry point for the image generator.
    
    Returns:
        int: Exit code (0 for success, non-zero for error)
    """
    generator = ImageGenerator()
    return await generator.run()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
