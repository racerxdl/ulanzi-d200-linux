import unittest
import tempfile
import io
import threading
from unittest.mock import patch
from pathlib import Path
from PIL import Image, ImageChops, ImageOps, ImageSequence
import yaml

from ulanzi_manager.config import ButtonConfig, Config, ConfigParser, parse_metrics_style
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


class StatsDisplay(FakeDevice):
    def __init__(self):
        super().__init__()
        self.button_calls = []
        self.write_threads = []

    def set_brightness(self, _brightness):
        self.write_threads.append(threading.get_ident())

    def set_label_style(self, _style):
        self.write_threads.append(threading.get_ident())

    def set_buttons(self, buttons, partial=False, *, cache=True):
        self.write_threads.append(threading.get_ident())
        self.button_calls.append((buttons, partial, cache))
        if partial:
            self.frame = Image.open(io.BytesIO(buttons[13]["image_data"])).convert("RGB")

    def set_small_window_data(self, data):
        self.write_threads.append(threading.get_ident())
        super().set_small_window_data(data)

    def drain_input(self):
        return 0

    def set_button_callback(self, callback):
        self.callback = callback


class UlanziDaemonTest(unittest.TestCase):
    def test_first_run_provisions_and_renders_without_missing_images(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "new" / "config.yaml"
            daemon = UlanziDaemon(str(path))
            device = StatsDisplay()
            device.clock = FakeClock(daemon)
            try:
                with (
                    patch("ulanzi_manager.daemon.UlanziDevice", return_value=device),
                    patch.object(daemon.metrics, "sample", return_value={"cpu": 25, "mem": 50, "gpu": 0}),
                ):
                    self.assertTrue(daemon.start())
                self.assertTrue(path.is_file())
                self.assertEqual([13], [button.index for button in daemon.config.buttons])
                self.assertTrue(all(not button.action_enabled for button in daemon.config.buttons))
                self.assertEqual((458, 196), device.frame.size)
            finally:
                daemon.stop()

    def test_start_preserves_existing_configuration_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            original = (
                "# Keep my formatting and comments\nbrightness: 37\nbuttons:\n"
                + "  - null\n" * 13
                + "  - display_mode: stats\n    action_enabled: false\n"
            ).encode()
            path.write_bytes(original)
            daemon = UlanziDaemon(str(path))
            device = StatsDisplay()
            device.clock = FakeClock(daemon)
            try:
                with (
                    patch("ulanzi_manager.daemon.UlanziDevice", return_value=device),
                    patch.object(daemon.metrics, "sample", return_value={"cpu": 25, "mem": 50, "gpu": 0}),
                ):
                    self.assertTrue(daemon.start())
                self.assertEqual(original, path.read_bytes())
                self.assertEqual(37, daemon.config.brightness)
                self.assertEqual((458, 196), device.frame.size)
            finally:
                daemon.stop()

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

    def _stats_daemon(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        daemon = UlanziDaemon(str(Path(directory.name) / "config.yaml"))
        clock = FakeClock(daemon, stop_at=3.7)
        device = StatsDisplay()
        device.clock = clock
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
        daemon.device = device
        return daemon, device, clock

    def test_slow_collection_and_rendering_leave_polling_and_keepalive_responsive(self):
        for phase in ("collection", "rendering"):
            with self.subTest(phase=phase):
                daemon, device, clock = self._stats_daemon()
                owner = threading.get_ident()
                entered, release = threading.Event(), threading.Event()
                sample_threads = []
                sample_times = []
                original_save = Image.Image.save

                def block():
                    entered.set()
                    if not release.wait(5):
                        raise RuntimeError("Test did not release statistics work")

                def sample():
                    sample_threads.append(threading.get_ident())
                    sample_times.append(clock.current)
                    if threading.get_ident() != owner and phase == "collection":
                        block()
                    return {"cpu": 50, "mem": 75, "gpu": 25}

                def save(image, *args, **kwargs):
                    if threading.get_ident() != owner and phase == "rendering":
                        block()
                    return original_save(image, *args, **kwargs)

                def unblock_on_stop():
                    daemon._stats_stop.wait(5)
                    release.set()

                releaser = threading.Thread(target=unblock_on_stop)

                def sleep(seconds):
                    if clock.current >= 1.5 and not entered.is_set():
                        self.assertTrue(entered.wait(5), "Statistics worker did not start")
                    clock.sleep(seconds)
                    if not daemon.running:
                        releaser.start()

                daemon.metrics = type("Metrics", (), {"sample": staticmethod(sample)})()
                try:
                    with (
                        patch("ulanzi_manager.daemon.ConfigParser.load", return_value=daemon.config),
                        patch("ulanzi_manager.daemon.UlanziDevice", return_value=device),
                        patch("ulanzi_manager.daemon.signal.signal"),
                        patch("ulanzi_manager.daemon.time.monotonic", side_effect=clock.monotonic),
                        patch("ulanzi_manager.daemon.time.sleep", side_effect=sleep),
                        patch.object(Image.Image, "save", save),
                    ):
                        daemon.run()
                finally:
                    release.set()
                    daemon.stop()
                    if releaser.ident is not None:
                        releaser.join(5)

                self.assertTrue(entered.is_set())
                self.assertGreaterEqual(device.read_count, 70)
                self.assertEqual([0.0, 0.0], device.keepalive_times[:2])
                for previous, current in zip(device.keepalive_times[1:], device.keepalive_times[2:]):
                    self.assertGreaterEqual(current - previous, 1.0 - 1e-6)
                    self.assertLessEqual(current - previous, 1.05 + 1e-6)
                self.assertEqual(2, len(sample_threads))
                self.assertEqual(owner, sample_threads[0])
                self.assertNotEqual(owner, sample_threads[1])
                self.assertGreaterEqual(sample_times[1], 1.5)
                self.assertLess(sample_times[1], 1.55)
                self.assertEqual({owner}, set(device.write_threads))
                self.assertEqual(1, device.close_count)
                self.assertEqual(1, sum(partial for _, partial, _ in device.button_calls))
                self.assertFalse(device.button_calls[-1][2])
                self.assertIsNone(daemon._stats_thread)

    def test_latest_complete_frame_replaces_pending_frames(self):
        daemon, device, clock = self._stats_daemon()
        entered = [threading.Event() for _ in range(4)]
        release = threading.Event()
        count = 0

        def sample():
            nonlocal count
            count += 1
            entered[count - 1].set()
            if count == 4 and not release.wait(5):
                raise RuntimeError("Test did not release statistics work")
            return {"cpu": count * 10, "mem": 0, "gpu": 0}

        daemon.metrics = type("Metrics", (), {"sample": staticmethod(sample)})()
        with patch("ulanzi_manager.daemon.time.monotonic", side_effect=clock.monotonic):
            daemon._configure_device()
            daemon._start_stats_worker()
            try:
                # Re-entering startup must not create a second producer.
                worker = daemon._stats_thread
                daemon._start_stats_worker()
                self.assertIs(worker, daemon._stats_thread)
                for index in range(1, 4):
                    daemon._stats_requested.set()
                    self.assertTrue(entered[index].wait(5))
                # Starting sample four proves frames two and three are complete.
                daemon._publish_stats_result()
                self.assertEqual((255, 0, 0), device.frame.getpixel((446, 142)))
                self.assertEqual(2, sum(partial for _, partial, _ in device.button_calls))
                daemon._publish_stats_result()
                self.assertEqual(2, sum(partial for _, partial, _ in device.button_calls))
                self.assertTrue(all(not cache for _, partial, cache in device.button_calls if partial))
                self.assertNotIn(worker.ident, device.write_threads)
            finally:
                release.set()
                daemon.stop()
        self.assertFalse(worker.is_alive())
        self.assertIsNone(daemon._stats_result)

    def test_reconfiguration_joins_worker_before_resetting_history(self):
        daemon, device, clock = self._stats_daemon()
        entered, release, configured = threading.Event(), threading.Event(), threading.Event()
        errors = []
        count = 0

        def sample():
            nonlocal count
            count += 1
            if count == 2:
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("Test did not release statistics work")
            return {"cpu": count * 10, "mem": 0, "gpu": 0}

        def configure():
            try:
                daemon._configure_device()
            except BaseException as error:
                errors.append(error)
            finally:
                configured.set()

        daemon.metrics = type("Metrics", (), {"sample": staticmethod(sample)})()
        with patch("ulanzi_manager.daemon.time.monotonic", side_effect=clock.monotonic):
            daemon._configure_device()
            background = daemon.stats_background
            daemon._start_stats_worker()
            worker = daemon._stats_thread
            daemon._stats_requested.set()
            reconfigure = threading.Thread(target=configure)
            try:
                self.assertTrue(entered.wait(5))
                reconfigure.start()
                self.assertTrue(daemon._stats_stop.wait(5))
                self.assertFalse(configured.is_set())
                self.assertIs(background, daemon.stats_background)
                self.assertEqual(1, len(daemon.stats_history))
            finally:
                release.set()
                if reconfigure.ident is not None:
                    reconfigure.join(5)
                daemon.stop()
                daemon.stop()
        self.assertFalse(reconfigure.is_alive())
        self.assertEqual([], errors)
        self.assertFalse(worker.is_alive())
        self.assertIsNot(background, daemon.stats_background)
        self.assertEqual([30], [sample["cpu"] for _, sample in daemon.stats_history])
        self.assertEqual(2, sum(partial for _, partial, _ in device.button_calls))
        self.assertIsNone(daemon._stats_result)
        self.assertEqual(1, device.close_count)

    def test_firmware_recovery_discards_inflight_frame_and_restarts_worker(self):
        daemon, first, clock = self._stats_daemon()
        replacement = StatsDisplay()
        replacement.clock = clock
        entered, release = threading.Event(), threading.Event()
        owner = threading.get_ident()
        sample_count = 0

        def sample():
            nonlocal sample_count
            sample_count += 1
            if sample_count == 2:
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("Test did not release statistics work")
                return {"cpu": 99, "mem": 0, "gpu": 0}
            return {"cpu": 10 if sample_count == 1 else 30, "mem": 0, "gpu": 0}

        def unblock_on_stop():
            daemon._stats_stop.wait(5)
            release.set()

        releaser = threading.Thread(target=unblock_on_stop)

        def sleep(seconds):
            if clock.current >= 1.5 and first.close_count == 0:
                self.assertTrue(entered.wait(5))
                first.configuration_requested = True
                releaser.start()
            clock.sleep(seconds)

        clock.stop_at = 2.2
        daemon.metrics = type("Metrics", (), {"sample": staticmethod(sample)})()
        try:
            with (
                patch("ulanzi_manager.daemon.ConfigParser.load", return_value=daemon.config),
                patch("ulanzi_manager.daemon.UlanziDevice", side_effect=[first, replacement]),
                patch("ulanzi_manager.daemon.signal.signal"),
                patch("ulanzi_manager.daemon.time.monotonic", side_effect=clock.monotonic),
                patch("ulanzi_manager.daemon.time.sleep", side_effect=sleep),
            ):
                daemon.run()
        finally:
            release.set()
            daemon.stop()
            if releaser.ident is not None:
                releaser.join(5)
        self.assertEqual(3, sample_count)
        self.assertEqual([30], [sample["cpu"] for _, sample in daemon.stats_history])
        self.assertEqual(1, sum(partial for _, partial, _ in first.button_calls))
        self.assertEqual(1, sum(partial for _, partial, _ in replacement.button_calls))
        self.assertEqual((255, 0, 0), replacement.frame.getpixel((446, 142)))
        self.assertEqual({owner}, set(first.write_threads + replacement.write_threads))
        self.assertEqual(1, first.close_count)
        self.assertEqual(1, replacement.close_count)
        self.assertIsNone(daemon._stats_thread)
        self.assertIsNone(daemon._stats_result)

    def test_unexpected_statistics_failure_reaches_service_manager(self):
        daemon, device, clock = self._stats_daemon()
        failure = ValueError("metric provider failed")
        owner = threading.get_ident()

        def sample():
            if threading.get_ident() != owner:
                raise failure
            return {"cpu": 50, "mem": 75, "gpu": 25}

        def sleep(seconds):
            if clock.current >= 1.5:
                # Joining a failed producer makes the error handoff deterministic.
                daemon._stats_thread.join(5)
                self.assertFalse(daemon._stats_thread.is_alive())
            clock.sleep(seconds)

        daemon.metrics = type("Metrics", (), {"sample": staticmethod(sample)})()
        with (
            patch("ulanzi_manager.daemon.ConfigParser.load", return_value=daemon.config),
            patch("ulanzi_manager.daemon.UlanziDevice", return_value=device),
            patch("ulanzi_manager.daemon.signal.signal"),
            patch("ulanzi_manager.daemon.time.monotonic", side_effect=clock.monotonic),
            patch("ulanzi_manager.daemon.time.sleep", side_effect=sleep),
            self.assertRaisesRegex(RuntimeError, "Statistics worker failed") as raised,
        ):
            daemon.run()
        self.assertIs(failure, raised.exception.__cause__)
        self.assertEqual(1, device.close_count)
        self.assertIsNone(daemon._stats_thread)

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

            def set_buttons(self, buttons, partial=False, *, cache=True):
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

            def set_buttons(self, buttons, partial=False, *, cache=True):
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
                        content_margin=48,
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

            def set_buttons(self, buttons, partial=False, *, cache=True):
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
        daemon._send_stats_frame(daemon._render_stats_background(1.5))
        self.assertEqual((255, 0, 0), daemon.device.frame.getpixel((446, 92)))

        values["cpu"] = 50
        daemon._send_stats_frame(daemon._render_stats_background(70))
        self.assertEqual((255, 0, 0), daemon.device.frame.getpixel((446, 128)))
        self.assertEqual(empty_plot_pixel, daemon.device.frame.getpixel((50, 128)))
        with patch("ulanzi_manager.daemon.time.monotonic", return_value=70):
            daemon._configure_device()
        self.assertEqual([(70, {"cpu": 50, "mem": 75, "gpu": 25})], list(daemon.stats_history))
        values["cpu"] = 100
        daemon._send_stats_frame(daemon._render_stats_background(130))
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


class ContentMarginRenderingTests(unittest.TestCase):
    def test_stats_foreground_is_inset_without_resizing_or_darkening_background(self):
        with tempfile.TemporaryDirectory() as directory:
            background_path = Path(directory) / "background.png"
            background = Image.new("RGB", (458, 196))
            background.putdata([
                (x % 256, y % 256, (x + y) % 256)
                for y in range(196) for x in range(458)
            ])
            background.save(background_path)
            for view, layout in (("text", "columns"), ("text", "rows"), ("text", "compact"),
                                 ("htop", "columns"), ("history", "columns")):
                for margin in (16, 48):
                    with self.subTest(view=view, layout=layout, margin=margin):
                        daemon = UlanziDaemon("unused.yaml")
                        device = StatsDisplay()
                        device.clock = FakeClock(daemon)
                        daemon.device = device
                        daemon.metrics.sample = lambda: {"cpu": 75, "mem": 50, "gpu": 25}
                        style = parse_metrics_style({
                            "view": view, "layout": layout, "content_margin": 1,
                        })
                        daemon.config = Config(buttons=[ButtonConfig(
                            index=13, image=None, label="", action_type="command", action_params={},
                            action_enabled=False, display_mode="stats",
                            background_tile=str(background_path), content_margin=margin,
                            metrics_style=style,
                        )])
                        with patch("ulanzi_manager.daemon.time.monotonic", return_value=0):
                            daemon._configure_device()
                        self.assertEqual(margin, daemon.stats_style["content_margin"])
                        self.assertEqual(1, style["content_margin"])
                        self.assertIsNone(ImageChops.difference(background, daemon.stats_background).getbbox())
                        difference = ImageChops.difference(background, device.frame)
                        bbox = difference.getbbox()
                        self.assertIsNotNone(bbox)
                        width, height = ImageOps.contain(
                            Image.new("RGBA", (458, 196)), (458 - 2 * margin, 196 - 2 * margin)
                        ).size
                        left, top = (458 - width) // 2, (196 - height) // 2
                        self.assertGreaterEqual(bbox[0], left)
                        self.assertGreaterEqual(bbox[1], top)
                        self.assertLessEqual(bbox[2], left + width)
                        self.assertLessEqual(bbox[3], top + height)
                        for region in ((0, 0, 458, margin), (0, 196 - margin, 458, 196),
                                       (0, 0, margin, 196), (458 - margin, 0, 458, 196)):
                            self.assertIsNone(difference.crop(region).getbbox())

    def test_gif_padding_preserves_decoded_disposal_timing_and_original_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "animation.gif"
            tile_path = Path(directory) / "tile.png"
            palette = [0, 0, 0, 255, 0, 0, 0, 255, 0, 0, 0, 255] + [0] * (768 - 12)
            frames = []
            for index in (1, 2, 3):
                frame = Image.new("P", (90, 60), 0)
                frame.putpalette(palette)
                frame.paste(index, ((index - 1) * 30, 10, index * 30, 50))
                frames.append(frame)
            frames[0].save(
                path, save_all=True, append_images=frames[1:], optimize=False,
                transparency=0, disposal=[1, 2, 1], duration=[40, 250, 700], loop=0,
            )
            original = path.read_bytes()
            tile = Image.new("RGBA", (458, 196), (32, 64, 96, 255))
            tile.paste((200, 100, 50, 255), (0, 0, 100, 196))
            tile.save(tile_path)
            with Image.open(path) as source:
                reference = [frame.convert("RGBA").copy() for frame in ImageSequence.Iterator(source)]
            self.assertEqual(3, len(reference))
            self.assertEqual((0, 255, 0, 255), reference[1].getpixel((45, 30)))
            self.assertEqual(0, reference[2].getpixel((45, 30))[3])
            self.assertEqual((0, 0, 255, 255), reference[2].getpixel((75, 30)))
            zero_margin = _load_gif_frames(str(path))
            for source, (data, _, _) in zip(reference, zero_margin):
                with Image.open(io.BytesIO(data)) as actual:
                    self.assertEqual(source.size, actual.size)
                    self.assertEqual(source.tobytes(), actual.convert("RGBA").tobytes())
            for background_tile, color in ((str(tile_path), None), (None, "black")):
                with self.subTest(background_tile=background_tile):
                    decoded = _load_gif_frames(str(path), 20, background_tile)
                    self.assertEqual([0.1, 0.25, 0.7], [entry[1] for entry in decoded])
                    self.assertEqual(3, len({entry[2] for entry in decoded}))
                    for source, (data, _, _) in zip(reference, decoded):
                        expected = tile.copy() if background_tile else Image.new("RGBA", (458, 196), color)
                        inset = ImageOps.contain(source, (418, 156), Image.Resampling.LANCZOS)
                        expected.alpha_composite(inset, ((458 - inset.width) // 2, (196 - inset.height) // 2))
                        with Image.open(io.BytesIO(data)) as actual:
                            self.assertEqual((458, 196), actual.size)
                            self.assertEqual(expected.tobytes(), actual.convert("RGBA").tobytes())
                    self.assertEqual(original, path.read_bytes())

    def test_raw_config_margin_reaches_daemon_gif_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "animation.gif"
            config_path = Path(directory) / "config.yaml"
            Image.new("RGB", (458, 196), "red").save(
                path, save_all=True, append_images=[Image.new("RGB", (458, 196), "blue")],
                duration=[100, 250],
            )
            config_path.write_text(yaml.safe_dump({"buttons": [None] * 13 + [{
                "image": "animation.gif", "display_mode": "gif",
                "action_enabled": False, "content_margin": 48,
            }]}))
            daemon = UlanziDaemon(str(config_path))
            daemon.config = ConfigParser.load(str(config_path))
            device = StatsDisplay()
            device.clock = FakeClock(daemon)
            daemon.device = device
            daemon._configure_device()
            self.assertEqual(48, daemon.config.buttons[0].content_margin)
            self.assertEqual((0, 0, 0), device.frame.getpixel((229, 47)))
            self.assertEqual((255, 0, 0), device.frame.getpixel((229, 48)))
            self.assertEqual((0, 0, 0), device.frame.getpixel((229, 148)))
            self.assertEqual([0.1, 0.25], [frame[1] for frame in daemon.gif_frames])


if __name__ == "__main__":
    unittest.main()
