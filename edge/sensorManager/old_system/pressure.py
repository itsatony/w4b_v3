from ctypes import c_ushort, c_short, c_ubyte, c_byte

from aggregator import Aggregator
from sensors.sensor import I2CSensor


class PressureSensor(I2CSensor):
    """
    I2C Implementation of the BME 280:
    https://ae-bst.resource.bosch.com/media/_tech/media/datasheets/BST-BME280-DS002.pdf
    """
    TEMPERATURE_LENGTH = 6
    SIZE = 24
    NAME = 'pressure'
    MODE, OVERSAMPLING_P, OVERSAMPLING_T, OVERSAMPLING_H = 1, 2, 2, 2
    WAIT_TIME = (1.25 + 2.3 * OVERSAMPLING_T + (2.3 * OVERSAMPLING_P + 0.575) + (2.3 * OVERSAMPLING_H + 0.575)) / 1000
    STANDBY_TIME = 4  # 100

    REG_CONTROL = 0xF4
    REG_CONTROL_H = 0xF2
    REG_CONFIG = 0xF5

    TEMPERATURE_KELVIN = 273.15
    TEMPERATURE_FACTOR = 5120.

    def __init__(self, aggregator: Aggregator, bus_address: int, altitude: int, sensor_name: str = None) -> None:
        super().__init__(aggregator, bus_address, sensor_name)
        self.__altitude = altitude
        self.__temperature_compensation, self.__pressure_compensation, self.__humidity_calibration = self.__calibrate()

    @staticmethod
    def __get_ushort(val1: int, val2: int) -> int:
        return c_ushort((val1 << 8) | val2).value

    @staticmethod
    def __get_short(val1: int, val2: int) -> int:
        return c_short((val1 << 8) | val2).value

    @staticmethod
    def __get_uchar(val: int) -> int:
        return c_ubyte(val).value

    def __create_coefficients(self, data: list) -> list:
        return [self.__get_ushort(data[1], data[0])] + \
               [self.__get_short(data[i + 1], data[i]) for i in range(2, len(data), 2)]

    def __create_humidity_coefficients(self) -> list:
        h1 = self.__get_uchar(self._bus.read_byte_data(self._bus_address, 0xA1))
        h = self._bus.read_i2c_block_data(self._bus_address, 0xE1, 7)
        h2 = self.__get_short(h[1], h[0])
        h3 = self.__get_uchar(h[2])
        h4 = c_short(h[3] << 4 | (0x0F & h[4])).value
        h5 = c_short((h[5] << 4) | ((h[4] >> 4) & 0x0F)).value
        h6 = c_byte(h[6]).value
        return [h1, h2, h3, h4, h5, h6]

    def __calibrate(self) -> (tuple, tuple, tuple):
        data = self._bus.read_i2c_block_data(self._bus_address, 0x88, self.SIZE)
        temperature_calibration = self.__create_coefficients(data[:self.TEMPERATURE_LENGTH])
        pressure_calibration = self.__create_coefficients(data[self.TEMPERATURE_LENGTH:])
        humidity_calibration = self.__create_humidity_coefficients()
        return tuple(temperature_calibration), tuple(pressure_calibration), tuple(humidity_calibration)

    def __get_adc_values(self) -> (int, int, int):
        data = self._bus.read_i2c_block_data(self._bus_address, 0xF7, 8)
        adc_p = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        adc_t = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        adc_h = (data[6] << 8) | data[7]
        return adc_p, adc_t, adc_h

    def __calculate_temperature(self, adc: int) -> float:
        temp1 = (adc / 16384 - self.__temperature_compensation[0] / 1024) * self.__temperature_compensation[1]
        temp2 = pow(adc / 131072 - self.__temperature_compensation[0] / 8192, 2) * self.__temperature_compensation[2]
        return temp1 + temp2

    def __calculate_pressure(self, adc: int, temperature_fine: float) -> float:
        var1 = temperature_fine / 2 - 64000
        var2 = pow(var1, 2) * self.__pressure_compensation[5] / 32768
        var2 = var2 + var1 * self.__pressure_compensation[4] * 2
        var2 = var2 / 4 + self.__pressure_compensation[3] * 65536
        var1 = (self.__pressure_compensation[2] * var1 / 524288 + self.__pressure_compensation[1]) * var1 / 524288
        var1 = (1 + var1 / 32768) * self.__pressure_compensation[0]
        if var1 == 0:
            return 0
        pressure = 1048576 - adc
        pressure = ((pressure - (var2 / 4096)) * 6250) / var1
        var1 = pow(pressure, 2) * self.__pressure_compensation[8] / 2147483648
        var2 = pressure * self.__pressure_compensation[7] / 32768
        pressure += (var1 + var2 + self.__pressure_compensation[6]) / 16
        return pressure / 100  # convert to hPa

    def __calculate_humidity(self, adc: int, temperature_fine: float) -> float:
        var_h = temperature_fine - 76800
        if var_h == 0:
            return 0
        var_h = (adc - (self.__humidity_calibration[3] * 64 + self.__humidity_calibration[4] / 16384 * var_h)) * \
                (self.__humidity_calibration[1] / 65536 * (1 + self.__humidity_calibration[5] / 67108864 * var_h *
                                                           (1 + self.__humidity_calibration[2] / 67108864 * var_h)))
        var_h *= (1 - self.__humidity_calibration[0] * var_h / 524288)
        if var_h > 100:
            return 100
        if var_h < 0:
            return 0
        return var_h

    def measure(self) -> None:
        air_pressure, temperature, humidity = self.get_measure()
        self._aggregator.commit(air_pressure['values'], air_pressure['name'])
        self._aggregator.commit(temperature['values'], temperature['name'])
        self._aggregator.commit(humidity['values'], humidity['name'])

    def get_measure(self):
        control = self.OVERSAMPLING_T << 5 | self.OVERSAMPLING_P << 2 | self.MODE
        self._bus.write_byte_data(self._bus_address, self.REG_CONTROL, control)
        self._bus.write_byte_data(self._bus_address, self.REG_CONFIG, self.STANDBY_TIME << 5)
        self._bus.write_byte_data(self._bus_address, self.REG_CONTROL_H, self.OVERSAMPLING_H)

        self.wait(self.WAIT_TIME)
        adc_p, adc_t, adc_h = self.__get_adc_values()

        temperature = self.__calculate_temperature(adc_t)
        pressure = self.__calculate_pressure(adc_p, temperature)
        humidity = self.__calculate_humidity(adc_h, temperature)
        temperature /= self.TEMPERATURE_FACTOR
        temperature_k = temperature + self.TEMPERATURE_KELVIN

        # pressure_nn = pressure / pow(1 - self.__altitude / 44330, 5.255)
        # Barometric formula: https://en.wikipedia.org/wiki/Barometric_formula
        pressure_nn = pressure * pow(temperature_k / (temperature_k + 0.0065 * self.__altitude), -5.255)

        time = self.get_time()
        air_pressure_name = self.NAME + self.get_sensor_name()
        air_pressure_values = {'air_pressure': pressure, 'normalized_pressure': pressure_nn, self.TIMESTAMP: time}

        temperature_name = 'temperature' + self.get_sensor_name()
        temperature_values = {self.TIMESTAMP: time, 'temperature': temperature}

        humidity_name = 'humidity' + self.get_sensor_name()
        humidity_values = {self.TIMESTAMP: time, 'humidity': humidity}

        return (
            {
                'name': air_pressure_name,
                'values': air_pressure_values
            },
            {
                'name': temperature_name,
                'values': temperature_values
            },
            {
                'name': humidity_name,
                'values': humidity_values
            }
        )
