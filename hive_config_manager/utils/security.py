#!/usr/bin/env python3
"""
Security Utilities for Hive Configuration Manager
"""

import os
import subprocess
import tempfile
import secrets
import string
import base64
import hashlib
from pathlib import Path
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class SecurityUtils:
    """
    Provides security-related utilities for hive management.
    
    Features:
    - SSH key pair generation
    - WireGuard configuration generation
    - Secure password generation
    """
    
    @staticmethod
    def generate_ssh_keypair(comment: str = "hive-access") -> Dict[str, str]:
        """
        Generate a new SSH key pair.
        
        Args:
            comment: Comment to include in the SSH key
            
        Returns:
            Dict containing 'private_key' and 'public_key'
            
        Raises:
            RuntimeError: If key generation fails
        """
        try:
            # Create a temporary directory for key generation
            with tempfile.TemporaryDirectory() as tmp_dir:
                key_path = Path(tmp_dir) / "hive_key"
                
                # Generate key pair using ssh-keygen
                subprocess.run([
                    "ssh-keygen", 
                    "-t", "ed25519",
                    "-f", str(key_path),
                    "-N", "",  # No passphrase
                    "-C", comment
                ], check=True, capture_output=True)
                
                # Read the generated keys
                private_key = key_path.read_text()
                public_key = (key_path.with_suffix(".pub")).read_text()
                
                return {
                    "private_key": private_key.strip(),
                    "public_key": public_key.strip()
                }
        except subprocess.CalledProcessError as e:
            logger.error(f"SSH key generation failed: {e.stderr.decode()}")
            raise RuntimeError(f"Failed to generate SSH key pair: {e}")
        except Exception as e:
            logger.error(f"SSH key generation error: {str(e)}")
            raise RuntimeError(f"Error during SSH key generation: {str(e)}")

    @staticmethod
    def generate_wireguard_keys() -> Dict[str, str]:
        """
        Generate WireGuard private and public keys.
        
        Returns:
            Dict containing 'private_key' and 'public_key'
            
        Raises:
            RuntimeError: If key generation fails
        """
        try:
            # Generate private key
            private_key = subprocess.run(
                ["wg", "genkey"],
                check=True, capture_output=True, text=True
            ).stdout.strip()
            
            # Generate public key from private key
            public_key = subprocess.run(
                ["wg", "pubkey"], 
                input=private_key,
                check=True, capture_output=True, text=True
            ).stdout.strip()
            
            return {
                "private_key": private_key,
                "public_key": public_key
            }
        except subprocess.CalledProcessError as e:
            logger.error(f"WireGuard key generation failed: {e.stderr}")
            raise RuntimeError(f"Failed to generate WireGuard keys: {e}")
        except Exception as e:
            logger.error(f"WireGuard key generation error: {str(e)}")
            raise RuntimeError(f"Error during WireGuard key generation: {str(e)}")

    @staticmethod
    def generate_wireguard_config(
        private_key: str,
        server_public_key: str,
        server_endpoint: str,
        allowed_ips: str = "10.10.0.0/24",
        client_ip: str = "10.10.0.X/32",
        persistent_keepalive: int = 25
    ) -> str:
        """
        Generate a WireGuard client configuration.
        
        Args:
            private_key: Client's private key
            server_public_key: Server's public key
            server_endpoint: Server's endpoint (IP:Port)
            allowed_ips: IPs that should be routed through the VPN
            client_ip: Client's IP address in the VPN network
            persistent_keepalive: Keepalive interval in seconds
            
        Returns:
            WireGuard configuration as a string
        """
        config = f"""[Interface]
PrivateKey = {private_key}
Address = {client_ip}
DNS = 1.1.1.1, 8.8.8.8

[Peer]
PublicKey = {server_public_key}
Endpoint = {server_endpoint}
AllowedIPs = {allowed_ips}
PersistentKeepalive = {persistent_keepalive}
"""
        return config

    @staticmethod
    def generate_secure_password(length: int = 16) -> str:
        """
        Generate a secure random password.
        
        Args:
            length: Length of the password
            
        Returns:
            A secure random password string
        """
        # Include all types of characters for a strong password
        alphabet = string.ascii_letters + string.digits + string.punctuation
        
        # Ensure at least one of each type is included
        password = [
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.digits),
            secrets.choice(string.punctuation)
        ]
        
        # Fill the rest with random characters
        password.extend(secrets.choice(alphabet) for _ in range(length - 4))
        
        # Shuffle the password characters
        secrets.SystemRandom().shuffle(password)
        
        return ''.join(password)

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Create a salted hash of a password.
        
        Args:
            password: The raw password to hash
            
        Returns:
            A formatted hash string which includes algorithm, salt, and hash
        """
        salt = os.urandom(16)
        hash_obj = hashlib.pbkdf2_hmac(
            'sha256', 
            password.encode(), 
            salt, 
            100000,  # Number of iterations
            dklen=64  # Length of the derived key
        )
        
        # Format as algorithm$iterations$salt$hash
        return (
            f"pbkdf2_sha256$100000$"
            f"{base64.b64encode(salt).decode()}$"
            f"{base64.b64encode(hash_obj).decode()}"
        )

    @staticmethod
    def verify_password(stored_hash: str, password: str) -> bool:
        """
        Verify a password against a stored hash.
        
        Args:
            stored_hash: The stored hash string from hash_password()
            password: The raw password to verify
            
        Returns:
            True if the password matches, False otherwise
        """
        if not stored_hash or not password:
            return False
            
        try:
            # Parse the stored hash
            algorithm, iterations, salt_b64, hash_b64 = stored_hash.split('$')
            
            if algorithm != "pbkdf2_sha256":
                return False
                
            iterations = int(iterations)
            salt = base64.b64decode(salt_b64)
            stored = base64.b64decode(hash_b64)
            
            # Calculate hash of the input password
            hash_obj = hashlib.pbkdf2_hmac(
                'sha256', 
                password.encode(), 
                salt, 
                iterations,
                dklen=len(stored)
            )
            
            # Compare in constant time to prevent timing attacks
            return secrets.compare_digest(hash_obj, stored)
        except (ValueError, TypeError):
            return False
