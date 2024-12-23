# hive_config_manager/tests/test_manager.py

import pytest
from pathlib import Path
import yaml
import tempfile
import shutil
from ..core.manager import HiveManager
from ..core.exceptions import HiveConfigError

@pytest.fixture
def temp_hives_dir():
    """Create a temporary directory for hive configurations"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)

@pytest.fixture
def valid_config():
    """Return a valid hive configuration"""
    return {
        'hive_id': 'hive_test123',
        'version': '1.0.0',
        'metadata': {
            'name': 'Test Hive',
            'location': {
                'address': 'Test Location',
                'latitude': 48.123456,
                'longitude': 11.123456,
                'timezone': 'Europe/Berlin'
            }
        },
        'network': {
            'primary': 'wifi',
            'wifi': [{
                'ssid': 'TestNetwork',
                'password': 'testpass',
                'priority': 1
            }]
        },
        'administrators': [{
            'name': 'Test Admin',
            'email': 'test@example.com',
            'username': 'testadmin',
            'phone': '+1234567890',
            'role': 'hive_admin'
        }],
        'collector': {
            'interval': 60
        },
        'sensors': [{
            'id': 'temp_01',
            'type': 'dht22',
            'name': 'Temperature Sensor',
            'enabled': True,
            'interface': {
                'type': 'gpio',
                'pin': 4
            }
        }],
        'maintenance': {
            'backup': {
                'enabled': True,
                'interval': 86400
            }
        }
    }

@pytest.fixture
def manager(temp_hives_dir):
    """Create a HiveManager instance with temporary directory"""
    return HiveManager(temp_hives_dir)

def test_create_hive(manager, valid_config):
    """Test creating a new hive configuration"""
    hive_id = manager.create_hive(valid_config)
    assert hive_id == valid_config['hive_id']
    assert (manager.base_path / f"{hive_id}.yaml").exists()

def test_create_hive_invalid_config(manager):
    """Test creating a hive with invalid configuration"""
    invalid_config = {'invalid': 'config'}
    with pytest.raises(HiveConfigError):
        manager.create_hive(invalid_config)

def test_get_hive(manager, valid_config):
    """Test retrieving a hive configuration"""
    hive_id = manager.create_hive(valid_config)
    config = manager.get_hive(hive_id)
    assert config == valid_config

def test_get_nonexistent_hive(manager):
    """Test retrieving a non-existent hive"""
    with pytest.raises(HiveConfigError):
        manager.get_hive('nonexistent')

def test_update_hive(manager, valid_config):
    """Test updating a hive configuration"""
    hive_id = manager.create_hive(valid_config)
    
    # Modify configuration
    updated_config = valid_config.copy()
    updated_config['metadata']['name'] = 'Updated Name'
    
    manager.update_hive(hive_id, updated_config)
    retrieved_config = manager.get_hive(hive_id)
    assert retrieved_config['metadata']['name'] == 'Updated Name'

def test_delete_hive(manager, valid_config):
    """Test deleting a hive configuration"""
    hive_id = manager.create_hive(valid_config)
    assert hive_id in manager.list_hives()
    
    manager.delete_hive(hive_id)
    assert hive_id not in manager.list_hives()

def test_validate_hive(manager, valid_config):
    """Test hive configuration validation"""
    hive_id = manager.create_hive(valid_config)
    errors = manager.validate_hive(hive_id)
    assert len(errors) == 0

def test_backup_creation(manager, valid_config):
    """Test backup creation during updates"""
    hive_id = manager.create_hive(valid_config)
    
    # Update configuration to trigger backup
    updated_config = valid_config.copy()
    updated_config['metadata']['name'] = 'Updated Name'
    manager.update_hive(hive_id, updated_config)
    
    # Check if backup was created
    backup_dir = manager.base_path / "backups"
    assert backup_dir.exists()
    assert len(list(backup_dir.glob(f"{hive_id}_*.yaml"))) > 0

# hive_config_manager/tests/test_validator.py

import pytest
from ..core.schemas import (
    NetworkWifi,
    NetworkLAN,
    Location,
    Administrator,
    SensorInterface,
    SensorAlert,
    Sensor,
    validate_yaml_config
)

def test_network_wifi_validation():
    """Test WiFi configuration validation"""
    # Valid configuration
    wifi = NetworkWifi(ssid="TestNetwork", password="testpass", priority=1)
    assert len(wifi.validate()) == 0
    
    # Invalid configuration
    wifi = NetworkWifi(ssid="", password="", priority=0)
    errors = wifi.validate()
    assert len(errors) == 3
    assert "SSID cannot be empty" in errors[0]

def test_location_validation():
    """Test location validation"""
    # Valid configuration
    loc = Location(
        address="Test Address",
        latitude=48.123456,
        longitude=11.123456,
        timezone="Europe/Berlin"
    )
    assert len(loc.validate()) == 0
    
    # Invalid configuration
    loc = Location(
        address="Test Address",
        latitude=91,
        longitude=181,
        timezone="Invalid/Zone"
    )
    errors = loc.validate()
    assert len(errors) == 2
    assert "Latitude must be between" in errors[0]

def test_administrator_validation():
    """Test administrator validation"""
    # Valid configuration
    admin = Administrator(
        name="Test Admin",
        email="test@example.com",
        username="testadmin",
        phone="+1234567890",
        role="hive_admin"
    )
    assert len(admin.validate()) == 0
    
    # Invalid configuration
    admin = Administrator(
        name="Test@Admin",
        email="invalid-email",
        username="test admin",
        phone="+1234567890",
        role="invalid_role"
    )
    errors = admin.validate()
    assert len(errors) > 0

def test_sensor_validation():
    """Test sensor configuration validation"""
    # Valid configuration
    sensor = Sensor(
        id="temp_01",
        type="dht22",
        name="Temperature Sensor",
        interface=SensorInterface(type="gpio", pin=4),
        alerts=[
            SensorAlert(
                metric="temperature",
                min=10,
                max=40
            )
        ]
    )
    assert len(sensor.validate()) == 0
    
    # Invalid configuration
    sensor = Sensor(
        id="invalid@id",
        type="",
        name="",
        interface=SensorInterface(type="invalid"),
        alerts=[
            SensorAlert(
                metric="",
                min=40,
                max=10
            )
        ]
    )
    errors = sensor.validate()
    assert len(errors) > 0