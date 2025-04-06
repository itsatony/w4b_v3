#!/usr/bin/env python3
"""
Utility to clean up and reset the image cache.

This script can be used to remove corrupted or partially downloaded files from
the cache directory, and optionally reset the entire cache.
"""

import argparse
import logging
import os
import shutil
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger('cleanup_cache')

def validate_image_file(file_path: Path) -> bool:
    """
    Validate an image file.
    
    Args:
        file_path: Path to the image file
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not file_path.exists():
        return False
        
    # Check file size
    file_size = file_path.stat().st_size
    if file_size == 0:
        logger.warning(f"File is empty: {file_path}")
        return False
        
    # Check if XZ compressed file
    if file_path.suffix.lower() == '.xz':
        try:
            with open(file_path, 'rb') as f:
                header = f.read(6)
                
            if len(header) < 6 or header[0] != 0xFD or header[1:6] != b'7zXZ\x00':
                logger.warning(f"Invalid XZ header: {file_path}")
                return False
        except Exception as e:
            logger.warning(f"Failed to read file header: {str(e)}")
            return False
    
    # Check if it's an extracted image (should have boot sector)
    elif file_path.suffix.lower() == '.img':
        try:
            with open(file_path, 'rb') as f:
                boot_sector = f.read(512)
                
            if len(boot_sector) < 512 or boot_sector[510:512] != b'\x55\xAA':
                logger.warning(f"Invalid boot sector: {file_path}")
                return False
        except Exception as e:
            logger.warning(f"Failed to read boot sector: {str(e)}")
            return False
    
    return True

def clean_cache(cache_dir: Path, reset: bool = False) -> None:
    """
    Clean the cache directory.
    
    Args:
        cache_dir: Path to the cache directory
        reset: Whether to completely reset the cache
    """
    if reset:
        logger.info(f"Completely resetting cache directory: {cache_dir}")
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (cache_dir / "downloads").mkdir(exist_ok=True)
        (cache_dir / "unpacked").mkdir(exist_ok=True)
        (cache_dir / "metadata").mkdir(exist_ok=True)
        
        logger.info("Cache reset completed")
        return
    
    # If not resetting, clean invalid files
    if not cache_dir.exists():
        logger.info(f"Cache directory does not exist: {cache_dir}")
        return
    
    # Check downloads directory
    downloads_dir = cache_dir / "downloads"
    if downloads_dir.exists():
        logger.info(f"Checking downloads directory: {downloads_dir}")
        
        for item in downloads_dir.glob("**/*"):
            if item.is_file():
                if not validate_image_file(item):
                    logger.info(f"Removing invalid file: {item}")
                    try:
                        item.unlink()
                    except Exception as e:
                        logger.error(f"Failed to remove file: {str(e)}")
                    
                    # Also remove the extracted version if it exists
                    if item.suffix.lower() == '.xz':
                        extracted = item.with_suffix('')
                        if extracted.exists():
                            logger.info(f"Removing potentially invalid extracted file: {extracted}")
                            try:
                                extracted.unlink()
                            except Exception as e:
                                logger.error(f"Failed to remove extracted file: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Clean up image cache')
    parser.add_argument('--cache-dir', type=str, default='/tmp/w4b_image_cache',
                        help='Path to the cache directory')
    parser.add_argument('--reset', action='store_true',
                        help='Completely reset the cache directory')
    args = parser.parse_args()
    
    cache_dir = Path(args.cache_dir)
    clean_cache(cache_dir, args.reset)

if __name__ == '__main__':
    main()
