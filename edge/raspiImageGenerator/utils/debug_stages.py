#!/usr/bin/env python3
"""
Debug utility for troubleshooting build stages in the Raspberry Pi image generator.
"""

import os
import sys
import argparse
import logging
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("debug-stages")

async def inspect_mount_point(mount_path: str) -> Dict[str, Any]:
    """
    Inspect a mount point and gather details about its contents.
    
    Args:
        mount_path: Path to the mount point
        
    Returns:
        Dict with mount point information
    """
    results = {
        "path": mount_path,
        "exists": os.path.exists(mount_path),
        "permissions": None,
        "content_count": 0,
        "key_dirs": {},
        "errors": []
    }
    
    if not results["exists"]:
        results["errors"].append(f"Mount point {mount_path} does not exist")
        return results
    
    try:
        # Get permissions
        stats = os.stat(mount_path)
        results["permissions"] = oct(stats.st_mode)[-3:]
        
        # Count contents
        items = os.listdir(mount_path)
        results["content_count"] = len(items)
        
        # Check key directories in root filesystem
        key_dirs = ["bin", "usr", "etc", "lib", "var", "sbin", "opt"]
        for dir_name in key_dirs:
            dir_path = os.path.join(mount_path, dir_name)
            results["key_dirs"][dir_name] = {
                "exists": os.path.exists(dir_path),
                "is_dir": os.path.isdir(dir_path) if os.path.exists(dir_path) else False
            }
            
            # If dir exists, count its contents
            if results["key_dirs"][dir_name]["exists"] and results["key_dirs"][dir_name]["is_dir"]:
                try:
                    results["key_dirs"][dir_name]["content_count"] = len(os.listdir(dir_path))
                except Exception:
                    results["key_dirs"][dir_name]["content_count"] = "error counting"
                    
        # If usr/bin exists, check for apt-get and other essential tools
        bin_path = os.path.join(mount_path, "usr", "bin")
        if os.path.exists(bin_path) and os.path.isdir(bin_path):
            essential_tools = ["apt-get", "apt", "dpkg", "bash", "python3"]
            results["essential_tools"] = {}
            
            for tool in essential_tools:
                tool_path = os.path.join(bin_path, tool)
                results["essential_tools"][tool] = {
                    "exists": os.path.exists(tool_path),
                    "executable": os.access(tool_path, os.X_OK) if os.path.exists(tool_path) else False
                }
    
    except Exception as e:
        results["errors"].append(f"Error inspecting mount point: {str(e)}")
    
    return results

async def test_qemu_setup(root_mount: str) -> Dict[str, Any]:
    """
    Test QEMU setup for ARM emulation.
    
    Args:
        root_mount: Path to the root mount point
        
    Returns:
        Dict with QEMU test results
    """
    results = {
        "host_qemu_paths": [],
        "target_qemu_path": os.path.join(root_mount, "usr", "bin", "qemu-arm-static"),
        "host_qemu_installed": False,
        "target_qemu_exists": False,
        "target_qemu_executable": False,
        "binfmt_registered": False,
        "errors": []
    }
    
    # Check if QEMU is installed on the host
    qemu_paths = [
        "/usr/bin/qemu-arm-static",
        "/usr/local/bin/qemu-arm-static"
    ]
    
    for path in qemu_paths:
        if os.path.exists(path):
            results["host_qemu_paths"].append(path)
            results["host_qemu_installed"] = True
    
    # Check for QEMU in the target
    target_qemu = os.path.join(root_mount, "usr", "bin", "qemu-arm-static")
    if os.path.exists(target_qemu):
        results["target_qemu_exists"] = True
        results["target_qemu_executable"] = os.access(target_qemu, os.X_OK)
    
    # Check binfmt registration
    try:
        binfmt_output = subprocess.check_output(
            ["update-binfmts", "--display"],
            universal_newlines=True
        )
        
        results["binfmt_registered"] = "qemu-arm" in binfmt_output and "enabled" in binfmt_output
        results["binfmt_output"] = binfmt_output
    except Exception as e:
        results["errors"].append(f"Error checking binfmt: {str(e)}")
    
    return results

