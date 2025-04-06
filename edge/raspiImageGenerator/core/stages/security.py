#!/usr/bin/env python3
"""
Security configuration stage for Raspberry Pi image generator.
"""

import os
import sys
import asyncio
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

from core.stages.base import BuildStage

class SecurityConfigStage(BuildStage):
    """
    Build stage for configuring security settings.
    """
    
    async def execute(self) -> bool:
        try:
            self.logger.info("Starting stage: SecurityConfigStage")
            
            # Check for required mount points
            if "root_mount" not in self.state or "boot_mount" not in self.state:
                raise KeyError("Missing required mount points in state")
            
            root_mount = self.state["root_mount"]
            boot_mount = self.state["boot_mount"]
            
            # Configure SSH
            self.logger.info("Configuring SSH")
            await self._configure_ssh(root_mount)
            
            # Configure VPN
            self.logger.info("Configuring WireGuard VPN")
            await self._configure_vpn(root_mount, boot_mount)
            
            # Configure firewall
            if self.state["config"]["security"].get("firewall", {}).get("enabled", True):
                self.logger.info("Configuring firewall")
                await self._configure_firewall(root_mount)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Security configuration failed: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return False
    
    async def _configure_ssh(self, root_mount: Path) -> None:
        """Configure SSH keys and settings."""
        ssh_config = self.state["config"]["security"].get("ssh", {})
        
        # Create .ssh directories
        root_ssh_dir = root_mount / "root" / ".ssh"
        pi_ssh_dir = root_mount / "home" / "pi" / ".ssh"
        
        root_ssh_dir.mkdir(exist_ok=True, mode=0o700)
        pi_ssh_dir.mkdir(exist_ok=True, mode=0o700)
        
        # Add SSH public key for authorized_keys
        if "public_key" in ssh_config:
            auth_keys_root = root_ssh_dir / "authorized_keys"
            auth_keys_pi = pi_ssh_dir / "authorized_keys"
            
            with open(auth_keys_root, "w") as f:
                f.write(f"{ssh_config['public_key']}\n")
            
            with open(auth_keys_pi, "w") as f:
                f.write(f"{ssh_config['public_key']}\n")
            
            # Set proper permissions
            auth_keys_root.chmod(0o600)
            auth_keys_pi.chmod(0o600)
            
            self.logger.info("Added SSH public key for root user")
            self.logger.info("Added SSH public key for pi user")
        
        # Add SSH private key if provided
        if "private_key" in ssh_config:
            id_key_root = root_ssh_dir / "id_ed25519"
            
            with open(id_key_root, "w") as f:
                f.write(ssh_config["private_key"])
            
            id_key_root.chmod(0o600)
            self.logger.info("Added SSH private key for root user")
        
        # Configure SSH server if needed
        sshd_config_path = root_mount / "etc/ssh/sshd_config"
        if sshd_config_path.exists():
            with open(sshd_config_path, "r") as f:
                lines = f.readlines()
            
            with open(sshd_config_path, "w") as f:
                for line in lines:
                    if line.strip().startswith("PasswordAuthentication "):
                        password_auth = "yes" if ssh_config.get("password_auth", False) else "no"
                        f.write(f"PasswordAuthentication {password_auth}\n")
                    elif line.strip().startswith("PermitRootLogin "):
                        permit_root = "yes" if ssh_config.get("allow_root", False) else "no"
                        f.write(f"PermitRootLogin {permit_root}\n")
                    elif line.strip().startswith("Port "):
                        port = ssh_config.get("port", 22)
                        f.write(f"Port {port}\n")
                    else:
                        f.write(line)
    
    async def _configure_vpn(self, root_mount: Path, boot_mount: Path) -> None:
        """Configure WireGuard VPN."""
        vpn_config = self.state["config"]["security"].get("vpn", {})
        
        if not vpn_config.get("enabled", False):
            self.logger.info("VPN configuration disabled, skipping")
            return
        
        # Create WireGuard configuration directory
        wg_dir = root_mount / "etc/wireguard"
        wg_dir.mkdir(exist_ok=True)
        
        # Create WireGuard configuration file
        config_content = vpn_config.get("config", "")
        wg_conf_path = wg_dir / "wg0.conf"
        
        with open(wg_conf_path, "w") as f:
            f.write(config_content)
        
        # Set proper permissions
        wg_conf_path.chmod(0o600)
        
        # Create firstboot script to enable WireGuard on first boot
        # First, ensure boot directory exists in our working directory
        boot_firstboot_path = boot_mount / "firstboot.sh"
        
        # Create the firstboot.sh script
        with open(boot_firstboot_path, "w") as f:
            f.write("""#!/bin/bash
# Enable WireGuard VPN on first boot
systemctl enable wg-quick@wg0
systemctl start wg-quick@wg0
""")
        
        # Make it executable
        boot_firstboot_path.chmod(0o755)
        
        # Create a script to run the firstboot.sh script on first boot
        rc_local_path = root_mount / "etc/rc.local"
        
        if rc_local_path.exists():
            with open(rc_local_path, "r") as f:
                content = f.read()
            
            # Add our command before exit 0
            if "exit 0" in content:
                content = content.replace("exit 0", "if [ -f /boot/firstboot.sh ]; then\n  /boot/firstboot.sh\n  rm /boot/firstboot.sh\nfi\nexit 0")
            else:
                content += "\nif [ -f /boot/firstboot.sh ]; then\n  /boot/firstboot.sh\n  rm /boot/firstboot.sh\nfi\n"
            
            with open(rc_local_path, "w") as f:
                f.write(content)
        else:
            # Create rc.local if it doesn't exist
            with open(rc_local_path, "w") as f:
                f.write("""#!/bin/bash
if [ -f /boot/firstboot.sh ]; then
  /boot/firstboot.sh
  rm /boot/firstboot.sh
fi
exit 0
""")
            rc_local_path.chmod(0o755)
        
        self.logger.info("Added complete WireGuard configuration")
    
    async def _configure_firewall(self, root_mount: Path) -> None:
        """Configure firewall rules."""
        firewall_config = self.state["config"]["security"].get("firewall", {})
        allowed_ports = firewall_config.get("allow_ports", [22, 51820])
        
        # Create firewall configuration script
        fw_script_path = root_mount / "etc/wireguard/firewall.sh"
        
        with open(fw_script_path, "w") as f:
            f.write("#!/bin/bash\n\n")
            f.write("# Flush existing rules\n")
            f.write("iptables -F\n")
            f.write("iptables -X\n\n")
            
            f.write("# Set default policies\n")
            f.write("iptables -P INPUT DROP\n")
            f.write("iptables -P FORWARD DROP\n")
            f.write("iptables -P OUTPUT ACCEPT\n\n")
            
            f.write("# Allow loopback\n")
            f.write("iptables -A INPUT -i lo -j ACCEPT\n\n")
            
            f.write("# Allow established and related\n")
            f.write("iptables -A INPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT\n\n")
            
            f.write("# Allow specific ports\n")
            for port in allowed_ports:
                f.write(f"iptables -A INPUT -p tcp --dport {port} -j ACCEPT\n")
                f.write(f"iptables -A INPUT -p udp --dport {port} -j ACCEPT\n")
            
            f.write("\n# Allow ICMP\n")
            f.write("iptables -A INPUT -p icmp -j ACCEPT\n\n")
            
            f.write("# Allow WireGuard interface\n")
            f.write("iptables -A INPUT -i wg0 -j ACCEPT\n\n")
            
            f.write("# Save rules\n")
            f.write("iptables-save > /etc/iptables/rules.v4\n")
        
        # Make script executable
        fw_script_path.chmod(0o755)
        
        # Add to rc.local to run on boot
        rc_local_path = root_mount / "etc/rc.local"
        
        if rc_local_path.exists():
            with open(rc_local_path, "r") as f:
                content = f.read()
            
            if "firewall.sh" not in content:
                if "exit 0" in content:
                    content = content.replace("exit 0", "/etc/wireguard/firewall.sh\nexit 0")
                else:
                    content += "\n/etc/wireguard/firewall.sh\n"
            
            with open(rc_local_path, "w") as f:
                f.write(content)
        
        # Ensure iptables package is installed - add to software list
        if "software" not in self.state:
            self.state["software"] = {}
        
        if "packages" not in self.state["software"]:
            self.state["software"]["packages"] = []
        
        if "iptables-persistent" not in self.state["software"]["packages"]:
            self.state["software"]["packages"].append("iptables-persistent")
        
        self.logger.info("Added firewall configuration")
