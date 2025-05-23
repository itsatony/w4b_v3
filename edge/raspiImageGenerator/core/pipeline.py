#!/usr/bin/env python3
"""
Build pipeline for the W4B Raspberry Pi Image Generator.

This module implements the multi-stage build pipeline for generating
customized Raspberry Pi OS images, handling the flow between stages
and overall state management.
"""

import asyncio
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Tuple

from core.image import ImageBuilder
from core.stages.base import BuildStage
from core.stages.download import DownloadStage
from core.stages.system_config import SystemConfigStage
from core.stages.software_install import SoftwareInstallStage
from core.stages.security import SecurityConfigStage
from core.stages.services import ServiceConfigStage
from core.stages.w4b_software import W4BSoftwareStage
from core.stages.validation import ValidationStage
from core.stages.compression import CompressionStage
from core.stages.publication import PublicationStage  # Add import for new stage


class BuildPipeline:
    """
    Orchestrates the multi-stage build process for a Raspberry Pi image.
    
    This class manages the execution of build stages, state passing between
    stages, error handling, and overall build status tracking.
    
    Attributes:
        config (Dict[str, Any]): Configuration dictionary
        work_dir (Path): Working directory
        build_id (str): Unique build identifier
        timestamp (str): Timestamp for the build
        logger (logging.Logger): Logger instance
        image_builder (ImageBuilder): Image builder instance
        stages (List[BuildStage]): List of build stages
        state (Dict[str, Any]): Shared state between stages
        current_stage (int): Index of current stage
        start_time (float): Build start time
        end_time (Optional[float]): Build end time
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        work_dir: Path,
        build_id: str,
        timestamp: str
    ):
        """
        Initialize the build pipeline.
        
        Args:
            config: Configuration dictionary
            work_dir: Working directory
            build_id: Unique build identifier
            timestamp: Timestamp for the build
        """
        self.config = config
        self.work_dir = work_dir
        self.build_id = build_id
        self.timestamp = timestamp
        self.logger = logging.getLogger("pipeline")
        
        self.image_builder = ImageBuilder(config, work_dir)
        self.stages = []
        self.state = {
            "config": config,
            "work_dir": work_dir,
            "build_id": build_id,
            "timestamp": timestamp,
            "image_builder": self.image_builder
        }
        
        self.current_stage = -1
        self.start_time = 0
        self.end_time = None
        
        # Initialize pipeline stages
        self._setup_stages()
    
    def _setup_stages(self) -> None:
        """Set up the build stages in the pipeline."""
        self.stages = [
            DownloadStage(self.state),
            SystemConfigStage(self.state),
            SoftwareInstallStage(self.state),
            SecurityConfigStage(self.state),
            ServiceConfigStage(self.state),
            W4BSoftwareStage(self.state),
            ValidationStage(self.state),
            CompressionStage(self.state),
            PublicationStage(self.state)  # Add new stage to pipeline
        ]
    
    async def _execute_stage(self, stage_index: int) -> bool:
        """
        Execute a stage by index.
        
        Args:
            stage_index: Index of the stage to execute
            
        Returns:
            bool: True if the stage completed successfully, False otherwise
        """
        if stage_index >= len(self.stages):
            return False
        
        stage = self.stages[stage_index]
        stage_name = stage.__class__.__name__
        
        # Log stage start only once here
        self.logger.info(f"Starting stage {stage_index+1}/{len(self.stages)}: {stage_name}")
        
        start_time = time.time()
        try:
            result = await stage.execute()
            elapsed = time.time() - start_time
            
            if result:
                self.logger.info(f"Stage {stage_name} completed in {elapsed:.1f}s")
                self.logger.info(f"Stage {stage_name} completed successfully")
            else:
                self.logger.error(f"Stage {stage_name} failed")
            
            return result
        except Exception as e:
            self.logger.error(f"Error executing stage {stage_name}: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return False
    
    async def run(self) -> bool:
        """
        Execute the build pipeline.
        
        Returns:
            bool: True if successful, False otherwise
        """
        self.start_time = time.time()
        self.logger.info(f"Starting build pipeline for hive {self.config['hive_id']}")
        
        try:
            # Run each stage in sequence
            for i in range(len(self.stages)):
                self.current_stage = i
                success = await self._execute_stage(i)
                
                if not success:
                    self.logger.error("Pipeline aborted due to stage failure")
                    return False
            
            self.end_time = time.time()
            total_duration = self.end_time - self.start_time
            
            self.logger.info(
                f"Build pipeline completed successfully in {total_duration:.1f}s"
            )
            
            # Log output file information
            if "output_file" in self.state:
                output_file = self.state["output_file"]
                checksums = self.state.get("checksums", {})
                
                self.logger.info(f"Output image: {output_file}")
                
                for algo, checksum in checksums.items():
                    self.logger.info(f"{algo.upper()} checksum: {checksum}")
            
            return True
            
        except Exception as e:
            self.logger.exception(f"Pipeline failed: {str(e)}")
            return False
            
        finally:
            # Ensure image is unmounted
            try:
                await self.image_builder.unmount_image()
            except Exception as e:
                self.logger.error(f"Error during cleanup: {str(e)}")
            # Clean up mounted filesystems and loop devices at the end
            await self._cleanup_resources()
    
    async def _cleanup_resources(self) -> None:
        """Clean up resources used by the pipeline."""
        try:
            # Unmount filesystems if they're still mounted
            await self._unmount_filesystems()
            
            # Detach loop devices
            await self._detach_loop_devices()
            
        except Exception as e:
            self.logger.error(f"Error during resource cleanup: {str(e)}")
    
    async def _unmount_filesystems(self) -> None:
        """Unmount filesystems if they're still mounted."""
        try:
            boot_mount = self.state.get("boot_mount")
            root_mount = self.state.get("root_mount")
            
            if boot_mount and Path(boot_mount).exists():
                self.logger.info(f"Unmounting boot partition: {boot_mount}")
                process = await asyncio.create_subprocess_exec(
                    "umount", "-f", str(boot_mount),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                if process.returncode != 0 and stderr:
                    self.logger.warning(f"Failed to unmount boot partition: {stderr.decode()}")
            
            if root_mount and Path(root_mount).exists():
                self.logger.info(f"Unmounting root partition: {root_mount}")
                process = await asyncio.create_subprocess_exec(
                    "umount", "-f", str(root_mount),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                if process.returncode != 0 and stderr:
                    self.logger.warning(f"Failed to unmount root partition: {stderr.decode()}")
                    
        except Exception as e:
            self.logger.error(f"Error unmounting filesystems: {str(e)}")
    
    async def _detach_loop_devices(self) -> None:
        """Detach loop devices if they're still attached."""
        try:
            loop_device = self.state.get("loop_device")
            
            if loop_device:
                self.logger.info(f"Detaching loop device: {loop_device}")
                process = await asyncio.create_subprocess_exec(
                    "losetup", "-d", loop_device,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                if process.returncode != 0 and stderr:
                    self.logger.warning(f"Failed to detach loop device: {stderr.decode()}")
                    
        except Exception as e:
            self.logger.error(f"Error detaching loop devices: {str(e)}")
