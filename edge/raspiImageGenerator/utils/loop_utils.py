#!/usr/bin/env python3
"""
Utility functions for working with loop devices.

This module provides helper functions for working with loop devices and partition detection.
It can be used both programmatically and as a command-line utility.
"""

import os
import sys
import argparse
import subprocess
import time
from pathlib import Path
import glob
import json

def setup_loop_device(image_path: str, force_partition: bool = True) -> dict:
    """
    Set up a loop device for an image file.
    
    Args:
        image_path: Path to the image file
        force_partition: Whether to use -P flag to force partition scanning
        
    Returns:
        dict: Information about the created loop device
    """
    cmd = ['losetup', '-f', '--show']
    if force_partition:
        cmd.insert(1, '-P')
    cmd.append(image_path)
    
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error setting up loop device: {result.stderr}")
        return {}
    
    loop_device = result.stdout.strip()
    if not loop_device:
        print("Failed to get loop device path")
        return {}
    
    print(f"Created loop device: {loop_device}")
    
    # Wait for partitions to be recognized
    time.sleep(1)
    
    # Get partition information
    fdisk_result = subprocess.run(['fdisk', '-l', loop_device], capture_output=True, text=True)
    fdisk_output = fdisk_result.stdout
    
    # Find partitions
    partitions = glob.glob(f"{loop_device}*")
    partitions = [p for p in partitions if p != loop_device]
    
    # Try device mapper if no partitions found
    device_mapper_partitions = []
    if not partitions:
        print("No partitions found with standard naming, trying kpartx")
        kpartx_result = subprocess.run(['kpartx', '-avs', loop_device], capture_output=True, text=True)
        print(f"kpartx output: {kpartx_result.stdout}")
        
        # Wait for device mapper
        time.sleep(1)
        
        # Check device mapper
        loop_name = os.path.basename(loop_device)
        mapper_paths = [
            f"/dev/mapper/{loop_name}p1",
            f"/dev/mapper/{loop_name}1",
            f"/dev/mapper/loop{loop_name.replace('loop', '')}p1"
        ]
        
        for path in mapper_paths:
            if os.path.exists(path):
                print(f"Found mapper device: {path}")
                device_mapper_partitions.append(path)
                # Add the second partition too
                second_part = path.replace("p1", "p2").replace("1", "2")
                if os.path.exists(second_part):
                    device_mapper_partitions.append(second_part)
    
    return {
        "loop_device": loop_device,
        "partitions": partitions,
        "device_mapper_partitions": device_mapper_partitions,
        "fdisk_output": fdisk_output
    }

def detach_loop_device(loop_device: str) -> bool:
    """
    Detach a loop device.
    
    Args:
        loop_device: Path to the loop device
        
    Returns:
        bool: True if successful, False otherwise
    """
    # First try to clean up kpartx mappings
    subprocess.run(['kpartx', '-d', loop_device], capture_output=True)
    
    # Now detach the loop device
    result = subprocess.run(['losetup', '-d', loop_device], capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Failed to detach loop device: {result.stderr}")
        return False
    
    print(f"Detached loop device: {loop_device}")
    return True

def find_attached_loops() -> list:
    """
    Find all attached loop devices.
    
    Returns:
        list: List of attached loop devices and their backing files
    """
    result = subprocess.run(['losetup', '-l', '-J'], capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error listing loop devices: {result.stderr}")
        return []
    
    try:
        loop_data = json.loads(result.stdout)
        return loop_data.get('loopdevices', [])
    except json.JSONDecodeError:
        print("Failed to parse losetup output")
        return []

def debug_system_devices():
    """Print debug information about system devices"""
    print("\n=== SYSTEM DEVICES DEBUG ===")
    
    # List all loop devices
    print("\n--- Loop Devices ---")
    subprocess.run(['losetup', '-l'], check=False)
    
    # List all block devices
    print("\n--- Block Devices ---")
    subprocess.run(['lsblk'], check=False)
    
    # List device mapper devices
    print("\n--- Device Mapper ---")
    dm_list = glob.glob('/dev/mapper/*')
    print(f"Device mapper entries: {dm_list}")
    
    # Check for kpartx availability
    print("\n--- kpartx Status ---")
    kpartx_result = subprocess.run(['which', 'kpartx'], capture_output=True, text=True)
    if kpartx_result.returncode == 0:
        print(f"kpartx found at: {kpartx_result.stdout.strip()}")
    else:
        print("kpartx not found in PATH")

def main():
    """Command-line entry point"""
    parser = argparse.ArgumentParser(description='Loop device utility')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Setup command
    setup_parser = subparsers.add_parser('setup', help='Set up a loop device')
    setup_parser.add_argument('image_path', help='Path to the image file')
    setup_parser.add_argument('--no-partition', action='store_true', help='Do not force partition scanning')
    
    # Detach command
    detach_parser = subparsers.add_parser('detach', help='Detach a loop device')
    detach_parser.add_argument('loop_device', help='Path to the loop device')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List all loop devices')
    
    # Debug command
    debug_parser = subparsers.add_parser('debug', help='Debug system devices')
    
    # Parse arguments
    args = parser.parse_args()
    
    if args.command == 'setup':
        result = setup_loop_device(args.image_path, not args.no_partition)
        print(json.dumps(result, indent=2))
    elif args.command == 'detach':
        success = detach_loop_device(args.loop_device)
        sys.exit(0 if success else 1)
    elif args.command == 'list':
        loops = find_attached_loops()
        print(json.dumps(loops, indent=2))
    elif args.command == 'debug':
        debug_system_devices()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