async def debug_chroot_env(root_mount: str) -> Dict[str, Any]:
    """
    Debug chroot environment setup.
    
    Args:
        root_mount: Path to the root mount point
        
    Returns:
        Dict with chroot debugging information
    """
    results = {
        "mounts": {},
        "resolv_conf": False,
        "errors": []
    }
    
    # Check required mount points for chroot
    mount_points = {
        "proc": os.path.join(root_mount, "proc"),
        "sys": os.path.join(root_mount, "sys"),
        "dev": os.path.join(root_mount, "dev"),
        "dev/pts": os.path.join(root_mount, "dev/pts")
    }
    
    for name, path in mount_points.items():
        results["mounts"][name] = {
            "path": path,
            "exists": os.path.exists(path),
            "mounted": False
        }
    
    # Check if /etc/resolv.conf exists in the chroot
    resolv_conf = os.path.join(root_mount, "etc", "resolv.conf")
    results["resolv_conf"] = os.path.exists(resolv_conf)
    
    # Try to determine if any mounts are active
    try:
        mount_output = subprocess.check_output(["mount"], universal_newlines=True)
        
        for name, mount_info in results["mounts"].items():
            if mount_info["path"] in mount_output:
                mount_info["mounted"] = True
    except Exception as e:
        results["errors"].append(f"Error checking mounts: {str(e)}")
    
    return results

async def try_copy_qemu(root_mount: str) -> Dict[str, Any]:
    """
    Attempt to copy QEMU to the target filesystem.
    
    Args:
        root_mount: Path to the root mount point
        
    Returns:
        Dict with results of the attempt
    """
    results = {
        "source_path": None,
        "target_path": os.path.join(root_mount, "usr", "bin", "qemu-arm-static"),
        "success": False,
        "errors": []
    }
    
    # Check if QEMU is installed on the host
    qemu_paths = [
        "/usr/bin/qemu-arm-static",
        "/usr/local/bin/qemu-arm-static"
    ]
    
    for path in qemu_paths:
        if os.path.exists(path):
            results["source_path"] = path
            break
    
    if not results["source_path"]:
        results["errors"].append("QEMU not found on host system")
        return results
    
    # Create target directory if it doesn't exist
    target_dir = os.path.dirname(results["target_path"])
    if not os.path.exists(target_dir):
        try:
            os.makedirs(target_dir, exist_ok=True)
        except Exception as e:
            results["errors"].append(f"Failed to create target directory: {str(e)}")
            return results
    
    # Copy QEMU to target
    try:
        import shutil
        shutil.copy2(results["source_path"], results["target_path"])
        os.chmod(results["target_path"], 0o755)
        results["success"] = True
    except Exception as e:
        results["errors"].append(f"Failed to copy QEMU: {str(e)}")
    
    return results

async def try_install_qemu_on_host() -> Dict[str, Any]:
    """
    Attempt to install QEMU and binfmt support on the host system.
    
    Returns:
        Dict with results of the installation attempt
    """
    results = {
        "qemu_installed": False,
        "binfmt_installed": False,
        "qemu_path": None,
        "binfmt_enabled": False,
        "errors": []
    }
    
    # Check if running as root
    if os.geteuid() != 0:
        results["errors"].append("Not running as root. Cannot install system packages.")
        return results
    
    try:
        # Update package lists
        subprocess.run(["apt-get", "update"], check=True)
        
        # Install qemu-user-static and binfmt-support
        subprocess.run(
            ["apt-get", "install", "-y", "qemu-user-static", "binfmt-support"],
            check=True
        )
        
        # Check if installation was successful
        if os.path.exists("/usr/bin/qemu-arm-static"):
            results["qemu_installed"] = True
            results["qemu_path"] = "/usr/bin/qemu-arm-static"
        
        # Enable binfmt
        subprocess.run(["update-binfmts", "--enable", "qemu-arm"], check=True)
        
        # Check if binfmt is enabled
        binfmt_output = subprocess.check_output(
            ["update-binfmts", "--display", "qemu-arm"],
            universal_newlines=True
        )
        
        results["binfmt_enabled"] = "enabled" in binfmt_output
        results["binfmt_installed"] = True
        
    except Exception as e:
        results["errors"].append(f"Error installing QEMU: {str(e)}")
    
    return results

