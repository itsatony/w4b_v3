import subprocess


class Webcam():
    def get_indoor_image(self):
        return self.get_image('video0')

    def get_outdoor_image(self):
        return self.get_image('video2')

    def get_image(self, video_device):
        img_path = '/tmp/current_' + video_device + '.jpg'
        subprocess.call(['/usr/bin/fswebcam', '-d', '/dev/' + video_device, '-r', '"1280x960"', img_path])
        return img_path
