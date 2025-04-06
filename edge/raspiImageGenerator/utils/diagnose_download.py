#!/usr/bin/env python3
"""
Diagnostic utility for troubleshooting image download and caching issues.
"""

import os
import sys
import argparse
import logging
import shutil
import requests
from pathlib import Path
from typing import Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("diagnose-download")

def check_file(file_path: str) -> Dict[str, Any]:
    """
    Check a file's details and validity.
    
    Args:
        file_path: Path to the file to check
    
    Returns:
        Dict with file information
    """
    path = Path(file_path)
    results = {
        "exists": path.exists(),
        "size": 0,
        "is_empty": True,
        "permissions": None,
        "valid_header": False,
        "errors": []
    }
    
    if not path.exists():
        results["errors"].append("File does not exist")
        return results
        
    try:
        stats = path.stat()
        results["size"] = stats.st_size
        results["is_empty"] = stats.st_size == 0
        results["permissions"] = oct(stats.st_mode)[-3:]  # Last 3 digits are the permissions
        
        if results["is_empty"]:
            results["errors"].append("File is empty (0 bytes)")
        
        # Check file header
        if path.suffix.lower() == '.xz':
            with open(path, 'rb') as f:
                header = f.read(6)
                
            valid_header = len(header) >= 6 and header[0] == 0xFD and header[1:6] == b'7zXZ\x00'
            results["valid_header"] = valid_header
            
            if not valid_header:
                results["errors"].append("File has invalid XZ header")
        
        elif path.suffix.lower() == '.img':
            with open(path, 'rb') as f:
                boot_sector = f.read(512)
                
            valid_header = len(boot_sector) >= 512 and boot_sector[510:512] == b'\x55\xAA'
            results["valid_header"] = valid_header
            
            if not valid_header:
                results["errors"].append("File does not have a valid boot sector signature")
                
    except Exception as e:
        results["errors"].append(f"Error checking file: {str(e)}")
    
    return results

def check_download_url(url: str) -> Dict[str, Any]:
    """
    Check a download URL for availability and size.
    
    Args:
        url: URL to check
    
    Returns:
        Dict with URL information
    """
    results = {
        "url": url,
        "reachable": False,
        "size": 0,
        "content_type": None,
        "supports_resume": False,
        "errors": []
    }
    
    try:
        # First do a HEAD request to get metadata
        response = requests.head(url, allow_redirects=True, timeout=10)
        
        results["reachable"] = response.status_code == 200
        results["content_type"] = response.headers.get('content-type')
        results["size"] = int(response.headers.get('content-length', 0))
        results["supports_resume"] = 'accept-ranges' in response.headers
        
        if not results["reachable"]:
            results["errors"].append(f"URL returned status code: {response.status_code}")
            
        if results["size"] == 0:
            results["errors"].append("URL does not report content length")
            
    except Exception as e:
        results["errors"].append(f"Error checking URL: {str(e)}")
    
    return results

def check_disk_space(path: str) -> Dict[str, Any]:
    """
    Check available disk space.
    
    Args:
        path: Path to check disk space for
    
    Returns:
        Dict with disk space information
    """
    results = {
        "path": path,
        "total": 0,
        "used": 0,
        "free": 0,
        "sufficient": False,
        "errors": []
    }
    
    try:
        usage = shutil.disk_usage(path)
        results["total"] = usage.total
        results["used"] = usage.used
        results["free"] = usage.free
        
        # Consider 8GB as minimum required space for downloading and extracting RPi images
        required_space = 8 * 1024 * 1024 * 1024
        results["sufficient"] = usage.free >= required_space
        
        if not results["sufficient"]:
            results["errors"].append(
                f"Insufficient disk space: {usage.free/(1024**3):.1f}GB available, "
                f"8GB recommended"
            )
            
    except Exception as e:
        results["errors"].append(f"Error checking disk space: {str(e)}")
    
    return results

def check_cache_directory(cache_dir: str) -> Dict[str, Any]:
    """
    Check the cache directory structure and permissions.
    
    Args:
        cache_dir: Path to the cache directory
    
    Returns:
        Dict with cache directory information
    """
    results = {
        "path": cache_dir,
        "exists": False,
        "writable": False,
        "structure_valid": False,
        "total_size": 0,
        "download_count": 0,
        "unpacked_count": 0,
        "errors": []
    }
    
    path = Path(cache_dir)
    
    if not path.exists():
        results["errors"].append("Cache directory doesn't exist")
        return results
        
    results["exists"] = True
    
    # Check if writable
    try:
        test_file = path / ".write_test"
        with open(test_file, "w") as f:
            f.write("test")
        test_file.unlink()
        results["writable"] = True
    except Exception as e:
        results["errors"].append(f"Cache directory is not writable: {str(e)}")
    
    # Check subdirectory structure
    downloads_dir = path / "downloads"
    unpacked_dir = path / "unpacked"
    metadata_dir = path / "metadata"
    
    structure_valid = (
        downloads_dir.exists() and 
        downloads_dir.is_dir() and
        unpacked_dir.exists() and
        unpacked_dir.is_dir() and
        metadata_dir.exists() and
        metadata_dir.is_dir()
    )
    
    results["structure_valid"] = structure_valid
    
    if not structure_valid:
        results["errors"].append("Cache directory structure is invalid")
    
    # Count and measure size of cached files
    total_size = 0
    download_count = 0
    unpacked_count = 0
    
    if downloads_dir.exists():
        for item in downloads_dir.glob("**/*"):
            if item.is_file():
                total_size += item.stat().st_size
                download_count += 1
    
    if unpacked_dir.exists():
        for item in unpacked_dir.glob("*"):
            if item.is_dir():
                unpacked_count += 1
                for file in item.glob("**/*"):
                    if file.is_file():
                        total_size += file.stat().st_size
    
    results["total_size"] = total_size
    results["download_count"] = download_count
    results["unpacked_count"] = unpacked_count
    
    return results

