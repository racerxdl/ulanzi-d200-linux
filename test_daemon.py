import unittest
import tempfile
import io
from unittest.mock import patch
from pathlib import Path
from PIL import Image

from ulanzi_manager.config import ButtonConfig, Config, parse_metrics_style
from ulanzi_manager.daemon import UlanziDaemon, _load_gif_frames
from ulanzi_manager.device import ButtonPress


class FakeDevice:
    def __init__(self):
        self.read_count = 0
        self.keepalive_times = []
        self.close_count = 0
        self.clock = None
        self.write_error = None
        self.small_window_updates = []
        self.configuration_requested = False

    def read_button_press(self):
        self.read_count += 1

    def set_small_window_data(self, data):
        if self.write_error:
            raise self.write_error
        self.keepalive_times.append(self.clock.current)
        self.small_window_updates.append(dict(data))

    def close(self):
        self.close_count += 1


class FakeExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, action_type, params):
        self.calls.append((action_type, params))


class FakeClock:
    def __init__(self, daemon, stop_at=2.2):
        self.daemon = daemon
        self.stop_at = stop_at
        self.current = 0.0

    def monotonic(self):
        return self.current

    def sleep(self, seconds):
        self.current += seconds
        if self.current >= self.stop_at:
            self.daemon.running = False


