#!/usr/bin/env python3
"""
Command-line runner for the W4B Raspberry Pi Image Generator.

This script provides a simple CLI interface to run the image generator
with basic parameters and configuration.
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from image_generator import ImageGenerator
from utils.logging_setup import configure_logging


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="W4B Raspberry Pi Image Generator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Basic configuration
    parser.add_argument("--hive-id", required=True, help="ID of the hive to generate an image for")
    parser.add_argument("--config-file", default="sample_config.yaml", help="Path to YAML configuration file")
    parser.add_argument("--output-dir", default="/tmp", help="Directory to store generated images")
    
    # Optional settings
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    # Optional configuration overrides
    parser.add_argument("--pi-model", choices=["3", "4", "5"], help="Raspberry Pi model")
    parser.add_argument("--timezone", help="Default timezone")
    parser.add_argument("--vpn-server", help="WireGuard VPN server endpoint")
    
    args = parser.parse_args()
    return args


async def main() -> int:
    """
    Main entry point for the image generator CLI.
    
    Returns:
        int: Exit code (0 for success, non-zero for error)
    """
    # Parse arguments
    args = parse_arguments()
    
    # Configure logging
    log_level = logging.DEBUG if args.debug else logging.INFO if args.verbose else logging.WARNING
    configure_logging(log_level)
    
    logger = logging.getLogger("cli")
    logger.info(f"Starting W4B Raspberry Pi Image Generator for hive {args.hive_id}")
    
    # Run the image generator
    try:
        # Set environment variables based on arguments
        if args.hive_id:
            os.environ["W4B_HIVE_ID"] = args.hive_id
        if args.output_dir:
            os.environ["W4B_IMAGE_OUTPUT_DIR"] = args.output_dir
        if args.pi_model:
            os.environ["W4B_PI_MODEL"] = args.pi_model
        if args.timezone:
            os.environ["W4B_TIMEZONE"] = args.timezone
        if args.vpn_server:
            os.environ["W4B_VPN_SERVER"] = args.vpn_server
        
        # Create command-line args for image generator
        gen_args = argparse.Namespace(
            hive_id=args.hive_id,
            config_file=args.config_file,
            output_dir=args.output_dir,
            verbose=args.verbose,
            debug=args.debug,
            pi_model=args.pi_model,
            timezone=args.timezone,
            vpn_server=args.vpn_server,
            validate_only=False,
            skip_validation=False
        )
        
        # Create and run the image generator
        generator = ImageGenerator()
        generator.parsed_args = gen_args
        generator.setup_environment()
        await generator.load_configuration()
        success = await generator.run_pipeline()
        await generator.cleanup()
        
        if success:
            logger.info(f"Image generation for hive {args.hive_id} completed successfully")
            return 0
        else:
            logger.error(f"Image generation for hive {args.hive_id} failed")
            return 1
            
    except KeyboardInterrupt:
        logger.info("Image generation interrupted")
        return 130
    except Exception as e:
        logger.exception(f"Unhandled error: {str(e)}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
