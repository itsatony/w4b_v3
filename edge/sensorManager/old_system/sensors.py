import json

from core.config.sensors_config import SensorsConfig


class Sensors():
    LOG_FOLDER = '/var/log/we4bee/'
    SENSORS = [
        'balance_outdoor',
        'humidity_indoor',
        'humidity_outdoor',
        'photo_outdoor',
        'pressure_outdoor',
        'rain_outdoor',
        'temperature_indoor_left',
        'temperature_indoor',
        'temperature_indoor_middle',
        'temperature_indoor_right',
        'temperature_outdoor',
        'wind_outdoor'
    ]

    def get_snapshot(self):
        measurements = []

        for sensor_name in self.SENSORS:
            measurement = self.get_snapshot_sensor(sensor_name)
            if measurement != None:
                measurements.append(measurement)

        measurement = self.get_snapshot_sensor('finedust_outdoor', 'pm10')
        if measurement != None:
            measurements.append(measurement)

        measurement = self.get_snapshot_sensor('finedust_outdoor', 'pm2_5')
        if measurement != None:
            measurements.append(measurement)

        return measurements

    def get_snapshot_sensor(self, name, filter=None):
        try:
            with open(self.LOG_FOLDER + name + '.log', "rb") as f:
                lines = f.readlines()
                if lines:
                    if filter != None:
                        lines = [line for line in lines if filter in line.decode("utf-8")]

                    last_line = lines[-1].decode("utf-8").strip(' \t\n\r')
                    json_str = "-".join(last_line.split("-")[1:]).strip(' \t\n\r"').replace("'", "\"").replace("\n", "")
                    json_values = json.loads(json_str)

                    if ('temperature_' in name):
                        short_name = name.replace('temperature', '')
                        bus_address = None

                        sensor_config = SensorsConfig()
                        sensor_conf = sensor_config.read()

                        for sensor in sensor_conf:
                            if sensor['sensor_type'] == 'TemperatureW1Sensor':
                                sensor_values = sensor['values']
                                sensor_name = sensor_values['sensor_name']
                                sensor_address = sensor_values['bus_path'].replace('/sys/bus/w1/devices/', '') \
                                    .replace('/w1_slave', '')
                                if sensor_name == short_name:
                                    bus_address = sensor_address

                        json_values['bus_address'] = bus_address

                    return {
                        "name": name,
                        "values": json_values
                    }

        except IOError as e:
            print("Sensor file for sensor " + name + " not found!", e)

        return None
