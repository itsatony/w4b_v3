#!/usr/bin/env python3
"""
Base build stage for the W4B Raspberry Pi Image Generator.

This module defines the abstract base class for all build stages in the
image generation pipeline, providing common utilities and interfaces.
"""

import abc
import asyncio
import logging
from typing import Dict, Any, Optional, List

from utils.error_handling import ImageBuildError, CircuitBreaker


class BuildStage(abc.ABC):
    """
    Abstract base class for build pipeline stages.
    
    This class defines the interface and common functionality for all
    build stages in the image generation pipeline.
    
    Attributes:
        name (str): Name of the stage
        state (Dict[str, Any]): Shared pipeline state
        logger (logging.Logger): Logger instance
        circuit_breaker (CircuitBreaker): Circuit breaker for fault tolerance
    """
    
    def __init__(self, state: Dict[str, Any]):
        """
        Initialize the build stage.
        
        Args:
            state: Shared pipeline state
        """
        self.name = self.__class__.__name__
        self.state = state
        self.logger = logging.getLogger(f"stage.{self.name.lower()}")
        
        # Create circuit breaker for this stage
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60.0,
            name=self.name,
            logger=self.logger
        )
        
        # Initialize stage-specific state
        self.stage_state = {}
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get configuration for this stage.
        
        Returns:
            Dict[str, Any]: Stage configuration
        """
        # Get global configuration
        config = self.state["config"]
        
        # Get stage-specific configuration if available
        stage_key = self.name.lower().replace("stage", "")
        if stage_key in config:
            return config[stage_key]
        
        return {}
    
    async def pre_run(self) -> bool:
        """
        Perform pre-run checks and preparations.
        
        Returns:
            bool: True if pre-run succeeded, False otherwise
        """
        try:
            self.logger.info(f"Starting stage: {self.name}")
            self.stage_state["start_time"] = asyncio.get_event_loop().time()
            return True
        except Exception as e:
            self.logger.error(f"Pre-run failed: {str(e)}")
            return False
    
    @abc.abstractmethod
    async def execute(self) -> bool:
        """
        Execute the main stage logic.
        
        This method must be implemented by all concrete stage classes.
        
        Returns:
            bool: True if execution succeeded, False otherwise
        """
        # Implement in derived classes
        return True
    
    async def post_run(self, success: bool) -> None:
        """
        Perform post-run cleanup and reporting.
        
        Args:
            success: Whether the stage execution was successful
        """
        try:
            # Calculate stage duration
            if "start_time" in self.stage_state:
                duration = asyncio.get_event_loop().time() - self.stage_state["start_time"]
                self.logger.info(f"Stage completed in {duration:.2f}s")
            
            # Update state with stage results
            if success:
                self.state["completed_stages"] = self.state.get("completed_stages", []) + [self.name]
                self.logger.info(f"Stage {self.name} completed successfully")
            else:
                self.logger.error(f"Stage {self.name} failed")
                
        except Exception as e:
            self.logger.error(f"Post-run error: {str(e)}")
    
    async def run(self) -> bool:
        """
        Run the full stage lifecycle.
        
        This method orchestrates the pre-run, execute, and post-run phases
        and handles errors.
        
        Returns:
            bool: True if the stage succeeded, False otherwise
        """
        success = False
        
        try:
            # Pre-run checks
            if not await self.pre_run():
                self.logger.error(f"Stage {self.name} pre-run checks failed")
                return False
            
            # Execute within circuit breaker
            success = await self.circuit_breaker.execute(self.execute)
            
        except Exception as e:
            self.logger.exception(f"Stage {self.name} failed with error: {str(e)}")
            success = False
            
        finally:
            # Post-run cleanup
            await self.post_run(success)
            
        return success
