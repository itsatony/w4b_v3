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
import time
import shutil  # Add missing import for shutil
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
    
    async def cleanup(self):
        """Clean up temporary resources."""
        self.logger.info(f"Cleaning up working directory: {self.work_dir}")
        
        # Ensure image is unmounted with maximum force
        await self._force_cleanup_mounts()
        
        # Try to remove directory, handling busy errors
        retries = 3
        while retries > 0:
            try:
                # First try removing directory contents one by one
                for item in os.listdir(self.work_dir):
                    item_path = os.path.join(self.work_dir, item)
                    if os.path.ismount(item_path):
                        # Try umount again if still mounted
                        await self._force_unmount(Path(item_path))
                        continue
                    
                    try:
                        if os.path.isdir(item_path):
                            shutil.rmtree(item_path, ignore_errors=True)
                        else:
                            os.unlink(item_path)
                    except Exception as e:
                        self.logger.warning(f"Unable to remove {item_path}: {str(e)}")
                
                # Then try to remove the directory itself
                shutil.rmtree(self.work_dir, ignore_errors=True)
                break
            except Exception as e:
                self.logger.warning(f"Error removing working directory: {str(e)}")
                retries -= 1
                if retries > 0:
                    self.logger.info("Retrying directory cleanup...")
                    time.sleep(2)  # Wait before retry
                else:
                    self.logger.warning(f"Unable to completely remove {self.work_dir}. Manual cleanup may be needed.")

    async def _force_cleanup_mounts(self):
        """Aggressively clean up all mounts related to the working directory."""
        try:
            # Find all mounts related to our working directory
            result = await asyncio.create_subprocess_exec(
                'mount',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            
            # Parse mount output to find our mounts
            our_mounts = []
            for line in stdout.decode().splitlines():
                if str(self.work_dir) in line:
                    parts = line.split(' ')
                    if len(parts) >= 3:  # Basic format check
                        mount_point = parts[2]
                        our_mounts.append(mount_point)
            
            # Unmount in reverse order (deepest mounts first)
            our_mounts.sort(key=len, reverse=True)
            
            for mount in our_mounts:
                self.logger.info(f"Forcing unmount of: {mount}")
                # Try umount with increasing force
                await self._force_unmount(Path(mount))
            
            # Ensure boot and rootfs are unmounted
            boot_mount = self.work_dir / "boot"
            root_mount = self.work_dir / "rootfs"
            
            if boot_mount.exists():
                await self._force_unmount(boot_mount)
            
            if root_mount.exists():
                await self._force_unmount(root_mount)
            
            # Detach all loop devices associated with our working directory
            loop_result = await asyncio.create_subprocess_exec(
                'losetup', '-a',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            loop_stdout, _ = await loop_result.communicate()
            
            for line in loop_stdout.decode().splitlines():
                if str(self.work_dir) in line:
                    device = line.split(':', 1)[0]
                    self.logger.info(f"Detaching loop device: {device}")
                    detach_result = await asyncio.create_subprocess_exec(
                        'losetup', '-d', device,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    await detach_result.communicate()
            
            # Wait a moment to ensure file system operations complete
            time.sleep(1)
        
        except Exception as e:
            self.logger.warning(f"Error during mount cleanup: {str(e)}")

    async def _force_unmount(self, mount_point: Path):
        """Force unmount a directory with multiple strategies and detailed error handling."""
        if not mount_point.exists():
            return
        
        try:
            # Check if it's mounted
            result = await asyncio.create_subprocess_exec(
                'mount',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            
            mount_output = stdout.decode()
            if str(mount_point) not in mount_output:
                self.logger.debug(f"Mount point {mount_point} is not currently mounted")
                return  # Not mounted, no need to unmount
            
            self.logger.info(f"Unmounting: {mount_point}")
            
            # Try three strategies in order of increasing aggressiveness:
            
            # 1. Normal unmount
            normal_result = await asyncio.create_subprocess_exec(
                'umount', str(mount_point),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await normal_result.communicate()
            
            # Check if successful
            if normal_result.returncode == 0:
                self.logger.debug(f"Successfully unmounted {mount_point}")
                await asyncio.sleep(0.5)  # Wait for unmount to complete
                return
                
            self.logger.warning(f"Normal unmount failed for {mount_point}: {stderr.decode()}")
            
            # 2. Force unmount
            self.logger.info(f"Trying force unmount for {mount_point}")
            force_result = await asyncio.create_subprocess_exec(
                'umount', '-f', str(mount_point),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await force_result.communicate()
            
            # Check if successful
            check_result = await asyncio.create_subprocess_exec(
                'mount',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            check_stdout, _ = await check_result.communicate()
            
            if str(mount_point) not in check_stdout.decode():
                self.logger.debug(f"Force unmount successful for {mount_point}")
                await asyncio.sleep(0.5)  # Wait for unmount to complete
                return
                
            self.logger.warning(f"Force unmount failed for {mount_point}: {stderr.decode() if stderr else 'Unknown error'}")
            
            # 3. Lazy unmount (last resort)
            self.logger.info(f"Trying lazy unmount for {mount_point}")
            lazy_result = await asyncio.create_subprocess_exec(
                'umount', '-l', str(mount_point),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await lazy_result.communicate()
            
            if lazy_result.returncode != 0:
                self.logger.warning(f"Lazy unmount failed for {mount_point}: {stderr.decode() if stderr else 'Unknown error'}")
            else:
                self.logger.info(f"Lazy unmount initiated for {mount_point}")
            
            # Wait for lazy unmount to take effect
            await asyncio.sleep(1)
            
            # Kill any processes using the mount point
            self.logger.info(f"Checking for processes using {mount_point}")
            fuser_result = await asyncio.create_subprocess_exec(
                'fuser', '-k', str(mount_point),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await fuser_result.communicate()
            
        except Exception as e:
            self.logger.warning(f"Error during unmount operation for {mount_point}: {str(e)}")

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
