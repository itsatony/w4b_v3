#!/usr/bin/env python3
"""
Utility to check and install system dependencies required for image generation.
"""

import os
import logging
import subprocess
import sys
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("dependencies")

REQUIRED_PACKAGES = [
    "qemu-user-static",
    "binfmt-support",
    "kpartx",
    "parted",
    "e2fsprogs",
    "dosfstools",
    "mount",
    "xz-utils"
]

def check_dependencies():
    """Check if all required dependencies are installed."""
    logger.info("Checking required system dependencies...")
    
    missing_packages = []
    
    for package in REQUIRED_PACKAGES:
        try:
            # Try to find the package using which or dpkg
            if package == "qemu-user-static":
                if not Path("/usr/bin/qemu-arm-static").exists() and not Path("/usr/local/bin/qemu-arm-static").exists():
                    missing_packages.append(package)
            else:
                # For other packages, check with dpkg
                result = subprocess.run(
                    ["dpkg", "-s", package], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True
                )
                if result.returncode != 0:
                    missing_packages.append(package)
        except Exception:
            missing_packages.append(package)
    
    if missing_packages:
        logger.warning(f"Missing required packages: {', '.join(missing_packages)}")
        return False, missing_packages
    else:
        logger.info("All required dependencies are installed.")
        return True, []

def install_dependencies(missing_packages=None):
    """
    Install missing dependencies.
    
    Args:
        missing_packages: List of packages to install. If None, check first.
        
    Returns:
        bool: True if successful, False otherwise
    """
    if missing_packages is None:
        all_installed, missing_packages = check_dependencies()
        if all_installed:
            return True
    
    if not missing_packages:
        return True
        
    # Check if running as root
    if os.geteuid() != 0:
        logger.error("Need to run as root to install dependencies.")
        logger.info(f"Run: sudo apt-get update && sudo apt-get install -y {' '.join(missing_packages)}")
        return False
    
    logger.info(f"Installing missing packages: {', '.join(missing_packages)}")
    
    try:
        # Update package lists
        subprocess.run(["apt-get", "update"], check=True)
        
        # Install missing packages
        subprocess.run(["apt-get", "install", "-y"] + missing_packages, check=True)
        
        # Verify installation
        all_installed, still_missing = check_dependencies()
        
        if still_missing:
            logger.error(f"Failed to install some packages: {', '.join(still_missing)}")
            return False
            
        logger.info("All dependencies installed successfully.")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install dependencies: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return False

def setup_binfmt():
    """
    Ensure binfmt_misc is properly set up for QEMU emulation.
    
    Returns:
        bool: True if successful, False otherwise
    """
    logger.info("Setting up binfmt_misc support for QEMU...")
    
    try:
        # Check if running as root
        if os.geteuid() != 0:
            logger.error("Need to run as root to set up binfmt_misc.")
            logger.info("Run: sudo update-binfmts --enable qemu-arm")
            return False
        
        # Update binfmt
        subprocess.run(["update-binfmts", "--enable", "qemu-arm"], check=True)
        
        # Verify setup
        result = subprocess.run(
            ["update-binfmts", "--display", "qemu-arm"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if "enabled" in result.stdout:
            logger.info("binfmt_misc correctly set up for QEMU emulation.")
            return True
        else:
            logger.warning("binfmt_misc might not be properly configured.")
            return False
            
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to set up binfmt_misc: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return False

def check_for_sudo():
    """Check if the script is running with sudo/root privileges."""
    if os.geteuid() != 0:
        logger.warning("This script is not running with root privileges.")
        logger.warning("Some operations may fail. Consider running with sudo.")
        return False
    return True

def main():
    """Main function for command-line use."""
    check_for_sudo()
    
    all_installed, missing_packages = check_dependencies()
    
    if not all_installed:
        if check_for_sudo():
            logger.info("Installing missing dependencies...")
            if install_dependencies(missing_packages):
                logger.info("Dependencies installed successfully.")
            else:
                logger.error("Failed to install some dependencies.")
                sys.exit(1)
        else:
            logger.error("Cannot install missing dependencies without root privileges.")
            logger.info(f"Run: sudo apt-get update && sudo apt-get install -y {' '.join(missing_packages)}")
            sys.exit(1)
    
    # Set up binfmt_misc if running as root
    if check_for_sudo():
        if setup_binfmt():
            logger.info("binfmt_misc setup completed successfully.")
        else:
            logger.warning("binfmt_misc setup may not be complete.")
    
    logger.info("System ready for image generation.")

if __name__ == "__main__":
    main()
