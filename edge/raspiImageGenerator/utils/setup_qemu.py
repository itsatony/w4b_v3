#!/usr/bin/env python3
"""
Setup QEMU for cross-architecture operations.
This script helps set up QEMU static binaries for arm/aarch64 emulation
on x86 hosts.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("qemu-setup")

def check_qemu_installed():
    """Check if QEMU is installed."""
    qemu_path = Path("/usr/bin/qemu-arm-static")
    if qemu_path.exists():
        logger.info("QEMU is already installed")
        return True
    
    logger.warning("QEMU is not installed")
    return False

def install_qemu():
    """Install QEMU and register binfmt handlers."""
    try:
        logger.info("Installing QEMU for cross-architecture support")
        subprocess.run(["apt-get", "update"], check=True)
        subprocess.run(["apt-get", "install", "-y", "qemu-user-static", "binfmt-support"], check=True)
        
        # Register binfmt handlers
        logger.info("Registering binfmt handlers")
        subprocess.run(["update-binfmts", "--enable", "qemu-arm"], check=True)
        
        logger.info("QEMU installation complete")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install QEMU: {str(e)}")
        return False

def check_and_setup():
    """Check and setup QEMU if not installed."""
    if not check_qemu_installed():
        if os.geteuid() != 0:
            logger.error("This script needs to be run as root to install QEMU")
            return False
        
        return install_qemu()
    return True

if __name__ == "__main__":
    if check_and_setup():
        sys.exit(0)
    else:
        sys.exit(1)
