# hive_config_manager/core/schemas.py

from typing import List, Dict, Optional, Union, Any
from dataclasses import dataclass
from datetime import datetime
import re

@dataclass
class NetworkWifi:
    ssid: str
    password: str
    priority: int = 1

    def validate(self) -> List[str]:
        errors = []
        if not self.ssid:
            errors.append("WiFi SSID cannot be empty")
        if not self.password:
            errors.append("WiFi password cannot be empty")
        if self.priority < 1:
            errors.append("WiFi priority must be >= 1")
        return errors

@dataclass
class NetworkLAN:
    dhcp: bool = True
    static_ip: Optional[str] = None
    gateway: Optional[str] = None
    dns: List[str] = None

    def validate(self) -> List[str]:
        errors = []
        if not self.dhcp and not all([self.static_ip, self.gateway]):
            errors.append("Static IP configuration requires IP and gateway")
        if self.static_ip and not re.match(r'^\d{1,3}(\.\d{1,3}){3}$', self.static_ip):
            errors.append("Invalid static IP format")
        return errors

@dataclass
class Location:
    address: str
    latitude: float
    longitude: float
    timezone: str

    def validate(self) -> List[str]:
        errors = []
        if not -90 <= self.latitude <= 90:
            errors.append("Latitude must be between -90 and 90")
        if not -180 <= self.longitude <= 180:
            errors.append("Longitude must be between -180 and 180")
        # TODO: Add timezone validation against pytz
        return errors

@dataclass
class Administrator:
    name: str
    email: str
    username: str
    phone: str
    role: str

    def validate(self) -> List[str]:
        errors = []
        if not re.match(r'^[\w\s-]+$', self.name):
            errors.append("Invalid administrator name format")
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', self.email):
            errors.append("Invalid email format")
        if not re.match(r'^[\w_-]+$', self.username):
            errors.append("Invalid username format")
        if self.role not in ['hive_admin', 'hive_viewer']:
            errors.append("Invalid role")
        return errors

@dataclass
class SensorInterface:
    type: str
    pin: Optional[int] = None
    data_pin: Optional[int] = None
    clock_pin: Optional[int] = None

    def validate(self) -> List[str]:
        errors = []
        if self.type not in ['gpio', 'i2c', 'spi']:
            errors.append("Invalid interface type")
        if self.type == 'gpio' and self.pin is None:
            errors.append("GPIO interface requires pin number")
        return errors

@dataclass
class SensorCalibration:
    offset: float = 0.0
    scale: float = 1.0
    tare: Optional[int] = None
    scale_factor: Optional[float] = None

@dataclass
class SensorAlert:
    metric: str
    min: Optional[float] = None
    max: Optional[float] = None
    threshold_duration: int = 300
    rate_of_change_max: Optional[float] = None

    def validate(self) -> List[str]:
        errors = []
        if not self.metric:
            errors.append("Alert metric cannot be empty")
        if self.min is not None and self.max is not None and self.min >= self.max:
            errors.append("Alert min value must be less than max")
        if self.threshold_duration < 0:
            errors.append("Threshold duration must be positive")
        return errors

@dataclass
class Sensor:
    id: str
    type: str
    name: str
    enabled: bool = True
    location: Optional[str] = None
    interface: SensorInterface = None
    collection: Dict[str, Any] = None
    calibration: Optional[SensorCalibration] = None
    alerts: List[SensorAlert] = None

    def validate(self) -> List[str]:
        errors = []
        if not re.match(r'^[\w_-]+$', self.id):
            errors.append(f"Invalid sensor ID format: {self.id}")
        if not self.name:
            errors.append("Sensor name cannot be empty")
        if self.interface:
            errors.extend(self.interface.validate())
        if self.alerts:
            for alert in self.alerts:
                errors.extend(alert.validate())
        return errors

@dataclass
class HiveConfig:
    hive_id: str
    version: str
    metadata: Dict[str, Any]
    network: Dict[str, Any]
    administrators: List[Administrator]
    collector: Dict[str, Any]
    sensors: List[Sensor]
    maintenance: Dict[str, Any]

    def validate(self) -> List[str]:
        """Validate entire hive configuration"""
        errors = []
        
        # Validate hive_id format
        if not re.match(r'^hive_[\w-]+$', self.hive_id):
            errors.append("Invalid hive_id format")

        # Validate version
        if not re.match(r'^\d+\.\d+\.\d+$', self.version):
            errors.append("Invalid version format")

        # Validate metadata
        location = Location(**self.metadata['location'])
        errors.extend(location.validate())

        # Validate administrators
        for admin in self.administrators:
            errors.extend(admin.validate())

        # Validate sensors
        for sensor in self.sensors:
            errors.extend(sensor.validate())

        # Validate collector configuration
        if 'interval' in self.collector and self.collector['interval'] < 1:
            errors.append("Collector interval must be positive")

        return errors

def validate_yaml_config(config: Dict[str, Any]) -> List[str]:
    """Validate a YAML configuration dictionary"""
    try:
        hive_config = HiveConfig(**config)
        return hive_config.validate()
    except Exception as e:
        return [f"Configuration error: {str(e)}"]