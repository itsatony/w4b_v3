# hive_config_manager/tests/test_manager.py

import pytest
import yaml
import os
from pathlib import Path
import tempfile
import shutil
from datetime import datetime

from hive_config_manager.core.manager import HiveManager
from hive_config_manager.core.exceptions import (
    HiveConfigError,
    ValidationError,
    ConfigNotFoundError,
    DuplicateHiveError
)

@pytest.fixture
def temp_hives_dir():
    """Create a temporary directory for hive configurations"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)

@pytest.fixture
def manager(temp_hives_dir):
    """Create a HiveManager instance with temporary directory"""
    return HiveManager(temp_hives_dir)

@pytest.fixture
def valid_config():
    """Return a valid base hive configuration"""
    return {
        'version': '1.0.0',
        'metadata': {
            'name': 'Test Hive',
            'location': {
                'address': 'Test Location',
                'latitude': 48.123456,
                'longitude': 11.123456,
                'timezone': 'Europe/Berlin'
            },
            'notes': 'Test hive configuration'
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
            'interval': 60,
            'batch_size': 100,
            'retry_attempts': 3,
            'retry_delay': 5,
            'buffer_size': 1000,
            'logging': {
                'level': 'INFO',
                'max_size': '100M',
                'retention': 7
            }
        },
        'sensors': [{
            'id': 'temp_01',
            'type': 'dht22',
            'name': 'Temperature Sensor',
            'enabled': True,
            'interface': {
                'type': 'gpio',
                'pin': 4
            },
            'collection': {
                'interval': 300,
                'retries': 3
            },
            'calibration': {
                'offset': -0.5,
                'scale': 1.0
            }
        }],
        'maintenance': {
            'backup': {
                'enabled': True,
                'interval': 86400,
                'retention': 7
            },
            'updates': {
                'auto_update': True,
                'update_hour': 3,
                'allowed_days': ['Sunday']
            },
            'monitoring': {
                'metrics_retention': 30,
                'enable_detailed_logging': True
            }
        }
    }

# Basic Operations Tests
def test_create_hive(manager, valid_config):
    """Test basic hive creation with valid configuration"""
    hive_id = manager.create_hive(valid_config)
    assert hive_id.startswith('hive_')
    assert (manager.base_path / f"{hive_id}.yaml").exists()

def test_get_hive(manager, valid_config):
    """Test retrieving a hive configuration"""
    hive_id = manager.create_hive(valid_config)
    config = manager.get_hive(hive_id)
    assert config['metadata']['name'] == valid_config['metadata']['name']
    assert config['version'] == valid_config['version']

def test_update_hive(manager, valid_config):
    """Test updating an existing hive configuration"""
    hive_id = manager.create_hive(valid_config)
    updated_config = valid_config.copy()
    updated_config['metadata']['name'] = 'Updated Name'
    manager.update_hive(hive_id, updated_config)
    config = manager.get_hive(hive_id)
    assert config['metadata']['name'] == 'Updated Name'

def test_delete_hive(manager, valid_config):
    """Test deleting a hive configuration"""
    hive_id = manager.create_hive(valid_config)
    assert hive_id in manager.list_hives()
    manager.delete_hive(hive_id)
    assert hive_id not in manager.list_hives()

def test_list_hives(manager, valid_config):
    """Test listing all hive configurations"""
    # Create multiple hives
    hive_ids = []
    for i in range(3):
        config = valid_config.copy()
        config['metadata']['name'] = f'Test Hive {i}'
        hive_id = manager.create_hive(config)
        hive_ids.append(hive_id)
    
    listed_hives = manager.list_hives()
    assert len(listed_hives) == 3
    assert all(hive_id in listed_hives for hive_id in hive_ids)

# Validation Tests
def test_create_hive_with_invalid_config(manager):
    """Test creation with invalid configuration"""
    invalid_config = {'invalid': 'config'}
    with pytest.raises(ValidationError):
        manager.create_hive(invalid_config)

def test_create_hive_with_invalid_network(manager, valid_config):
    """Test creation with invalid network configuration"""
    config = valid_config.copy()
    config['network'] = {'primary': 'invalid'}
    with pytest.raises(ValidationError):
        manager.create_hive(config)

def test_create_hive_with_invalid_coordinates(manager, valid_config):
    """Test creation with invalid coordinates"""
    config = valid_config.copy()
    config['metadata']['location']['latitude'] = 91  # Invalid latitude
    with pytest.raises(ValidationError):
        manager.create_hive(config)

def test_create_hive_with_invalid_sensor(manager, valid_config):
    """Test creation with invalid sensor configuration"""
    config = valid_config.copy()
    config['sensors'][0]['interface']['type'] = 'invalid'
    with pytest.raises(ValidationError):
        manager.create_hive(config)

# Edge Cases Tests
def test_get_nonexistent_hive(manager):
    """Test attempting to retrieve non-existent hive"""
    with pytest.raises(ConfigNotFoundError) as exc_info:
        manager.get_hive('nonexistent')
    assert str(exc_info.value) == "Configuration not found for hive: nonexistent"

def test_update_nonexistent_hive(manager, valid_config):
    """Test attempting to update non-existent hive"""
    with pytest.raises(ConfigNotFoundError):
        manager.update_hive('nonexistent', valid_config)

def test_delete_nonexistent_hive(manager):
    """Test attempting to delete non-existent hive"""
    with pytest.raises(ConfigNotFoundError) as exc_info:
        manager.delete_hive('nonexistent')
    assert str(exc_info.value) == "Configuration not found for hive: nonexistent"

def test_create_duplicate_hive(manager, valid_config):
    """Test creating hive with duplicate ID"""
    hive_id = manager.create_hive(valid_config)
    config = valid_config.copy()
    config['hive_id'] = hive_id
    with pytest.raises(DuplicateHiveError):
        manager.create_hive(config)

# Backup Tests
def test_backup_creation(manager, valid_config):
    """Test backup creation during updates"""
    hive_id = manager.create_hive(valid_config)
    
    # Update to trigger backup
    updated_config = valid_config.copy()
    updated_config['metadata']['name'] = 'Updated Name'
    manager.update_hive(hive_id, updated_config)
    
    backup_dir = manager.base_path / "backups"
    assert backup_dir.exists()
    backups = list(backup_dir.glob(f"{hive_id}_*.yaml"))
    assert len(backups) > 0

def test_backup_content(manager, valid_config):
    """Test backup content matches original"""
    hive_id = manager.create_hive(valid_config)
    
    # Get original content
    original_path = manager.base_path / f"{hive_id}.yaml"
    with open(original_path) as f:
        original_content = yaml.safe_load(f)
    
    # Update to trigger backup
    updated_config = valid_config.copy()
    updated_config['metadata']['name'] = 'Updated Name'
    manager.update_hive(hive_id, updated_config)
    
    # Check backup content
    backup_dir = manager.base_path / "backups"
    backups = list(backup_dir.glob(f"{hive_id}_*.yaml"))
    with open(backups[0]) as f:
        backup_content = yaml.safe_load(f)
    
    assert backup_content['metadata']['name'] == original_content['metadata']['name']

# File Operation Tests
def test_file_permissions(manager, valid_config):
    """Test configuration file permissions"""
    hive_id = manager.create_hive(valid_config)
    config_path = manager.base_path / f"{hive_id}.yaml"
    
    # Check file exists
    assert config_path.exists()
    
    # Get file permissions
    permissions = oct(config_path.stat().st_mode)[-3:]
    
    # Platform-specific checks
    if os.name == 'posix':  # Linux/Unix
        assert permissions in ('600', '640', '644', '664')
    else:  # Windows doesn't have the same permission model
        assert config_path.exists()

def test_atomic_updates(manager, valid_config):
    """Test atomic nature of configuration updates"""
    hive_id = manager.create_hive(valid_config)
    original_config = manager.get_hive(hive_id)
    
    # Simulate failed update
    try:
        invalid_config = valid_config.copy()
        invalid_config['metadata'] = {'name': None}  # Invalid but won't cause TypeError
        manager.update_hive(hive_id, invalid_config)
    except ValidationError:
        pass
    
    # Check config remains unchanged
    current_config = manager.get_hive(hive_id)
    assert current_config == original_config

# Performance Tests
@pytest.mark.slow
def test_large_configuration(manager, valid_config):
    """Test handling of large configuration with many sensors"""
    large_config = valid_config.copy()
    base_sensor = valid_config['sensors'][0].copy()
    
    # Add 100 sensors
    large_config['sensors'] = []
    for i in range(100):
        sensor = base_sensor.copy()
        sensor.update({
            'id': f'sensor_{i:03d}',
            'name': f'Sensor {i}',
            'interface': {
                'type': 'gpio',
                'pin': i + 1
            }
        })
        large_config['sensors'].append(sensor)
    
    hive_id = manager.create_hive(large_config)
    retrieved_config = manager.get_hive(hive_id)
    assert len(retrieved_config['sensors']) == 100

@pytest.mark.slow
def test_concurrent_operations(manager, valid_config):
    """Test concurrent operations on configurations"""
    import threading
    import queue
    
    errors = queue.Queue()
    configs_created = queue.Queue()
    
    def create_hive(index):
        try:
            config = valid_config.copy()
            config['metadata']['name'] = f'Test Hive {index}'
            hive_id = manager.create_hive(config)
            configs_created.put(hive_id)
        except Exception as e:
            errors.put(e)
    
    threads = [threading.Thread(target=create_hive, args=(i,)) 
              for i in range(10)]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # Check for errors
    if not errors.empty():
        raise errors.get()
    
    # Verify created configs
    created_configs = []
    while not configs_created.empty():
        created_configs.append(configs_created.get())
    
    assert len(created_configs) == 10
    assert len(manager.list_hives()) == 10