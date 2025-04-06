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
from core.stages.software import SoftwareInstallStage
from core.stages.security import SecurityConfigStage
from core.stages.services import ServiceConfigStage
from core.stages.w4b import W4BSoftwareStage
from core.stages.validation import ValidationStage
from core.stages.compression import CompressionStage


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
            CompressionStage(self.state)
        ]
    
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
            for i, stage in enumerate(self.stages):
                self.current_stage = i
                stage_name = stage.__class__.__name__
                
                self.logger.info(f"Starting stage {i+1}/{len(self.stages)}: {stage_name}")
                
                stage_start_time = time.time()
                success = await stage.run()
                stage_duration = time.time() - stage_start_time
                
                if success:
                    self.logger.info(
                        f"Stage {stage_name} completed in {stage_duration:.1f}s"
                    )
                else:
                    self.logger.error(f"Stage {stage_name} failed, aborting pipeline")
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
