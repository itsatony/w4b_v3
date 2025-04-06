from datetime import datetime
from os.path import isfile
from time import sleep

from smbus2 import SMBus

from aggregator import Aggregator


class Sensor:
    TIMESTAMP = 'timestamp'

    def __init__(self, aggregator: Aggregator, sensor_name: str) -> None:
        super().__init__()
        self._aggregator = aggregator
        self.__sensor_name = sensor_name

    def get_sensor_name(self) -> str:
        return self.__sensor_name if self.__sensor_name is not None else ''

    @staticmethod
    def get_time() -> int:
        return int(datetime.timestamp(datetime.now()))

    @staticmethod
    def wait(wait_time: float) -> None:
        sleep(wait_time)

    def measure(self) -> None:
        pass
    
    def get_measure(self):
        pass

class SerialSensor(Sensor):
    def __init__(self, aggregator: Aggregator, bus_path: str, sensor_name: str) -> None:
        super().__init__(aggregator, sensor_name)
        if not isfile(bus_path):
            raise FileNotFoundError
        self._bus_path = bus_path

    def get_bus_path(self) -> str:
        return self._bus_path


class I2CSensor(Sensor):
    def __init__(self, aggregator: Aggregator, bus_address: int, sensor_name: str) -> None:
        super().__init__(aggregator, sensor_name)
        self._bus_address = bus_address
        self._bus = SMBus(1)
