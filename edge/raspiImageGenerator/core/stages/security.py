#!/usr/bin/env python3
"""
Security configuration stage for the W4B Raspberry Pi Image Generator.

This module implements the security configuration stage of the build pipeline,
responsible for setting up SSH keys, WireGuard VPN, and firewall rules.
"""

import asyncio
import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

from core.stages.base import BuildStage
from utils.error_handling import ImageBuildError, SecurityError


class SecurityConfigStage(BuildStage):
    """
    Build stage for configuring security settings.
    
    This stage is responsible for setting up SSH keys, WireGuard VPN,
    firewall rules, and other security hardening measures.
    
    Attributes:
        name (str): Name of the stage
        state (Dict[str, Any]): Shared pipeline state
        logger (logging.Logger): Logger instance
        circuit_breaker (CircuitBreaker): Circuit breaker for fault tolerance
    """
    
    async def execute(self) -> bool:
        """
        Execute the security configuration stage.
        
        Returns:
            bool: True if configuration succeeded, False otherwise
        """
        try:
            # Get paths from state
            boot_mount = self.state["boot_mount"]
            root_mount = self.state["root_mount"]
            
            # Set up SSH
            await self._configure_ssh(root_mount)
            
            # Set up WireGuard VPN
            await self._configure_vpn(root_mount)
            
            # Set up firewall
            await self._configure_firewall(root_mount)
            
            # Add additional security hardening
            await self._configure_security_hardening(root_mount)
            
            self.logger.info("Security configuration completed successfully")
            return True
            
        except Exception as e:
            self.logger.exception(f"Security configuration failed: {str(e)}")
            return False
    
    async def _configure_ssh(self, root_mount: Path) -> None:
        """
        Configure SSH with secure settings.
        
        Args:
            root_mount: Path to the root file system
        """
        ssh_config = self.state["config"]["security"].get("ssh", {})
        if not ssh_config.get("enabled", True):
            self.logger.info("SSH is disabled, skipping SSH configuration")
            return
        
        # Configure SSH settings
        self.logger.info("Configuring SSH")
        
        # Create SSH config directory
        ssh_config_dir = root_mount / "etc/ssh/sshd_config.d"
        ssh_config_dir.mkdir(exist_ok=True)
        
        # Create custom SSH config
        ssh_port = ssh_config.get("port", 22)
        password_auth = ssh_config.get("password_auth", True)
        allow_root = ssh_config.get("allow_root", False)
        
        with open(ssh_config_dir / "10-w4b.conf", "w") as f:
            f.write(f"# W4B Custom SSH Configuration\n")
            f.write(f"Port {ssh_port}\n")
            f.write(f"PasswordAuthentication {'yes' if password_auth else 'no'}\n")
            f.write(f"PermitRootLogin {'yes' if allow_root else 'no'}\n")
            f.write(f"ChallengeResponseAuthentication no\n")
            f.write(f"UsePAM yes\n")
            f.write(f"X11Forwarding no\n")
            f.write(f"PrintMotd no\n")
            f.write(f"AcceptEnv LANG LC_*\n")
            f.write(f"Subsystem sftp /usr/lib/openssh/sftp-server\n")
        
        # Set up authorized keys
        if "public_key" in ssh_config:
            # Create .ssh directory for root
            root_ssh_dir = root_mount / "root/.ssh"
            root_ssh_dir.mkdir(mode=0o700, exist_ok=True)
            
            # Write public key to authorized_keys
            with open(root_ssh_dir / "authorized_keys", "w") as f:
                f.write(f"{ssh_config['public_key']}\n")
            
            # Set permissions
            (root_ssh_dir / "authorized_keys").chmod(0o600)
            
            self.logger.info("Added SSH public key for root user")
            
            # Also set up for default user (pi) if exists
            pi_home = root_mount / "home/pi"
            if pi_home.exists():
                pi_ssh_dir = pi_home / ".ssh"
                pi_ssh_dir.mkdir(mode=0o700, exist_ok=True)
                
                # Write public key to authorized_keys
                with open(pi_ssh_dir / "authorized_keys", "w") as f:
                    f.write(f"{ssh_config['public_key']}\n")
                
                # Set permissions
                (pi_ssh_dir / "authorized_keys").chmod(0o600)
                
                # Set ownership (assuming pi user has uid/gid 1000)
                os.chown(pi_ssh_dir, 1000, 1000)
                os.chown(pi_ssh_dir / "authorized_keys", 1000, 1000)
                
                self.logger.info("Added SSH public key for pi user")
        
        # Only set up private key if explicitly provided
        if "private_key" in ssh_config:
            # Create .ssh directory for root
            root_ssh_dir = root_mount / "root/.ssh"
            root_ssh_dir.mkdir(mode=0o700, exist_ok=True)
            
            # Write private key
            with open(root_ssh_dir / "id_ed25519", "w") as f:
                f.write(f"{ssh_config['private_key']}\n")
            
            # Set permissions
            (root_ssh_dir / "id_ed25519").chmod(0o600)
            
            self.logger.info("Added SSH private key for root user")
    
    async def _configure_vpn(self, root_mount: Path) -> None:
        """
        Configure WireGuard VPN.
        
        Args:
            root_mount: Path to the root file system
        """
        vpn_config = self.state["config"]["security"].get("vpn", {})
        if not vpn_config.get("enabled", True):
            self.logger.info("VPN is disabled, skipping VPN configuration")
            return
        
        if vpn_config.get("type", "wireguard") != "wireguard":
            self.logger.warning(f"Unsupported VPN type: {vpn_config.get('type')}, only wireguard is supported")
            return
        
        # Create WireGuard directory
        wg_dir = root_mount / "etc/wireguard"
        wg_dir.mkdir(exist_ok=True)
        
        # Check if we have complete WireGuard configuration
        if "private_key" not in vpn_config and "config" not in vpn_config:
            self.logger.warning("Missing WireGuard configuration, skipping VPN setup")
            return
        
        self.logger.info("Configuring WireGuard VPN")
        
        # If we have a complete WireGuard configuration, use that
        if "config" in vpn_config:
            with open(wg_dir / "wg0.conf", "w") as f:
                f.write(vpn_config["config"])
            
            # Set proper permissions
            (wg_dir / "wg0.conf").chmod(0o600)
            
            self.logger.info("Added complete WireGuard configuration")
            
        # Otherwise, build configuration from components
        elif "private_key" in vpn_config:
            server = vpn_config.get("server", "vpn.example.com:51820")
            client_ip = vpn_config.get("client_ip", "10.10.0.2/32")
            public_key = vpn_config.get("public_key", "")
            
            with open(wg_dir / "wg0.conf", "w") as f:
                f.write("[Interface]\n")
                f.write(f"PrivateKey = {vpn_config['private_key']}\n")
                f.write(f"Address = {client_ip}\n")
                f.write("DNS = 1.1.1.1, 8.8.8.8\n")
                f.write("\n")
                
                if public_key:
                    f.write("[Peer]\n")
                    f.write(f"PublicKey = {public_key}\n")
                    f.write(f"Endpoint = {server}\n")
                    f.write("AllowedIPs = 10.10.0.0/24\n")
                    f.write("PersistentKeepalive = 25\n")
            
            # Set proper permissions
            (wg_dir / "wg0.conf").chmod(0o600)
            
            self.logger.info("Created WireGuard configuration from components")
        
        # Add WireGuard service to firstboot
        firstboot_path = Path(self.state["boot_mount"]) / "firstboot.sh"
        
        with open(firstboot_path, "r") as f:
            content = f.readlines()
        
        # Find position to insert package installation (before "Mark setup as complete")
        insert_pos = 0
        for i, line in enumerate(content):
            if "Mark setup as complete" in line:
                insert_pos = i
                break
        
        # Create service configuration section
        wg_lines = [
            "# Enable WireGuard VPN service\n",
            "echo \"Enabling WireGuard VPN service\"\n",
            "systemctl enable wg-quick@wg0\n",
            "systemctl start wg-quick@wg0\n",
            "\n"
        ]
        
        # Insert service lines
        content = content[:insert_pos] + wg_lines + content[insert_pos:]
        
        # Write back to file
        with open(firstboot_path, "w") as f:
            f.writelines(content)
    
    async def _configure_firewall(self, root_mount: Path) -> None:
        """
        Configure firewall rules.
        
        Args:
            root_mount: Path to the root file system
        """
        firewall_config = self.state["config"]["security"].get("firewall", {})
        if not firewall_config.get("enabled", True):
            self.logger.info("Firewall is disabled, skipping firewall configuration")
            return
        
        self.logger.info("Configuring firewall rules")
        
        # Get allowed ports
        allowed_ports = firewall_config.get("allow_ports", [22, 51820, 9100])
        
        # Add firewall configuration to firstboot
        firstboot_path = Path(self.state["boot_mount"]) / "firstboot.sh"
        
        with open(firstboot_path, "r") as f:
            content = f.readlines()
        
        # Find position to insert firewall configuration (before "Mark setup as complete")
        insert_pos = 0
        for i, line in enumerate(content):
            if "Mark setup as complete" in line:
                insert_pos = i
                break
        
        # Create firewall configuration section
        fw_lines = [
            "# Configure firewall rules\n",
            "echo \"Configuring firewall rules\"\n",
            "apt-get install -y ufw\n",
            "ufw default deny incoming\n",
            "ufw default allow outgoing\n"
        ]
        
        # Add allowed ports
        for port in allowed_ports:
            fw_lines.append(f"ufw allow {port}\n")
        
        # Allow connections from VPN subnet
        fw_lines.append(f"ufw allow from 10.10.0.0/24\n")
        
        # Enable firewall
        fw_lines.append("echo 'y' | ufw enable\n")
        fw_lines.append("\n")
        
        # Insert firewall lines
        content = content[:insert_pos] + fw_lines + content[insert_pos:]
        
        # Write back to file
        with open(firstboot_path, "w") as f:
            f.writelines(content)
    
    async def _configure_security_hardening(self, root_mount: Path) -> None:
        """
        Configure additional security hardening measures.
        
        Args:
            root_mount: Path to the root file system
        """
        self.logger.info("Configuring security hardening measures")
        
        # Add security hardening to firstboot
        firstboot_path = Path(self.state["boot_mount"]) / "firstboot.sh"
        
        with open(firstboot_path, "r") as f:
            content = f.readlines()
        
        # Find position to insert security hardening (before "Mark setup as complete")
        insert_pos = 0
        for i, line in enumerate(content):
            if "Mark setup as complete" in line:
                insert_pos = i
                break
        
        # Create security hardening section
        security_lines = [
            "# Security hardening\n",
            "echo \"Applying security hardening\"\n",
            
            # Update system packages
            "apt-get update\n",
            "apt-get upgrade -y\n",
            
            # Secure /tmp directory
            "echo 'tmpfs /tmp tmpfs defaults,nosuid,nodev 0 0' >> /etc/fstab\n",
            
            # Configure automatic security updates
            "apt-get install -y unattended-upgrades apt-listchanges\n",
            "echo 'APT::Periodic::Update-Package-Lists \"1\";' > /etc/apt/apt.conf.d/20auto-upgrades\n",
            "echo 'APT::Periodic::Unattended-Upgrade \"1\";' >> /etc/apt/apt.conf.d/20auto-upgrades\n",
            
            # Disable unnecessary services
            "systemctl disable bluetooth.service\n",
            
            # Set stronger user password policy
            "apt-get install -y libpam-pwquality\n",
            "sed -i 's/# minlen = 8/minlen = 12/' /etc/security/pwquality.conf\n",
            "sed -i 's/# dcredit = 0/dcredit = -1/' /etc/security/pwquality.conf\n",
            "sed -i 's/# ucredit = 0/ucredit = -1/' /etc/security/pwquality.conf\n",
            "sed -i 's/# lcredit = 0/lcredit = -1/' /etc/security/pwquality.conf\n",
            "sed -i 's/# ocredit = 0/ocredit = -1/' /etc/security/pwquality.conf\n",
            
            # Harden sysctl settings
            "cat << EOF > /etc/sysctl.d/99-security.conf\n",
            "# Prevent IP spoofing\n",
            "net.ipv4.conf.all.rp_filter=1\n",
            "net.ipv4.conf.default.rp_filter=1\n",
            "# Disable source routing\n",
            "net.ipv4.conf.all.accept_source_route=0\n",
            "net.ipv4.conf.default.accept_source_route=0\n",
            "# Disable ICMP redirect acceptance\n",
            "net.ipv4.conf.all.accept_redirects=0\n",
            "net.ipv4.conf.default.accept_redirects=0\n",
            "net.ipv6.conf.all.accept_redirects=0\n",
            "net.ipv6.conf.default.accept_redirects=0\n",
            "EOF\n",
            "sysctl --system\n",
            "\n"
        ]
        
        # Insert security hardening lines
        content = content[:insert_pos] + security_lines + content[insert_pos:]
        
        # Write back to file
        with open(firstboot_path, "w") as f:
            f.writelines(content)
