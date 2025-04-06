from math import pi
from re import match
from threading import RLock

from aggregator import Aggregator
from sensors.sensor import I2CSensor

ERROR_VALUE = -float('inf')
FLOAT_PATTERN = "^-?\\d+(\\.\\d+)?$"


class SimpleI2CSensor(I2CSensor):
    def __init__(self, aggregator: Aggregator, bus_address: int, sensor_name: str, type_name: str, value_name: str,
                 data: int, size: int, lock: RLock) -> None:
        super().__init__(aggregator, bus_address, sensor_name)
        self.__data = data
        self.__size = size
        self._type_name = type_name
        self._value_name = value_name
        self.__lock = lock

    def _init_measurement(self) -> bool:
        try:
            self._bus.write_byte(self._bus_address, self.__data)
            return True
        except IOError:
            return False

    @staticmethod
    def __calculate_value(data) -> float:
        tmp = "".join(map(chr, filter(lambda x: x < 255, data)))
        if match(FLOAT_PATTERN, tmp) is None:
            return ERROR_VALUE
        return float(tmp)

    def __read_data(self) -> list:
        try:
            return self._bus.read_i2c_block_data(self._bus_address, 0, self.__size)
        except OSError:
            return []

    def _read_sensor_data(self) -> float:
        with self.__lock:
            if not self._init_measurement():
                return ERROR_VALUE
            self.wait(0.1)
            data = self.__read_data()

        if data is None or len(data) == 0:
            return ERROR_VALUE
        return self.__calculate_value(data)

    def measure(self) -> None:
        i2cs = self.get_measure()
        if i2cs == None:
            return None

        self._aggregator.commit(i2cs['values'], i2cs['name'])
    
    def get_measure(self):
        value = self._read_sensor_data()
        if value == ERROR_VALUE:
            return None

        name = self._type_name + self.get_sensor_name()
        values = {self.TIMESTAMP: self.get_time(), self._value_name: value}

        return (
            {
                'name': name,
                'values': values
            }
        )


class WindSensor(SimpleI2CSensor):
    def __init__(self, aggregator: Aggregator, bus_address: int, sensor_name: str, type_name: str, value_name: str,
                 data: int, size: int, lock: RLock, diameter: float) -> None:
        super().__init__(aggregator, bus_address, sensor_name, type_name, value_name, data, size, lock)
        self.__circumference = diameter * pi

    def measure(self) -> None:
        winds = self.get_measure()
        if winds == None:
            return None

        self._aggregator.commit(winds['values'], winds['name'])
    
    def get_measure(self):
        value = self._read_sensor_data()
        if value == ERROR_VALUE:
            return

        name = self._type_name + self.get_sensor_name()
        values =  {self.TIMESTAMP: self.get_time(), self._value_name: value * self.__circumference,
                  self._value_name + '_raw': value}

        return (
            {
                'name': name,
                'values': values
            }
        )


class BalanceSensor(SimpleI2CSensor):
    def __init__(self, aggregator: Aggregator, bus_address: int, sensor_name: str, type_name: str, value_name: str,
                 data: int, size: int, lock: RLock, offset: int, factor: float) -> None:
        super().__init__(aggregator, bus_address, sensor_name, type_name, value_name, data, size, lock)
        self.__offset = offset
        self.__factor = factor

    def measure(self) -> None:
        balances = self.get_measure()
        if balances == None:
            return None

        self._aggregator.commit(balances['values'], balances['name'])

    def get_measure(self):
        value = self._read_sensor_data()
        if value == ERROR_VALUE:
            return

        name = self._type_name + self.get_sensor_name()
        values =  {self.TIMESTAMP: self.get_time(), self._value_name: (value - self.__offset) * self.__factor,
                  self._value_name + '_raw': value}

        return (
            {
                'name': name,
                'values': values
            }
        )
