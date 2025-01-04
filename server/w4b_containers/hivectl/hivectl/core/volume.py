# /hivectl/core/volume.py
"""
Volume management functionality for HiveCtl.
"""
import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

from .exceptions import VolumeError, VolumeNotFound, VolumeOperationError
from .utils import run_command

logger = logging.getLogger('hivectl.volume')

@dataclass
class VolumeStatus:
    """Volume status information."""
    name: str
    driver: str
    mountpoint: str
    size: str
    created: str
    labels: Dict[str, str]

    def to_dict(self):
        return asdict(self)

class VolumeManager:
    """Manages container volume operations."""
    
    def __init__(self, compose_config):
        """
        Initialize volume manager.
        
        Args:
            compose_config: Parsed compose configuration
        """
        self.compose = compose_config
        self._tmp_dir = None

    def _parse_volume_df_output(self, output: str) -> Dict[str, str]:
        """
        Parse the output of 'podman system df -v' to get volume sizes.
        
        Args:
            output: Raw command output
            
        Returns:
            Dict[str, str]: Mapping of volume names to their sizes
        """
        volumes = {}
        in_volumes_section = False
        for line in output.splitlines():
            if "Local Volumes space usage:" in line:
                in_volumes_section = True
                continue
            if in_volumes_section:
                if not line.strip() or line.startswith("VOLUME"):
                    continue
                if line.startswith("Containers space usage:"):  # Next section
                    break
                try:
                    parts = line.split()
                    if len(parts) >= 3:
                        name = parts[0]
                        size = parts[2]
                        volumes[name] = size
                except Exception as e:
                    logger.debug(f"Failed to parse volume line: {line}, error: {e}")
                    continue
        return volumes

    def get_volume_status(self, volume_name: Optional[str] = None) -> List[VolumeStatus]:
        """Get status of volumes."""
        try:
            cmd = "podman volume ls --format json"
            result = run_command(cmd)
            
            try:
                volumes = json.loads(result.stdout)
                if not isinstance(volumes, list):
                    volumes = [volumes]
            except json.JSONDecodeError:
                logger.error(f"Failed to parse volume list output: {result.stdout}")
                return []

            # Get volume sizes from system df
            try:
                df_cmd = "podman system df -v"
                df_result = run_command(df_cmd)
                volume_sizes = self._parse_volume_df_output(df_result.stdout)
            except Exception as e:
                logger.warning(f"Failed to get volume sizes: {e}")
                volume_sizes = {}

            status_list = []
            for vol in volumes:
                if volume_name and vol['Name'] != volume_name:
                    continue
                
                try:
                    # Get detailed volume info
                    detail_cmd = f"podman volume inspect {vol['Name']}"
                    detail_result = run_command(detail_cmd)
                    details = json.loads(detail_result.stdout)[0]

                    # Get volume size from parsed df output
                    size = volume_sizes.get(vol['Name'], 'N/A')

                    status = VolumeStatus(
                        name=vol['Name'],
                        driver=details.get('Driver', 'local'),
                        mountpoint=details.get('Mountpoint', ''),
                        size=size,
                        created=details.get('CreatedAt', 'N/A'),
                        labels=details.get('Labels', {})
                    )
                    status_list.append(status)
                except Exception as e:
                    logger.warning(f"Failed to get details for volume {vol['Name']}: {e}")
                    # Add basic volume info even if details fail
                    status = VolumeStatus(
                        name=vol['Name'],
                        driver='local',
                        mountpoint='',
                        size='N/A',
                        created='N/A',
                        labels={}
                    )
                    status_list.append(status)

            return status_list

        except Exception as e:
            logger.error(f"Failed to get volume status: {e}")
            raise VolumeError(f"Failed to get volume status: {e}")

    def create_volume(self, volume_name: str, config: dict = None) -> bool:
        """
        Create a volume if it doesn't exist.
        
        Args:
            volume_name: Name of the volume
            config: Volume configuration (optional)
            
        Returns:
            bool: Success status
        """
        try:
            # Check if volume exists
            existing = self.get_volume_status(volume_name)
            if existing:
                logger.debug(f"Volume {volume_name} already exists")
                return True
                
            cmd_parts = ["podman", "volume", "create"]
            
            if config:
                # Add volume options from config
                for key, value in config.items():
                    if key not in ['external', 'name']:  # Skip compose-specific keys
                        cmd_parts.extend([f"--opt={key}={value}"])
                
            cmd_parts.append(volume_name)
            cmd = " ".join(cmd_parts)
            
            run_command(cmd)
            logger.info(f"Created volume: {volume_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create volume {volume_name}: {e}")
            raise VolumeOperationError(f"Failed to create volume: {e}")

    def remove_volume(self, volume_name: str, force: bool = False) -> bool:
        """Remove a volume."""
        try:
            cmd = f"podman volume rm {'--force' if force else ''} {volume_name}"
            run_command(cmd)
            logger.info(f"Removed volume: {volume_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove volume {volume_name}: {e}")
            raise VolumeOperationError(f"Failed to remove volume: {e}")

    def ensure_volumes(self) -> bool:
        """
        Ensure all volumes defined in compose exist.
        
        Returns:
            bool: Success status
        """
        success = True
        for service, volumes in self.compose.volumes.items():
            for vol_type, vol_config in volumes.items():
                try:
                    self.create_volume(vol_config['name'], vol_config.get('config'))
                except Exception as e:
                    logger.error(f"Failed to ensure volume {vol_config['name']}: {e}")
                    success = False
                    
        return success

    def validate_volumes(self) -> Dict[str, dict]:
        """Validate all required volumes exist."""
        try:
            # Get all existing volumes
            cmd = "podman volume ls --format json"
            result = run_command(cmd)
            volumes = json.loads(result.stdout) if result.stdout.strip() else []
            if not isinstance(volumes, list):
                volumes = [volumes] if volumes else []

            # Get volume sizes
            df_cmd = "podman system df -v"
            df_result = run_command(df_cmd)
            volume_sizes = self._parse_volume_df_output(df_result.stdout)

            validation = {}
            
            # Iterate through compose volumes
            for service_name, service_volumes in self.compose.volumes.items():
                if service_name not in validation:
                    validation[service_name] = {}
                    
                for volume_name, volume_config in service_volumes.items():
                    volume_full_name = volume_config['name']
                    
                    # Check if volume exists
                    exists = any(v['Name'] == volume_full_name for v in volumes)
                    size = volume_sizes.get(volume_full_name, 'N/A')
                    
                    validation[service_name][volume_name] = {
                        'name': volume_full_name,
                        'exists': exists,
                        'details': {
                            'size': size,
                            'driver': 'local'
                        } if exists else None
                    }

            return validation

        except Exception as e:
            logger.error(f"Failed to validate volumes: {e}")
            return {}

    def backup_volume(self, volume_name: str, backup_path: Path) -> bool:
        """
        Backup a volume to a tar file.
        
        Args:
            volume_name: Name of the volume to backup
            backup_path: Path to store the backup
            
        Returns:
            bool: Success status
        """
        try:
            # Create backup directory if it doesn't exist
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create temporary container to access volume
            cmd = f"""podman run --rm -v {volume_name}:/source:ro \
                     -v {backup_path.parent}:/backup \
                     alpine tar czf /backup/{backup_path.name} -C /source ."""
            
            run_command(cmd)
            logger.info(f"Backed up volume {volume_name} to {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to backup volume {volume_name}: {e}")
            raise VolumeOperationError(f"Failed to backup volume: {e}")

    def restore_volume(self, volume_name: str, backup_path: Path) -> bool:
        """
        Restore a volume from a backup file.
        
        Args:
            volume_name: Name of the volume to restore
            backup_path: Path to the backup file
            
        Returns:
            bool: Success status
        """
        try:
            if not backup_path.exists():
                raise VolumeError(f"Backup file not found: {backup_path}")
                
            # Ensure volume exists
            self.create_volume(volume_name)
            
            # Restore from backup using temporary container
            cmd = f"""podman run --rm -v {volume_name}:/target \
                     -v {backup_path}:/backup.tar.gz:ro \
                     alpine sh -c "cd /target && tar xzf /backup.tar.gz"""
            
            run_command(cmd)
            logger.info(f"Restored volume {volume_name} from {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore volume {volume_name}: {e}")
            raise VolumeOperationError(f"Failed to restore volume: {e}")

    def copy_config_to_volume(self, service: str, config_path: Path) -> bool:
        """
        Copy configuration files to a service volume.
        
        Args:
            service: Service name
            config_path: Path to configuration files
            
        Returns:
            bool: Success status
        """
        try:
            # Get config volume for service
            volumes = self.compose.volumes.get(service, {})
            config_volume = next(
                (v['name'] for k, v in volumes.items() if 'config' in k.lower()),
                None
            )
            
            if not config_volume:
                logger.warning(f"No config volume found for service {service}")
                return False
                
            if not config_path.exists():
                logger.warning(f"Config path does not exist: {config_path}")
                return False
                
            # Create temporary directory for staging
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Copy files to staging directory
                run_command(f"cp -r {config_path}/* {temp_path}/")
                run_command(f"chmod -R 755 {temp_path}")
                
                # Copy to volume using temporary container
                cmd = f"""podman run --rm \
                         -v {config_volume}:/dest \
                         -v {temp_path}:/src:ro \
                         alpine sh -c "cp -r /src/* /dest/ && chown -R 1000:1000 /dest/"
                """
                run_command(cmd)
                
            logger.info(f"Copied config files to volume {config_volume}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to copy config files for {service}: {e}")
            raise VolumeOperationError(f"Failed to copy config files: {e}")

    def get_volume_logs(self, volume_name: str) -> Optional[str]:
        """
        Get volume logs if available.
        
        Args:
            volume_name: Name of the volume
            
        Returns:
            Optional[str]: Log content if available
        """
        try:
            status = self.get_volume_status(volume_name)
            if not status:
                raise VolumeNotFound(f"Volume {volume_name} not found")
                
            mountpoint = status[0].mountpoint
            if not mountpoint:
                return None
                
            # Look for log files in the volume
            log_paths = [
                Path(mountpoint) / 'logs',
                Path(mountpoint) / 'log',
                Path(mountpoint) / '*.log'
            ]
            
            for log_path in log_paths:
                if log_path.exists():
                    cmd = f"tail -n 1000 {log_path}/*.log 2>/dev/null || true"
                    result = run_command(cmd)
                    if result.stdout.strip():
                        return result.stdout
                        
            return None
            
        except Exception as e:
            logger.error(f"Failed to get volume logs for {volume_name}: {e}")
            return None

    def cleanup_volumes(self, all_volumes: bool = False) -> Tuple[int, List[str]]:
        """
        Clean up unused volumes.
        
        Args:
            all_volumes: Whether to remove all volumes or just unused ones
            
        Returns:
            Tuple[int, List[str]]: Count of removed volumes and their names
        """
        try:
            cmd = f"podman volume prune -f {'--all' if all_volumes else ''}"
            result = run_command(cmd)
            
            # Parse output to get removed volumes
            removed = []
            for line in result.stdout.splitlines():
                if "Deleted" in line:
                    volume = line.split()[-1]
                    removed.append(volume)
                    
            logger.info(f"Cleaned up {len(removed)} volumes")
            return len(removed), removed
            
        except Exception as e:
            logger.error(f"Failed to cleanup volumes: {e}")
            raise VolumeOperationError(f"Failed to cleanup volumes: {e}")