def main():
    parser = argparse.ArgumentParser(description='Diagnose image download issues')
    parser.add_argument('--cache-dir', type=str, default='/tmp/w4b_image_cache',
                        help='Path to the cache directory')
    parser.add_argument('--check-file', type=str, help='Check a specific file')
    parser.add_argument('--check-url', type=str, 
                        default='https://downloads.raspberrypi.org/raspios_lite_armhf/images/raspios_lite_armhf-2024-11-19/2024-11-19-raspios-bookworm-armhf-lite.img.xz',
                        help='Check a download URL')
    parser.add_argument('--repair', action='store_true', help='Attempt to repair cache issues')
    args = parser.parse_args()
    
    print("\n===== W4B Image Download Diagnostic Tool =====\n")
    
    # Check disk space
    print("Checking disk space...")
    disk_space = check_disk_space("/tmp")
    print(f"  Total: {disk_space['total']/(1024**3):.1f} GB")
    print(f"  Used:  {disk_space['used']/(1024**3):.1f} GB")
    print(f"  Free:  {disk_space['free']/(1024**3):.1f} GB")
    print(f"  Sufficient: {'Yes' if disk_space['sufficient'] else 'No'}")
    
    if disk_space["errors"]:
        print("\nDisk space issues:")
        for error in disk_space["errors"]:
            print(f"  - {error}")
    
    # Check cache directory
    print("\nChecking cache directory...")
    cache_info = check_cache_directory(args.cache_dir)
    print(f"  Path: {cache_info['path']}")
    print(f"  Exists: {'Yes' if cache_info['exists'] else 'No'}")
    print(f"  Writable: {'Yes' if cache_info['writable'] else 'No'}")
    print(f"  Valid structure: {'Yes' if cache_info['structure_valid'] else 'No'}")
    print(f"  Total size: {cache_info['total_size']/(1024**3):.2f} GB")
    print(f"  Downloaded files: {cache_info['download_count']}")
    print(f"  Unpacked images: {cache_info['unpacked_count']}")
    
    if cache_info["errors"]:
        print("\nCache directory issues:")
        for error in cache_info["errors"]:
            print(f"  - {error}")
    
    # Check URL
    if args.check_url:
        print("\nChecking download URL...")
        url_info = check_download_url(args.check_url)
        print(f"  URL: {url_info['url']}")
        print(f"  Reachable: {'Yes' if url_info['reachable'] else 'No'}")
        print(f"  Content type: {url_info['content_type']}")
        print(f"  Reported size: {url_info['size']/(1024**3):.2f} GB")
        print(f"  Supports resume: {'Yes' if url_info['supports_resume'] else 'No'}")
        
        if url_info["errors"]:
            print("\nURL issues:")
            for error in url_info["errors"]:
                print(f"  - {error}")
    
    # Check specific file
    if args.check_file:
        print("\nChecking file...")
        file_info = check_file(args.check_file)
        print(f"  Path: {args.check_file}")
        print(f"  Exists: {'Yes' if file_info['exists'] else 'No'}")
        if file_info['exists']:
            print(f"  Size: {file_info['size']/(1024**1024):.2f} MB")
            print(f"  Empty: {'Yes' if file_info['is_empty'] else 'No'}")
            print(f"  Permissions: {file_info['permissions']}")
            print(f"  Valid header: {'Yes' if file_info['valid_header'] else 'No'}")
        
        if file_info["errors"]:
            print("\nFile issues:")
            for error in file_info["errors"]:
                print(f"  - {error}")
    
    # Repair issues if requested
    if args.repair:
        print("\nAttempting to repair issues...")
        
        # Create cache directory structure if missing
        path = Path(args.cache_dir)
        if not path.exists():
            print(f"  Creating missing cache directory: {path}")
            path.mkdir(parents=True, exist_ok=True)
        
        downloads_dir = path / "downloads"
        unpacked_dir = path / "unpacked"
        metadata_dir = path / "metadata"
        
        for dir_path in [downloads_dir, unpacked_dir, metadata_dir]:
            if not dir_path.exists():
                print(f"  Creating missing directory: {dir_path}")
                dir_path.mkdir(parents=True, exist_ok=True)
        
        # Remove empty or corrupt cached files
        if downloads_dir.exists():
            for item in downloads_dir.glob("**/*"):
                if item.is_file() and (item.stat().st_size == 0 or not check_file(str(item))["valid_header"]):
                    print(f"  Removing corrupt or empty file: {item}")
                    item.unlink()
                    
            # Check for empty directories and remove them
            for item in downloads_dir.glob("**/"):
                if item != downloads_dir and item.is_dir() and not any(item.iterdir()):
                    print(f"  Removing empty directory: {item}")
                    item.rmdir()
        
        print("Repair completed")
    
    print("\nDiagnostic completed.")

if __name__ == "__main__":
    main()
