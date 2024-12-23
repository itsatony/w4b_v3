# hive_config_manager/cli/prompts.py

import yaml
from typing import Dict, Any, List
import inquirer
from prompt_toolkit.shortcuts import message_dialog, yes_no_dialog
from prompt_toolkit.formatted_text import HTML
from ..utils.id_generator import generate_sensor_id

class HivePrompts:
    """
    User interaction prompts for the Hive Configuration Manager.
    
    Provides methods for gathering user input and displaying formatted output
    for various hive configuration operations.
    """

    def get_new_hive_config(self) -> Dict[str, Any]:
        """
        Interactive prompt sequence for creating a new hive configuration.
        
        Returns:
            Dict containing the new hive configuration
        """
        print("\n=== Creating New Hive Configuration ===\n")
        
        # Basic Information
        basic_info = inquirer.prompt([
            inquirer.Text('name',
                message="Hive name",
                validate=lambda _, x: bool(x.strip())),
            inquirer.Text('location',
                message="Physical location",
                validate=lambda _, x: bool(x.strip())),
            inquirer.Text('latitude',
                message="Latitude (e.g., 48.123456)",
                validate=self._validate_latitude),
            inquirer.Text('longitude',
                message="Longitude (e.g., 11.123456)",
                validate=self._validate_longitude),
            inquirer.List('timezone',
                message="Timezone",
                choices=self._get_common_timezones()),
            inquirer.Text('notes',
                message="Notes (optional)")
        ])

        # Network Configuration
        network = self._get_network_config()

        # Administrator Configuration
        administrators = self._get_administrators()

        # Sensor Configuration
        sensors = self._get_sensor_config()

        # Build complete configuration
        config = {
            'version': '1.0.0',
            'metadata': {
                'name': basic_info['name'],
                'location': {
                    'address': basic_info['location'],
                    'latitude': float(basic_info['latitude']),
                    'longitude': float(basic_info['longitude']),
                    'timezone': basic_info['timezone']
                },
                'notes': basic_info['notes']
            },
            'network': network,
            'administrators': administrators,
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
            'sensors': sensors,
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

        return config

    def _get_network_config(self) -> Dict[str, Any]:
        """Gather network configuration details"""
        network_type = inquirer.prompt([
            inquirer.List('type',
                message="Primary network connection",
                choices=['wifi', 'lan'])
        ])

        config = {'primary': network_type['type']}

        if network_type['type'] == 'wifi':
            networks = []
            while True:
                add_network = inquirer.prompt([
                    inquirer.Confirm('add',
                        message="Add WiFi network?",
                        default=True)
                ])
                if not add_network['add']:
                    break

                wifi = inquirer.prompt([
                    inquirer.Text('ssid',
                        message="WiFi SSID",
                        validate=lambda _, x: bool(x.strip())),
                    inquirer.Password('password',
                        message="WiFi password"),
                    inquirer.Text('priority',
                        message="Priority (1=highest)",
                        default="1",
                        validate=lambda _, x: x.isdigit() and int(x) > 0)
                ])
                networks.append({
                    'ssid': wifi['ssid'],
                    'password': wifi['password'],
                    'priority': int(wifi['priority'])
                })
            config['wifi'] = networks
        else:
            use_dhcp = inquirer.prompt([
                inquirer.Confirm('dhcp',
                    message="Use DHCP?",
                    default=True)
            ])
            config['lan'] = {'dhcp': use_dhcp['dhcp']}
            
            if not use_dhcp['dhcp']:
                static = inquirer.prompt([
                    inquirer.Text('ip',
                        message="Static IP address",
                        validate=self._validate_ip),
                    inquirer.Text('gateway',
                        message="Gateway address",
                        validate=self._validate_ip),
                    inquirer.Text('dns',
                        message="DNS servers (comma-separated)",
                        validate=self._validate_dns_list)
                ])
                config['lan']['static'] = {
                    'ip': static['ip'],
                    'gateway': static['gateway'],
                    'dns': [x.strip() for x in static['dns'].split(',')]
                }

        return config

    def _get_administrators(self) -> List[Dict[str, str]]:
        """Gather administrator information"""
        admins = []
        while True:
            add_admin = inquirer.prompt([
                inquirer.Confirm('add',
                    message="Add administrator?",
                    default=True if not admins else False)
            ])
            if not add_admin['add']:
                break

            admin = inquirer.prompt([
                inquirer.Text('name',
                    message="Administrator name",
                    validate=lambda _, x: bool(x.strip())),
                inquirer.Text('email',
                    message="Email address",
                    validate=self._validate_email),
                inquirer.Text('username',
                    message="Username",
                    validate=lambda _, x: bool(x.strip()) and ' ' not in x),
                inquirer.Text('phone',
                    message="Phone number"),
                inquirer.List('role',
                    message="Role",
                    choices=['hive_admin', 'hive_viewer'])
            ])
            admins.append(admin)

        return admins

    def _get_sensor_config(self) -> List[Dict[str, Any]]:
        """Gather sensor configuration"""
        sensors = []
        sensor_counts = {}
        while True:
            add_sensor = inquirer.prompt([
                inquirer.Confirm('add',
                    message="Add sensor?",
                    default=True if not sensors else False)
            ])
            if not add_sensor['add']:
                break

            sensor = inquirer.prompt([
                inquirer.Text('id',
                    message="Sensor ID",
                    validate=lambda _, x: bool(x.strip()) and ' ' not in x),
                inquirer.List('type',
                    message="Sensor type",
                    choices=['dht22', 'hx711', 'ds18b20']),
                inquirer.Text('name',
                    message="Sensor name",
                    validate=lambda _, x: bool(x.strip())),
                inquirer.Text('location',
                    message="Sensor location",
                    validate=lambda _, x: bool(x.strip())),
                inquirer.List('interface_type',
                    message="Interface type",
                    choices=['gpio', 'i2c', 'spi'])
            ])

            # Interface-specific configuration
            interface = {'type': sensor['interface_type']}
            if sensor['interface_type'] == 'gpio':
                gpio = inquirer.prompt([
                    inquirer.Text('pin',
                        message="GPIO pin number",
                        validate=lambda _, x: x.isdigit())
                ])
                interface['pin'] = int(gpio['pin'])

            sensor_config = {
                'id': sensor['id'],
                'type': sensor['type'],
                'name': sensor['name'],
                'location': sensor['location'],
                'enabled': True,
                'interface': interface
            }
            sensors.append(sensor_config)
            sensor_type = sensor['type']
            if sensor_type not in sensor_counts:
                sensor_counts[sensor_type] = 0
            sensor_counts[sensor_type] += 1
            
            # Generate sensor ID if not provided
            if not sensor.get('id'):
                sensor['id'] = generate_sensor_id(
                    sensor_type, 
                    sensor_counts[sensor_type]
                )

        return sensors

    def format_config(self, config: Dict[str, Any]) -> str:
        """Format configuration for display"""
        return yaml.dump(config, sort_keys=False, allow_unicode=True)

    def confirm_deletion(self, hive_id: str) -> bool:
        """Confirm hive deletion"""
        return yes_no_dialog(
            title="Confirm Deletion",
            text=f"Are you sure you want to delete hive {hive_id}?"
        ).run()

    def show_validation_results(self, errors: List[str]) -> None:
        """Display validation results"""
        if errors:
            message = "\n".join([f"• {error}" for error in errors])
            message_dialog(
                title="Validation Errors",
                text=HTML(f'<style fg="red">{message}</style>')
            ).run()
        else:
            message_dialog(
                title="Validation Success",
                text=HTML('<style fg="green">Configuration is valid</style>')
            ).run()

    # Validation helpers
    def _validate_latitude(self, _, x: str) -> bool:
        try:
            lat = float(x)
            return -90 <= lat <= 90
        except ValueError:
            return False

    def _validate_longitude(self, _, x: str) -> bool:
        try:
            lon = float(x)
            return -180 <= lon <= 180
        except ValueError:
            return False

    def _validate_ip(self, _, x: str) -> bool:
        parts = x.split('.')
        return (len(parts) == 4 and
                all(p.isdigit() and 0 <= int(p) <= 255 for p in parts))

    def _validate_dns_list(self, _, x: str) -> bool:
        return all(self._validate_ip(_, ip.strip())
                  for ip in x.split(','))

    def _validate_email(self, _, x: str) -> bool:
        import re
        pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        return bool(re.match(pattern, x))

    def _get_common_timezones(self) -> List[str]:
        """Return list of common timezones"""
        return [
            'UTC',
            'Europe/Berlin',
            'Europe/London',
            'Europe/Paris',
            'Europe/Rome',
            'Europe/Madrid'
        ]