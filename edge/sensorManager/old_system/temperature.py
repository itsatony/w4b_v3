from re import compile
from subprocess import run, PIPE

from aggregator import Aggregator
from sensors.sensor import SerialSensor
from re import compile


class TemperatureBusSensor(SerialSensor):
    NAME = 'temperature'
    PATTERN = compile('([a-z0-9]{2} ){9}t=(-?\\d+)\n')

    def __init__(self, aggregator: Aggregator, bus_path: str, sensor_name: str) -> None:
        super().__init__(aggregator, bus_path, sensor_name)

    def __read_sensor(self) -> float:
        result = run(['tail', '-1', self._bus_path], stdout=PIPE)
        value = self.PATTERN.match(result.stdout.decode('utf-8'))
        if value is None:
            return -1
        value = value.group(2)
        if value is None:
            return -1
        return float(value) / 1000

    def measure(self):
        temps = self.get_measure()
        self._aggregator.commit(temps['values'], temps['name'])

    def get_measure(self):
        name = self.NAME + self.get_sensor_name()
        temperature = self.__read_sensor()
        values = {self.NAME: temperature, self.TIMESTAMP: self.get_time()}

        return (
            {
                'name': name,
                'values': values
            }
        )
