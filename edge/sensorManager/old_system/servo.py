from time import sleep

from gpiozero import Servo, LED


class ServoEngine():
    def __init__(self):
        self.SERVO_PIN = 'BOARD15'
        self.POWER_PIN = 'BOARD13'

        self.servo = Servo(self.SERVO_PIN, min_pulse_width=0.55 / 1000, max_pulse_width=2.45 / 1000)
        self.led = LED(self.POWER_PIN)

    def open_close(self, sleep_time=1.0, wait_time=5.0):
        try:
            # Open shield
            self.led.on()
            sleep(sleep_time)
            self.servo.max()
            # Wait
            sleep(wait_time)
            # Close shield
            self.servo.min()
            sleep(sleep_time)
            self.led.off()
        finally:
            self.led.close()
            self.servo.close()
