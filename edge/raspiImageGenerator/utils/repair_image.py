#!/usr/bin/env python3
"""
Image repair utility for Raspberry Pi images.

This script can check, validate, and potentially repair corrupt Raspberry Pi OS images.
"""

import argparse
import os
import sys
import subprocess
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("image-repair")

def validate_image(image_path: str) -> bool:
    """
    Validate a Raspberry Pi image file.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        bool: True if valid, False otherwise
    """
    logger.info(f"Validating image: {image_path}")
    
    # Check if file exists
    img_path = Path(image_path)
    if not img_path.exists():
        logger.error(f"Image file does not exist: {image_path}")
        return False
    
    # Check file size
    file_size = img_path.stat().st_size
    if file_size < 1024 * 1024:  # At least 1MB
        logger.error(f"Image file too small ({file_size} bytes): {image_path}")
        return False
    
    logger.info(f"Image size: {file_size / (1024*1024):.2f} MB")
    
    # Check file type
    try:
        result = subprocess.run(["file", image_path], capture_output=True, text=True, check=True)
        logger.info(f"File type: {result.stdout.strip()}")
        
        if "boot sector" not in result.stdout.lower() and "dos/mbr boot sector" not in result.stdout.lower():
            logger.warning("File may not be a valid disk image")
            return False
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to check file type: {e}")
        return False
    
    # Try to examine partitions with fdisk
    try:
        result = subprocess.run(["fdisk", "-l", image_path], capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout:
            logger.info("Partition table found:")
            for line in result.stdout.split('\n'):
                if image_path in line or 'Device' in line or 'Boot' in line:
                    logger.info(f"  {line}")
            return True
        else:
            logger.warning(f"Failed to read partition table: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error examining partitions: {e}")
        return False

def extract_if_compressed(image_path: str) -> str:
    """
    Extract the image if it's compressed.
    
    Args:
        image_path: Path to the possibly compressed image
        
    Returns:
        str: Path to the extracted image, or original path if not compressed
    """
    img_path = Path(image_path)
    
    # Check if compressed
    if img_path.suffix.lower() in ['.xz', '.gz', '.bz2']:
        logger.info(f"Compressed image detected: {image_path}")
        
        # Determine extraction command
        if img_path.suffix.lower() == '.xz':
            cmd = ["xz", "-d", "-k", "-f", image_path]
        elif img_path.suffix.lower() == '.gz':
            cmd = ["gunzip", "-k", "-f", image_path]
        elif img_path.suffix.lower() == '.bz2':
            cmd = ["bunzip2", "-k", "-f", image_path]
        
        # Extract
        try:
            logger.info(f"Extracting: {' '.join(cmd)}")
            subprocess.run(cmd, check=True, capture_output=True)
            extracted_path = str(img_path.with_suffix(''))
            logger.info(f"Extracted to: {extracted_path}")
            return extracted_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Extraction failed: {e}")
            logger.error(f"Stderr: {e.stderr.decode() if e.stderr else 'Unknown error'}")
            return image_path
    
    return image_path

def repair_image(image_path: str) -> bool:
    """
    Attempt to repair a disk image.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        bool: True if repair successful, False otherwise
    """
    logger.info(f"Attempting to repair image: {image_path}")
    
    # Create a backup first
    backup_path = f"{image_path}.backup"
    try:
        logger.info(f"Creating backup: {backup_path}")
        subprocess.run(["cp", image_path, backup_path], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to create backup: {e}")
        return False
    
    # Try to repair with testdisk
    try:
        logger.info("Checking for testdisk...")
        subprocess.run(["which", "testdisk"], check=True, capture_output=True)
        
        logger.info("Running testdisk for analysis (this is interactive)...")
        logger.info("Follow the prompts to analyze and fix partition issues.")
        subprocess.run(["testdisk", image_path])
        
        # Validate after repair
        if validate_image(image_path):
            logger.info("Image successfully repaired and validated")
            return True
        else:
            logger.warning("Image still invalid after repair attempt")
            return False
    except subprocess.CalledProcessError:
        logger.error("testdisk not found. Please install it with: sudo apt-get install testdisk")
        return False
    except Exception as e:
        logger.error(f"Error during repair: {e}")
        return False

def create_fresh_loop(image_path: str) -> str:
    """
    Create a fresh loop device for an image.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        str: Path to the loop device, or empty string on failure
    """
    try:
        # Detach any existing loops for this image
        logger.info("Checking for existing loop devices...")
        result = subprocess.run(
            ["losetup", "-j", image_path], 
            capture_output=True, 
            text=True
        )
        
        for line in result.stdout.splitlines():
            if line and image_path in line:
                dev = line.split(':')[0]
                logger.info(f"Detaching existing loop device: {dev}")
                subprocess.run(["losetup", "-d", dev], check=False)
        
        # Create new loop device with partition scanning
        logger.info("Creating new loop device with partition scanning...")
        result = subprocess.run(
            ["losetup", "--partscan", "--find", "--show", image_path],
            capture_output=True,
            text=True,
            check=True
        )
        
        loop_dev = result.stdout.strip()
        if not loop_dev:
            logger.error("Failed to create loop device (empty result)")
            return ""
        
        logger.info(f"Created loop device: {loop_dev}")
        
        # Force kernel to scan partition table
        logger.info("Scanning partition table...")
        subprocess.run(["partprobe", "-s", loop_dev], check=False)
        
        # List loop status
        subprocess.run(["losetup", "-l"], check=True)
        
        # Check for partitions
        found_parts = []
        for suffix in ["p1", "p2", "1", "2"]:
            part_path = f"{loop_dev}{suffix}"
            if os.path.exists(part_path):
                found_parts.append(part_path)
        
        if found_parts:
            logger.info(f"Found partitions: {', '.join(found_parts)}")
        else:
            logger.warning("No partitions found")
        
        return loop_dev
    except subprocess.CalledProcessError as e:
        logger.error(f"Error creating loop device: {e}")
        logger.error(f"Stderr: {e.stderr}")
        return ""
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return ""

def main():
    parser = argparse.ArgumentParser(description="Raspberry Pi Image Repair Utility")
    parser.add_argument("image_path", help="Path to the Raspberry Pi image file")
    parser.add_argument("--validate", action="store_true", help="Validate the image only, don't repair")
    parser.add_argument("--extract", action="store_true", help="Extract if compressed")
    parser.add_argument("--repair", action="store_true", help="Attempt to repair the image")
    parser.add_argument("--loop", action="store_true", help="Create and test loop device")
    
    args = parser.parse_args()
    
    # Process image based on arguments
    image_path = args.image_path
    
    if args.extract or any([image_path.endswith(ext) for ext in ['.xz', '.gz', '.bz2']]):
        image_path = extract_if_compressed(image_path)
    
    if args.validate or args.repair or args.loop:
        if validate_image(image_path):
            logger.info("Image validation passed")
        else:
            logger.warning("Image validation failed")
            if args.repair:
                if repair_image(image_path):
                    logger.info("Image repair successful")
                else:
                    logger.error("Image repair failed")
    
    if args.loop:
        loop_dev = create_fresh_loop(image_path)
        if loop_dev:
            logger.info(f"Loop device created: {loop_dev}")
            logger.info(f"Detaching loop device {loop_dev}")
            subprocess.run(["losetup", "-d", loop_dev], check=False)
        else:
            logger.error("Failed to create loop device")

if __name__ == "__main__":
    main()
