#!/usr/bin/env python3
"""
Validation stage for the W4B Raspberry Pi Image Generator.

This module implements the validation stage of the build pipeline,
responsible for validating the generated image meets all requirements.
"""

import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List

from core.stages.base import BuildStage
from core.validation import ImageValidator
from utils.error_handling import ValidationError


class ValidationStage(BuildStage):
    """
    Build stage for validating the generated image.
    
    This stage is responsible for checking that the generated image meets
    all requirements and is properly configured.
    
    Attributes:
        name (str): Name of the stage
        state (Dict[str, Any]): Shared pipeline state
        logger (logging.Logger): Logger instance
        circuit_breaker (CircuitBreaker): Circuit breaker for fault tolerance
    """
    
    async def execute(self) -> bool:
        """
        Execute the validation stage.
        
        Returns:
            bool: True if validation succeeded, False otherwise
        """
        try:
            # Get necessary paths
            image_path = self.state["image_path"]
            boot_mount = self.state["boot_mount"]
            root_mount = self.state["root_mount"]
            
            # Get validation configuration
            config = self.get_config()
            validation_types = config.get("types", ["structure", "files", "services"])
            
            # Skip validation if requested
            if self.state["config"].get("skip_validation", False):
                self.logger.info("Validation stage skipped as requested")
                self.state["validation_results"] = {
                    "skipped": True,
                    "reason": "Validation skipped as requested"
                }
                return True
            
            # Create validator
            validator = ImageValidator()
            
            # Run validation
            self.logger.info(f"Validating image with types: {validation_types}")
            success, results = await validator.validate_image(
                image_path, boot_mount, root_mount, validation_types
            )
            
            # Store results in state
            self.state["validation_results"] = results
            
            if success:
                self.logger.info("Image validation succeeded")
                return True
            else:
                self.logger.error("Image validation failed")
                for validation_type, validation_result in results["validations"].items():
                    if not validation_result.get("success", False):
                        self.logger.error(f"{validation_type} validation failed:")
                        if "error" in validation_result:
                            self.logger.error(f"  Error: {validation_result['error']}")
                        if "results" in validation_result:
                            for key, value in validation_result["results"].items():
                                if isinstance(value, list) and key == "missing_files":
                                    for missing in value:
                                        self.logger.error(f"  Missing: {missing}")
                
                return False
                
        except Exception as e:
            self.logger.exception(f"Validation failed: {str(e)}")
            return False