async def main() -> None:
    parser = argparse.ArgumentParser(description="Debug build stages for Raspberry Pi image generator")
    parser.add_argument("--root-mount", type=str, default="/tmp/w4b_mnt_root",
                        help="Path to the root mount point")
    parser.add_argument("--boot-mount", type=str, default="/tmp/w4b_mnt_boot",
                        help="Path to the boot mount point")
    parser.add_argument("--fix", action="store_true",
                        help="Attempt to fix issues")
    parser.add_argument("--install-qemu", action="store_true",
                        help="Attempt to install QEMU on the host")
    args = parser.parse_args()
    
    print("\n===== W4B Build Stage Diagnostic Tool =====\n")
    
    # Inspect mount points
    print("Inspecting mount points...")
    root_mount_info = await inspect_mount_point(args.root_mount)
    boot_mount_info = await inspect_mount_point(args.boot_mount)
    
    print(f"\nRoot mount ({args.root_mount}):")
    print(f"  Exists: {'Yes' if root_mount_info['exists'] else 'No'}")
    if root_mount_info['exists']:
        print(f"  Permissions: {root_mount_info['permissions']}")
        print(f"  Content count: {root_mount_info['content_count']}")
        print("\n  Key directories:")
        for dir_name, dir_info in root_mount_info['key_dirs'].items():
            print(f"    {dir_name}: {'Present' if dir_info['exists'] else 'Missing'}")
            if dir_info.get('content_count'):
                print(f"      Items: {dir_info['content_count']}")
        
        if "essential_tools" in root_mount_info:
            print("\n  Essential tools:")
            for tool, tool_info in root_mount_info["essential_tools"].items():
                status = "Missing"
                if tool_info["exists"]:
                    status = "Present" + (" (executable)" if tool_info["executable"] else " (not executable)")
                print(f"    {tool}: {status}")
    
    print(f"\nBoot mount ({args.boot_mount}):")
    print(f"  Exists: {'Yes' if boot_mount_info['exists'] else 'No'}")
    if boot_mount_info['exists']:
        print(f"  Permissions: {boot_mount_info['permissions']}")
        print(f"  Content count: {boot_mount_info['content_count']}")
    
    # Debug QEMU setup
    print("\nChecking QEMU setup...")
    qemu_info = await test_qemu_setup(args.root_mount)
    
    print(f"  Host QEMU installed: {'Yes' if qemu_info['host_qemu_installed'] else 'No'}")
    if qemu_info['host_qemu_installed']:
        print(f"  Host QEMU paths: {', '.join(qemu_info['host_qemu_paths'])}")
    
    print(f"  Target QEMU exists: {'Yes' if qemu_info['target_qemu_exists'] else 'No'}")
    if qemu_info['target_qemu_exists']:
        print(f"  Target QEMU executable: {'Yes' if qemu_info['target_qemu_executable'] else 'No'}")
    
    print(f"  binfmt registration: {'Active' if qemu_info['binfmt_registered'] else 'Inactive'}")
    
    # Debug chroot environment
    print("\nChecking chroot environment...")
    chroot_info = await debug_chroot_env(args.root_mount)
    
    print(f"  resolv.conf present: {'Yes' if chroot_info['resolv_conf'] else 'No'}")
    print("  Mount points:")
    for name, mount_info in chroot_info["mounts"].items():
        status = "Missing"
        if mount_info["exists"]:
            status = "Present" + (" (mounted)" if mount_info["mounted"] else " (not mounted)")
        print(f"    {name}: {status}")
    
    # Try to fix issues if requested
    if args.fix:
        print("\nAttempting to fix issues...")
        
        # Try to copy QEMU to target
        if root_mount_info['exists'] and not qemu_info['target_qemu_exists']:
            print("  Copying QEMU to target filesystem...")
            copy_result = await try_copy_qemu(args.root_mount)
            if copy_result['success']:
                print("  Successfully copied QEMU to target")
            else:
                print(f"  Failed to copy QEMU: {copy_result['errors']}")
    
    # Try to install QEMU on host if requested
    if args.install_qemu:
        print("\nAttempting to install QEMU on host...")
        install_result = await try_install_qemu_on_host()
        if install_result["qemu_installed"]:
            print("  Successfully installed QEMU")
            print(f"  QEMU path: {install_result['qemu_path']}")
        else:
            print(f"  Failed to install QEMU: {install_result['errors']}")
        
        if install_result["binfmt_enabled"]:
            print("  Successfully enabled binfmt")
        else:
            print("  Failed to enable binfmt")
    
    # Print summary
    print("\nDiagnostic summary:")
    issues = []
    if not root_mount_info['exists']:
        issues.append("Root mount point does not exist")
    if not boot_mount_info['exists']:
        issues.append("Boot mount point does not exist")
    if not qemu_info['host_qemu_installed']:
        issues.append("QEMU not installed on host system")
    if root_mount_info['exists'] and not qemu_info['target_qemu_exists']:
        issues.append("QEMU not copied to target filesystem")
    if not qemu_info['binfmt_registered']:
        issues.append("binfmt not registered for QEMU")
    
    if issues:
        print("  Issues found:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("  No issues found")
    
    print("\nRecommendations:")
    if not qemu_info['host_qemu_installed']:
        print("  Install QEMU: sudo apt-get install -y qemu-user-static binfmt-support")
    if not qemu_info['binfmt_registered']:
        print("  Register binfmt: sudo update-binfmts --enable qemu-arm")
    if root_mount_info['exists'] and not qemu_info['target_qemu_exists']:
        print("  Run with --fix to copy QEMU to target")
    if not issues:
        print("  The firstboot approach is recommended for software installation")
        print("  This will install packages when the Raspberry Pi first boots")
        print("  Avoids complex QEMU setup and is more reliable")
    
    print("\nDiagnostic completed.")

if __name__ == "__main__":
    asyncio.run(main())
