from aggregator import Aggregator
from sensors.sensor import I2CSensor


class HumiditySensor(I2CSensor):
    SLEEP_TIME = 0.015
    CONF_REGISTER = 2
    HUMIDITY_BYTE, TEMPERATURE_BYTE = 1, 0
    READING_BYTE = 1 << 12
    CONVERSION = pow(2, -16)
    NAME = 'humidity'

    def __init__(self, aggregator: Aggregator, bus_address: int, sensor_name: str = None) -> None:
        super().__init__(aggregator, bus_address, sensor_name)

    def __init_measurement(self) -> None:
        self._bus.write_byte_data(self._bus_address, self.CONF_REGISTER, self.READING_BYTE)
        self.wait(self.SLEEP_TIME)

    def __init_humidity_measurement(self) -> None:
        self._bus.write_byte(self._bus_address, self.HUMIDITY_BYTE)
        self.wait(self.SLEEP_TIME)

    def __init_temperature_measurement(self) -> None:
        self._bus.write_byte(self._bus_address, self.TEMPERATURE_BYTE)
        self.wait(self.SLEEP_TIME)

    def __get_temperature(self) -> float:
        data0 = self._bus.read_byte(self._bus_address) << 8
        data1 = self._bus.read_byte(self._bus_address)
        return 165 * (data0 + data1) * self.CONVERSION - 40

    def __get_humidity(self) -> float:
        data0 = self._bus.read_byte(self._bus_address) << 8
        data1 = self._bus.read_byte(self._bus_address)
        return 100 * (data0 + data1) * self.CONVERSION

    def measure(self) -> None:
        temperature, humidity = self.get_measure()
        self._aggregator.commit(temperature['values'], temperature['name'])
        self._aggregator.commit(humidity['values'], humidity['name'])

    def get_measure(self):
        time = self.get_time()
        self.__init_measurement()

        self.__init_temperature_measurement()
        temperature = self.__get_temperature()
        temperature_name = 'temperature' + self.get_sensor_name()
        temperature_values = {'temperature': temperature, self.TIMESTAMP: time}

        self.__init_humidity_measurement()
        humidity = self.__get_humidity()
        humidity_name = self.NAME + self.get_sensor_name()
        humidity_values = {self.NAME: humidity, self.TIMESTAMP: time}

        return (
            {
                'name': temperature_name,
                'values': temperature_values
            },
            {
                'name': humidity_name,
                'values': humidity_values
            }
        )