class UlanziDaemonTest(unittest.TestCase):
    def _started_daemon(self):
        daemon = UlanziDaemon("unused.yaml")
        device = FakeDevice()
        daemon.device = device

        def start():
            daemon.running = True
            return True

        return daemon, device, start

    def test_keepalive_is_rate_limited_while_buttons_remain_responsive(self):
        daemon, device, start = self._started_daemon()
        clock = FakeClock(daemon)
        device.clock = clock

        with (
            patch.object(daemon, "start", side_effect=start),
            patch("ulanzi_manager.daemon.signal.signal"),
            patch("ulanzi_manager.daemon.time.monotonic", side_effect=clock.monotonic),
            patch("ulanzi_manager.daemon.time.sleep", side_effect=clock.sleep),
        ):
            daemon.run()

        self.assertEqual(3, len(device.keepalive_times))
        self.assertAlmostEqual(0.0, device.keepalive_times[0])
        self.assertAlmostEqual(1.0, device.keepalive_times[1])
        self.assertAlmostEqual(2.0, device.keepalive_times[2])
        self.assertGreaterEqual(device.read_count, 40)
        self.assertEqual(1, device.close_count)

    def test_custom_image_mode_remains_active_during_keepalive(self):
        daemon, device, start = self._started_daemon()
        clock = FakeClock(daemon)
        device.clock = clock
        daemon.small_window_mode = 2

        with (
            patch.object(daemon, "start", side_effect=start),
            patch("ulanzi_manager.daemon.signal.signal"),
            patch("ulanzi_manager.daemon.time.monotonic", side_effect=clock.monotonic),
            patch("ulanzi_manager.daemon.time.sleep", side_effect=clock.sleep),
        ):
            daemon.run()

        self.assertEqual([{"mode": 2}] * 3, device.small_window_updates)

    def test_metrics_refresh_independently_of_usb_keepalive(self):
        class TimedDisplay(FakeDevice):
            def __init__(self):
                super().__init__()
                self.frame_times = []

            def set_brightness(self, _brightness):
                pass

            def set_buttons(self, buttons, partial=False):
                if partial:
                    self.frame_times.append(self.clock.current)

        daemon = UlanziDaemon("unused.yaml")
        clock = FakeClock(daemon, stop_at=4.7)
        device = TimedDisplay()
        device.clock = clock
        daemon.device = device
        daemon.config = Config(buttons=[ButtonConfig(
            index=13, image=None, label="", action_type="command", action_params={},
            action_enabled=False, display_mode="stats",
            metrics_style=parse_metrics_style({"view": "history"}),
        )])
        daemon.metrics = type("Metrics", (), {
            "sample": lambda _self: {"cpu": round(clock.current * 10), "mem": 50, "gpu": 25},
        })()

        def start():
            daemon._configure_device()
            daemon.running = True
            return True

        with (
            patch.object(daemon, "start", side_effect=start),
            patch("ulanzi_manager.daemon.signal.signal"),
            patch("ulanzi_manager.daemon.time.monotonic", side_effect=clock.monotonic),
            patch("ulanzi_manager.daemon.time.sleep", side_effect=clock.sleep),
        ):
            daemon.run()

        self.assertEqual(4, len(device.frame_times))
        for previous, current in zip(device.frame_times, device.frame_times[1:]):
            self.assertGreaterEqual(current - previous, 1.5 - 1e-6)
            self.assertLessEqual(current - previous, 1.55 + 1e-6)
        periodic_keepalives = device.keepalive_times[1:]
        self.assertEqual(5, len(periodic_keepalives))
        for previous, current in zip(periodic_keepalives, periodic_keepalives[1:]):
            self.assertGreaterEqual(current - previous, 1.0 - 1e-6)
            self.assertLessEqual(current - previous, 1.05 + 1e-6)

    def test_action_runs_on_press_not_release(self):
        daemon = UlanziDaemon("unused.yaml")
        daemon.config = Config(
            buttons=[
                ButtonConfig(
                    index=0,
                    image=None,
                    label="Teste",
                    action_type="command",
                    action_params={"cmd": "true"},
                )
            ]
        )
        daemon.executor = FakeExecutor()

        daemon._on_button_press(ButtonPress(index=0, pressed=False, state=0))
        daemon._on_button_press(ButtonPress(index=0, pressed=True, state=0))

        self.assertEqual([("command", {"cmd": "true"})], daemon.executor.calls)

    def test_display_only_gif_does_not_execute_an_action(self):
        daemon = UlanziDaemon("unused.yaml")
        daemon.config = Config(
            buttons=[
                ButtonConfig(
                    index=13,
                    image=None,
                    label="",
                    action_type="command",
                    action_params={"cmd": ""},
                    action_enabled=False,
                )
            ]
        )
        daemon.executor = FakeExecutor()

        daemon._on_button_press(ButtonPress(index=13, pressed=True, state=0))

        self.assertEqual([], daemon.executor.calls)

    def test_gif_frames_are_ready_for_partial_updates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "status.gif"
            frames = [
                Image.new("RGB", (458, 196), color)
                for color in ("red", "blue")
            ]
            frames[0].save(
                path,
                save_all=True,
                append_images=frames[1:],
                duration=[40, 250],
                loop=0,
            )

            decoded = _load_gif_frames(str(path))

            self.assertEqual(2, len(decoded))
            self.assertEqual(0.1, decoded[0][1])
            self.assertEqual(0.25, decoded[1][1])
            self.assertNotEqual(decoded[0][0], decoded[1][0])
            self.assertNotEqual(decoded[0][2], decoded[1][2])

    def test_initial_wide_archive_separates_first_png_frame(self):
        class ConfigurationDevice:
            def __init__(self):
                self.button_calls = []
                self.small_window_updates = []

            def set_brightness(self, _brightness):
                pass

            def set_label_style(self, _style):
                pass

            def set_buttons(self, buttons, partial=False):
                self.button_calls.append((buttons, partial))

            def set_small_window_data(self, data):
                self.small_window_updates.append(dict(data))

        with tempfile.TemporaryDirectory() as temp_dir:
            gif_path = Path(temp_dir) / "large.gif"
            frames = [
                Image.new("RGB", (458, 196), color)
                for color in ("red", "blue")
            ]
            frames[0].save(
                gif_path,
                save_all=True,
                append_images=frames[1:],
                duration=100,
                loop=0,
            )
            daemon = UlanziDaemon("unused.yaml")
            daemon.config = Config(
                buttons=[
                    ButtonConfig(
                        index=13,
                        image=str(gif_path),
                        label="",
                        action_type="command",
                        action_params={"cmd": ""},
                        action_enabled=False,
                        display_mode="gif",
                    )
                ]
            )
            daemon.device = ConfigurationDevice()

            daemon._configure_device()

            initial, initial_partial = daemon.device.button_calls[0]
            first_frame, frame_partial = daemon.device.button_calls[1]
            self.assertFalse(initial_partial)
            self.assertNotIn("image", initial[13])
            self.assertNotIn("image_data", initial[13])
            self.assertEqual(2, initial[13]["small_view_mode"])
            self.assertTrue(frame_partial)
            self.assertTrue(
                first_frame[13]["image_data"].startswith(b"\x89PNG\r\n\x1a\n")
            )
            self.assertTrue(first_frame[13]["image_name"].endswith(".png"))
            self.assertEqual(2, len(daemon.gif_frames))
            self.assertEqual([{"mode": 2}], daemon.device.small_window_updates)


    def test_static_wide_background_is_sent_after_initial_archive(self):
        class ConfigurationDevice:
            def __init__(self):
                self.button_calls = []
                self.small_window_updates = []

            def set_brightness(self, _brightness):
                pass

            def set_label_style(self, _style):
                pass

            def set_buttons(self, buttons, partial=False):
                self.button_calls.append((buttons, partial))

            def set_small_window_data(self, data):
                self.small_window_updates.append(dict(data))

        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "background.png"
            Image.new("RGB", (458, 196), "navy").save(image_path)
            daemon = UlanziDaemon("unused.yaml")
            daemon.config = Config(
                buttons=[
                    ButtonConfig(
                        index=13,
                        image=str(image_path),
                        label="",
                        action_type="command",
                        action_params={"cmd": ""},
                        action_enabled=False,
                        display_mode="background",
                    )
                ]
            )
            daemon.device = ConfigurationDevice()

            daemon._configure_device()

            initial, initial_partial = daemon.device.button_calls[0]
            background, background_partial = daemon.device.button_calls[1]
            self.assertFalse(initial_partial)
            self.assertNotIn("image", initial[13])
            self.assertEqual(2, initial[13]["small_view_mode"])
            self.assertTrue(background_partial)
            self.assertEqual(str(image_path), background[13]["image"])
            self.assertEqual([], daemon.gif_frames)
            self.assertEqual([{"mode": 2}], daemon.device.small_window_updates)

    def test_history_uses_real_samples_and_leaves_unmeasured_time_empty(self):
        class DisplayDevice:
            def set_brightness(self, _value):
                pass

            def set_small_window_data(self, _data):
                pass

            def set_buttons(self, buttons, partial=False):
                if partial:
                    self.frame = Image.open(io.BytesIO(buttons[13]["image_data"])).convert("RGB")

        daemon = UlanziDaemon("unused.yaml")
        daemon.device = DisplayDevice()
        values = {"cpu": 0, "mem": 75, "gpu": 25}
        daemon.metrics = type("Metrics", (), {"sample": lambda _self: values.copy()})()
        daemon.config = Config(buttons=[ButtonConfig(
            index=13, image=None, label="", action_type="command", action_params={},
            action_enabled=False, display_mode="stats",
            metrics_style=parse_metrics_style({
                "view": "history", "colors": {
                    "cpu": {"color": "#ffffff", "line_color": "#ff0000"},
                    "mem": {"color": "#ffffff", "line_color": "#00ff00"},
                    "gpu": {"color": "#ffffff", "line_color": "#0000ff"},
                },
            }),
        )])
        with patch("ulanzi_manager.daemon.time.monotonic", return_value=0):
            daemon._configure_device()
        self.assertEqual((255, 0, 0), daemon.device.frame.getpixel((446, 164)))
        empty_plot_pixel = daemon.device.frame.getpixel((50, 128))

        values["cpu"] = 100
        with patch("ulanzi_manager.daemon.time.monotonic", return_value=1.49):
            daemon._update_stats_background()
        self.assertEqual([(0, {"cpu": 0, "mem": 75, "gpu": 25})], list(daemon.stats_history))
        with patch("ulanzi_manager.daemon.time.monotonic", return_value=1.5):
            daemon._update_stats_background()
        self.assertEqual((255, 0, 0), daemon.device.frame.getpixel((446, 92)))

        values["cpu"] = 50
        with patch("ulanzi_manager.daemon.time.monotonic", return_value=70):
            daemon._update_stats_background()
        self.assertEqual((255, 0, 0), daemon.device.frame.getpixel((446, 128)))
        self.assertEqual(empty_plot_pixel, daemon.device.frame.getpixel((50, 128)))
        with patch("ulanzi_manager.daemon.time.monotonic", return_value=70):
            daemon._configure_device()
        self.assertEqual([(70, {"cpu": 50, "mem": 75, "gpu": 25})], list(daemon.stats_history))
        values["cpu"] = 100
        with patch("ulanzi_manager.daemon.time.monotonic", return_value=130):
            daemon._update_stats_background()
        # All three continuous lines survive on the same plot, independently of white values.
        column_colors = {daemon.device.frame.getpixel((120, y)) for y in range(92, 165)}
        self.assertTrue({(255, 0, 0), (0, 255, 0), (0, 0, 255)} <= column_colors)
        self.assertEqual((0, 0, 0), daemon.device.frame.getpixel((120, 154)))

    def test_hid_write_failure_reaches_service_manager(self):
        daemon, device, start = self._started_daemon()
        device.clock = FakeClock(daemon)
        device.write_error = OSError("device disconnected")

        with (
            patch.object(daemon, "start", side_effect=start),
            patch("ulanzi_manager.daemon.signal.signal"),
            self.assertRaisesRegex(OSError, "device disconnected"),
        ):
            daemon.run()

        self.assertEqual(1, device.close_count)


if __name__ == "__main__":
    unittest.main()
