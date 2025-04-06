import subprocess


class Arduino:
    def __init__(self):
        self.PATH = '/home/pi/code-we4bee-sensor_network/config/flash_arduino.sh'

    def flash(self):
        return subprocess.getoutput('/bin/bash ' + self.PATH)
