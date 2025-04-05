# hive_config_manager/core/validator.py

import re
import ipaddress
from typing import List, Dict, Any, Optional
from datetime import datetime
import pytz

from .exceptions import ValidationError
from ..utils.id_generator import is_valid_hive_id, is_valid_sensor_id

class ConfigValidator:
    """
    Validates hive configurations against defined rules and constraints.
    
    This validator checks:
    - Required fields presence
    - Data types and formats
    - Value ranges and constraints
    - Logical relationships between fields
    """

    def __init__(self):
        self.errors: List[str] = []

    def validate(self, config: Dict[str, Any]) -> List[str]:
        """
        Validate complete hive configuration.
        
        Args:
            config: Dictionary containing hive configuration
            
        Returns:
            List of validation error messages (empty if valid)
        """
        self.errors = []
        
        # Check required top-level fields
        required_fields = [
            'version', 'metadata', 'network', 'administrators',
            'collector', 'sensors', 'maintenance'
        ]
        self._check_required_fields(config, required_fields)
        
        if not self.errors:
            # Version format
            self._validate_version(config['version'])
            
            # Validate each section
            self._validate_metadata(config['metadata'])
            self._validate_network(config['network'])
            self._validate_administrators(config['administrators'])
            self._validate_collector(config['collector'])
            self._validate_sensors(config['sensors'])
            self._validate_maintenance(config['maintenance'])
            
            # Validate security section if present
            if 'security' in config:
                self._validate_security(config['security'])
        
        return self.errors

    def _validate_version(self, version: str) -> None:
        """Validate version format (semver)"""
        if not re.match(r'^\d+\.\d+\.\d+$', version):
            self.errors.append(f"Invalid version format: {version}")

    def _validate_metadata(self, metadata: Dict[str, Any]) -> None:
        """Validate metadata section"""
        required = ['name', 'location']
        self._check_required_fields(metadata, required)
        
        if 'location' in metadata:
            loc = metadata['location']
            self._check_required_fields(loc, ['address', 'latitude', 'longitude', 'timezone'])
            
            # Validate coordinates
            if 'latitude' in loc:
                try:
                    lat = float(loc['latitude'])
                    if not -90 <= lat <= 90:
                        self.errors.append(f"Invalid latitude: {lat}")
                except (ValueError, TypeError):
                    self.errors.append("Latitude must be a number")
            
            if 'longitude' in loc:
                try:
                    lon = float(loc['longitude'])
                    if not -180 <= lon <= 180:
                        self.errors.append(f"Invalid longitude: {lon}")
                except (ValueError, TypeError):
                    self.errors.append("Longitude must be a number")
            
            # Validate timezone
            if 'timezone' in loc:
                try:
                    pytz.timezone(loc['timezone'])
                except pytz.exceptions.UnknownTimeZoneError:
                    self.errors.append(f"Invalid timezone: {loc['timezone']}")

    def _validate_network(self, network: Dict[str, Any]) -> None:
        """Validate network configuration"""
        if 'primary' not in network:
            self.errors.append("Missing primary network type")
            return
        
        if network['primary'] not in ['wifi', 'lan']:
            self.errors.append(f"Invalid network type: {network['primary']}")
        
        if network['primary'] == 'wifi':
            if 'wifi' not in network or not network['wifi']:
                self.errors.append("WiFi configuration missing")
            else:
                for idx, wifi in enumerate(network['wifi']):
                    if 'ssid' not in wifi:
                        self.errors.append(f"WiFi #{idx+1}: Missing SSID")
                    if 'password' not in wifi:
                        self.errors.append(f"WiFi #{idx+1}: Missing password")
                    if 'priority' in wifi:
                        try:
                            if int(wifi['priority']) < 1:
                                self.errors.append(f"WiFi #{idx+1}: Priority must be >= 1")
                        except (ValueError, TypeError):
                            self.errors.append(f"WiFi #{idx+1}: Invalid priority")
        
        elif network['primary'] == 'lan':
            if 'lan' not in network:
                self.errors.append("LAN configuration missing")
            else:
                lan = network['lan']
                if 'dhcp' not in lan:
                    self.errors.append("Missing DHCP configuration")
                if not lan.get('dhcp', True):
                    static = lan.get('static', {})
                    if 'ip' in static:
                        self._validate_ip(static['ip'], "Static IP")
                    else:
                        self.errors.append("Static IP configuration missing")
                    if 'gateway' in static:
                        self._validate_ip(static['gateway'], "Gateway")
                    else:
                        self.errors.append("Gateway configuration missing")

    def _validate_administrators(self, admins: List[Dict[str, Any]]) -> None:
        """Validate administrator configurations"""
        if not admins:
            self.errors.append("At least one administrator required")
            return
        
        for idx, admin in enumerate(admins):
            required = ['name', 'email', 'username', 'role']
            prefix = f"Administrator #{idx+1}"
            
            self._check_required_fields(admin, required, prefix)
            
            if 'email' in admin:
                if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', admin['email']):
                    self.errors.append(f"{prefix}: Invalid email format")
            
            if 'username' in admin:
                if not re.match(r'^[\w_-]+$', admin['username']):
                    self.errors.append(f"{prefix}: Invalid username format")
            
            if 'role' in admin:
                if admin['role'] not in ['hive_admin', 'hive_viewer']:
                    self.errors.append(f"{prefix}: Invalid role")

    def _validate_collector(self, collector: Dict[str, Any]) -> None:
        """Validate collector configuration"""
        required = ['interval', 'batch_size', 'retry_attempts']
        self._check_required_fields(collector, required)
        
        for field, min_val in [
            ('interval', 1),
            ('batch_size', 1),
            ('retry_attempts', 0),
            ('retry_delay', 0),
            ('buffer_size', 1)
        ]:
            if field in collector:
                try:
                    val = int(collector[field])
                    if val < min_val:
                        self.errors.append(f"Collector {field} must be >= {min_val}")
                except (ValueError, TypeError):
                    self.errors.append(f"Invalid collector {field}")

    def _validate_sensors(self, sensors: List[Dict[str, Any]]) -> None:
        """Validate sensor configurations"""
        sensor_ids = set()
        
        for idx, sensor in enumerate(sensors):
            prefix = f"Sensor #{idx+1}"
            required = ['id', 'type', 'name', 'interface']
            self._check_required_fields(sensor, required, prefix)
            
            if 'id' in sensor:
                if sensor['id'] in sensor_ids:
                    self.errors.append(f"{prefix}: Duplicate sensor ID")
                elif not re.match(r'^[\w_-]+$', sensor['id']):
                    self.errors.append(f"{prefix}: Invalid sensor ID format")
                else:
                    sensor_ids.add(sensor['id'])
            
            if 'interface' in sensor:
                self._validate_sensor_interface(sensor['interface'], prefix)
            
            if 'alerts' in sensor:
                for alert_idx, alert in enumerate(sensor['alerts']):
                    self._validate_sensor_alert(alert, f"{prefix} Alert #{alert_idx+1}")

    def _validate_sensor_interface(self, interface: Dict[str, Any], prefix: str) -> None:
        """Validate sensor interface configuration"""
        if 'type' not in interface:
            self.errors.append(f"{prefix}: Missing interface type")
            return
        
        if interface['type'] not in ['gpio', 'i2c', 'spi']:
            self.errors.append(f"{prefix}: Invalid interface type")
        
        if interface['type'] == 'gpio':
            if 'pin' not in interface:
                self.errors.append(f"{prefix}: Missing GPIO pin number")
            elif not isinstance(interface['pin'], int) or interface['pin'] < 0:
                self.errors.append(f"{prefix}: Invalid GPIO pin number")

    def _validate_sensor_alert(self, alert: Dict[str, Any], prefix: str) -> None:
        """Validate sensor alert configuration"""
        if 'metric' not in alert:
            self.errors.append(f"{prefix}: Missing alert metric")
        
        if 'min' in alert and 'max' in alert:
            try:
                if float(alert['min']) >= float(alert['max']):
                    self.errors.append(f"{prefix}: Min value must be less than max")
            except (ValueError, TypeError):
                self.errors.append(f"{prefix}: Invalid min/max values")

    def _validate_maintenance(self, maintenance: Dict[str, Any]) -> None:
        """Validate maintenance configuration"""
        for section in ['backup', 'updates', 'monitoring']:
            if section not in maintenance:
                self.errors.append(f"Missing maintenance.{section} configuration")

    def _validate_security(self, security: Dict[str, Any]) -> None:
        """
        Validate security configuration.
        
        Args:
            security: Security configuration dictionary
        """
        # Check for required security sections
        sections = ['wireguard', 'database', 'ssh', 'local_access']
        for section in sections:
            if section not in security:
                self.errors.append(f"Missing security.{section} configuration")
        
        # Validate WireGuard configuration if present
        if 'wireguard' in security:
            wireguard = security['wireguard']
            required_wg = ['private_key', 'public_key']
            for field in required_wg:
                if field not in wireguard:
                    self.errors.append(f"Missing security.wireguard.{field}")
            
            if 'client_ip' in wireguard:
                # Check if client_ip contains a valid IP/CIDR
                if not self._is_valid_cidr(wireguard['client_ip']):
                    self.errors.append(f"Invalid client IP: {wireguard['client_ip']}")
        
        # Validate database configuration if present
        if 'database' in security:
            db = security['database']
            required_db = ['username', 'password']
            for field in required_db:
                if field not in db:
                    self.errors.append(f"Missing security.database.{field}")
        
        # Validate SSH configuration if present
        if 'ssh' in security:
            ssh = security['ssh']
            if 'public_key' not in ssh:
                self.errors.append("Missing SSH public key")
            
            if 'port' in ssh:
                try:
                    port = int(ssh['port'])
                    if not 1 <= port <= 65535:
                        self.errors.append(f"Invalid SSH port: {port}")
                except (ValueError, TypeError):
                    self.errors.append(f"Invalid SSH port: {ssh['port']}")
        
        # Validate local access configuration if present
        if 'local_access' in security:
            local = security['local_access']
            required_local = ['username', 'password']
            for field in required_local:
                if field not in local:
                    self.errors.append(f"Missing security.local_access.{field}")

    def _is_valid_cidr(self, cidr: str) -> bool:
        """
        Check if a string is a valid CIDR notation.
        
        Args:
            cidr: String to check (e.g., '10.10.0.1/32')
            
        Returns:
            True if valid, False otherwise
        """
        try:
            import ipaddress
            ipaddress.ip_network(cidr, strict=False)
            return True
        except ValueError:
            return False

    def _check_required_fields(self, data: Dict[str, Any], 
                             fields: List[str], prefix: str = "") -> None:
        """Check presence of required fields"""
        for field in fields:
            if field not in data:
                self.errors.append(f"{prefix + ': ' if prefix else ''}Missing {field}")

    def _validate_ip(self, ip: str, prefix: str = "IP") -> None:
        """Validate IP address format"""
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            self.errors.append(f"Invalid {prefix} address: {ip}")
            
    def _validate_hive_id(self, hive_id: str) -> None:
        if not is_valid_hive_id(hive_id):
            self.errors.append(f"Invalid hive ID format: {hive_id}")

    def _validate_sensor_id(self, sensor_id: str, prefix: str) -> None:
        if not is_valid_sensor_id(sensor_id):
            self.errors.append(f"{prefix}: Invalid sensor ID format: {sensor_id}")