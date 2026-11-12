"""D200X: consecutive statistics frames must use different icon paths."""

import unittest

from ulanzi_manager.daemon import UlanziDaemon


class RecordingDevice:
    def __init__(self):
        self.names = []

    def set_buttons(self, buttons, partial=False, cache=True):
        self.names.append(buttons[13]['image_name'])


class StatsFrameNameTest(unittest.TestCase):
    def test_frames_alternate_between_two_names(self):
        daemon = UlanziDaemon('/nonexistent/config.yaml')
        daemon.device = RecordingDevice()
        for _ in range(4):
            daemon._send_stats_frame(b'png')
        names = daemon.device.names
        self.assertEqual(len(set(names)), 2)
        for previous, current in zip(names, names[1:]):
            self.assertNotEqual(previous, current)


if __name__ == '__main__':
    unittest.main()
