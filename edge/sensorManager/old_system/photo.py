from aggregator import Aggregator
from sensors.sensor import I2CSensor


class PhotoSensor(I2CSensor):
    INTEGRATION_TIMES = {100: 0x00, 200: 0x01, 300: 0x02, 400: 0x03, 500: 0x04, 600: 0x05}
    GAINS = {'low': (0x00, 1), 'medium': (0x10, 25), 'high': (0x20, 425), 'max': (0x30, 7850)}
    NAME = 'photo'
    COMMAND_BIT = 0xA0
    REGISTER_CONTROL, REGISTER_ENABLE = 0x01, 0x00
    ENABLE_POWER_OFF, ENABLE_POWER_ON, ENABLE_POWER_AEN, ENABLE_POWER_AIEN = 0x00, 0x01, 0x02, 0x10
    REGISTER_CHANNEL_0, REGISTER_CHANNEL_1 = 0x14, 0x16

    def __init__(self, aggregator: Aggregator, bus_address: int, integration_time: int, gain: str,
                 sensor_name: str = None) -> None:
        super().__init__(aggregator, bus_address, sensor_name)
        self.__integration_hex, self.__integration_time = self.INTEGRATION_TIMES[integration_time], integration_time
        self.__gain_hex, self.__gain = self.GAINS[gain]
        self.__enable()
        self._bus.write_byte_data(self._bus_address, self.COMMAND_BIT | self.REGISTER_CONTROL,
                                  self.__gain_hex | self.__integration_hex)
        self.__disable()

    def __enable(self) -> None:
        self._bus.write_byte_data(self._bus_address, self.COMMAND_BIT | self.REGISTER_ENABLE,
                                  self.ENABLE_POWER_ON | self.ENABLE_POWER_AEN | self.ENABLE_POWER_AIEN)

    def __disable(self) -> None:
        self._bus.write_byte_data(self._bus_address, self.COMMAND_BIT | self.REGISTER_ENABLE, self.ENABLE_POWER_OFF)

    def __read_data(self, address: int) -> int:
        return self._bus.read_word_data(self._bus_address, address)

    def __convert_to_lux(self, full: float, infrared: float) -> float:
        cpl = self.__integration_time * self.__gain / 408
        if cpl == 0:
            return 0
        lux1 = full - 1.64 * infrared
        lux2 = 0.59 * full - 0.86 * infrared
        return max(lux1, lux2) / cpl

    def measure(self) -> None:
        light = self.get_measure()
        self._aggregator.commit(light['values'], light['name'])

    def get_measure(self):
        self.__enable()
        self.wait(0.1 + self.__integration_time / 1000)
        full = self.__read_data(self.COMMAND_BIT | self.REGISTER_CHANNEL_0)
        infrared = self.__read_data(self.COMMAND_BIT | self.REGISTER_CHANNEL_1)
        self.__disable()
        lux = self.__convert_to_lux(full, infrared)
        name = self.NAME + self.get_sensor_name()
        values = {self.TIMESTAMP: self.get_time(), 'ambient_light': full, 'infrared_light': infrared, 'lux': lux}

        return (
            {
                'name': name,
                'values': values
            }
        )
        
