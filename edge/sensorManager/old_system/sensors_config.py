from ast import literal_eval
from subprocess import run
from typing import Dict


class SensorsConfig():
    def __init__(self, sensors: Dict[str, str] = {}, offset: int = 0, scale: float = 0.0, altitude: str = None,
                 frequency: int = 1):
        self.PATH = '/home/pi/sensors.dat'
        self.SENSORS_TEMPLATE = [
            '(\'WindSensor\', {{\'bus_address\': 0x4, \'sensor_name\': \'_outdoor\', \'size\': 16, \'data\': 64, ' +
            '\'type_name\': \'wind\', \'value_name\': \'speed\', \'diameter\': 0.28}}, {})',
            '(\'I2CSensor\', {{\'bus_address\': 0x4, \'sensor_name\': \'_outdoor\', \'size\': 16, \'data\': 65, ' +
            '\'type_name\': \'rain\', \'value_name\': \'rain\'}}, {})',
            '(\'PhotoSensor\', {{\'bus_address\': 0x29, \'integration_time\': 100, \'gain\': \'low\', ' +
            '\'sensor_name\': \'_outdoor\'}}, {})',
            '(\'HumiditySensor\', {{\'bus_address\': 0x40, \'sensor_name\': \'_indoor\'}}, {})'
        ]
        self.PRESSURE_SENSOR_TEMPLATE = '(\'PressureSensor\', {{\'bus_address\': 0x76, \'altitude\': {}, ' + \
                                        '\'sensor_name\': \'_outdoor\'}}, {})'
        self.SENSORS_TEMPLATE_FIXED = [
            '(\'I2CSensor\', {\'bus_address\': 0x4, \'sensor_name\': \'_outdoor\', \'size\': 16, \'data\': 61, ' +
            '\'type_name\': \'finedust\', \'value_name\': \'pm2_5\'}, 180)',
            '(\'I2CSensor\', {\'bus_address\': 0x4, \'sensor_name\': \'_outdoor\', \'size\': 16, \'data\': 62, ' +
            '\'type_name\': \'finedust\', \'value_name\': \'pm10\'}, 180)']
        self.BALANCE_SENSOR = '(\'BalanceSensor\', {{\'bus_address\': 0x4, \'sensor_name\': \'_outdoor\', \'size\': 16, ' + \
                              '\'data\': 63, \'type_name\': \'balance\', \'value_name\': \'weight\', \'offset\': {},' + \
                              '\'factor\': {}}}, {})'
        self.W1_TEMPERATURE_SENSOR = '(\'TemperatureW1Sensor\', {{\'bus_path\': \'/sys/bus/w1/devices/{}/w1_slave\', ' + \
                                     '\'sensor_name\': \'_indoor_{}\'}}, {})'
        self.sensors = sensors
        self.offset = offset
        self.scale = scale
        self.altitude = altitude
        self.frequency = frequency

    def set_altitude(self, m_altitude):
        self.altitude = m_altitude

    def set_offset(self, m_offset):
        self.offset = m_offset

    def set_scale(self, m_scale):
        self.scale = m_scale

    def set_sensors(self, mappings):
        self.sensors = mappings

    def get_altitude(self):
        return self.altitude

    def get_offset(self):
        return self.offset

    def get_scale(self):
        return self.scale

    def get_sensors(self):
        return self.sensors

    def read(self, file_path: str = None):
        if file_path is None:
            file_path = self.PATH

        sensors_config = []
        with open(file_path, 'r') as f:
            for line in f:
                if line[0] == '#':
                    continue
                tmp = literal_eval(line)
                sensor_config = {
                    'sensor_type': tmp[0],
                    'values': tmp[1],
                    'additional_params': None
                }
                if len(tmp) > 2:
                    sensor_config['additional_params'] = tmp[2]

                sensors_config.append(sensor_config)
        return sensors_config

    def load(self):
        conf = self.read()
        balance_conf = [v for i, v in enumerate(conf) if v['sensor_type'] == 'BalanceSensor'][0]['values']
        pressure_conf = [v for i, v in enumerate(conf) if v['sensor_type'] == 'PressureSensor'][0]['values']

        self.offset = balance_conf['offset']
        self.scale = balance_conf['factor']
        self.altitude = pressure_conf['altitude']
        self.sensors = {}
        temperature_conf = [v for i, v in enumerate(conf) if v['sensor_type'] == 'TemperatureW1Sensor']
        for temp in temperature_conf:
            temp_pos = temp['values']['sensor_name'].replace('_indoor_', '')
            temp_address = temp['values']['bus_path'].replace('/sys/bus/w1/devices/', '').replace('/w1_slave', '')
            self.sensors[temp_address] = temp_pos

    def write(self):
        with open(self.PATH, 'w') as f:
            for line in self.SENSORS_TEMPLATE:
                f.write(line.format(self.frequency))
                f.write('\n')
            for line in self.SENSORS_TEMPLATE_FIXED:
                f.write(line)
                f.write('\n')
            f.write(self.BALANCE_SENSOR.format(self.offset, self.scale, self.frequency))
            f.write('\n')
            f.write(self.PRESSURE_SENSOR_TEMPLATE.format(self.altitude, self.frequency))
            f.write('\n')
            for sensor, name in self.sensors.items():
                f.write(self.W1_TEMPERATURE_SENSOR.format(sensor, name, self.frequency))
                f.write('\n')
            f.flush()
        self.__upload_config()

    @staticmethod
    def __upload_config() -> None:
        run(['python3', '/home/pi/code-we4bee-sensor_network/upload_config.py'])
