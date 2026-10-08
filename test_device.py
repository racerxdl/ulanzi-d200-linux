import io
import json
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from pathlib import Path

from PIL import Image

from ulanzi_manager.device import UlanziDevice


class DeferredFirmware:
    """Model the shared ZIP staging file while the full layout is still importing."""

    def __init__(self, error="0"):
        self.error = error
        self.displayed = {0: Image.new("RGB", (196, 196), "green")}
        self.responses = []
        self.pending_layout = None
        self.remaining = 0
        self.buffer = bytearray()
        self.full_uploads = 0
        self.received_archives = []

    def _apply(self, data):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            for key, entry in manifest.items():
                col, row = map(int, key.split("_"))
                icon = entry["ViewParam"][0].get("Icon")
                if icon:
                    self.displayed[row * 5 + col] = Image.open(
                        io.BytesIO(archive.read(icon))
                    ).convert("RGB")

    def write(self, packet):
        report_size = len(packet)
        # Match hidapi: its unnumbered report ID is removed before USB output.
        if packet[0] == 0:
            packet = packet[1:]
        if not self.remaining:
            command = struct.unpack(">H", packet[2:4])[0]
            if command == 3:
                if self.pending_layout is not None and self.error == "0":
                    self._apply(self.pending_layout)
                    self.pending_layout = None
                payload = json.dumps({"error": self.error}).encode()
                self.responses.append(b"||\x03\x03" + struct.pack("<I", len(payload)) + payload)
                return report_size
            if command not in (1, 13):
                return report_size
            self.command = command
            self.remaining = struct.unpack("<I", packet[4:8])[0]
            self.buffer = bytearray()
            if command == 13:
                # A new archive can replace the file an unfinished full import needs.
                self.pending_layout = None
            packet = packet[8:]
        data = packet[:self.remaining]
        self.buffer.extend(data)
        self.remaining -= len(data)
        if not self.remaining:
            self.received_archives.append(bytes(self.buffer))
            if self.command == 1:
                self.pending_layout = bytes(self.buffer)
                self.full_uploads += 1
                self.responses.append(b"||\x01\x0b" + struct.pack("<I", 1014) + bytes(1014))
            else:
                self._apply(bytes(self.buffer))
        return report_size

    def read(self, _size):
        return self.responses.pop(0) if self.responses else []


class UlanziDeviceTest(unittest.TestCase):
    def test_archive_preserves_icon_contents(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            buttons = {}
            originals = {}
            for index, color in enumerate(("red", "blue", "purple")):
                image_path = root / f"icon-{index}.png"
                Image.new("RGB", (196, 196), color).save(image_path)
                originals[f"icons/{image_path.name}"] = image_path.read_bytes()
                buttons[index] = {"image": str(image_path), "label": f"App {index}"}
            sent = []
            device = object.__new__(UlanziDevice)
            device.device = DeferredFirmware()
            device._send_file = sent.append
            device.set_buttons(buttons)
            with zipfile.ZipFile(io.BytesIO(sent[0])) as archive:
                self.assertIsNone(archive.testzip())
                manifest = json.loads(archive.read("manifest.json"))
                for index in range(3):
                    name = manifest[f"{index}_0"]["ViewParam"][0]["Icon"]
                    self.assertEqual(originals[name], archive.read(name))

    def test_hid_transfer_preserves_zero_and_magic_continuation_bytes(self):
        payload = bytes(4096)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
            archive.writestr("manifest.json", '{"0_0":{"ViewParam":[{}]}}')
            archive.writestr("payload.bin", payload)
        data = bytearray(buffer.getvalue())
        # Place both formerly rejected bytes inside a stored entry, then update
        # its CRC by rebuilding the actual consumer-readable ZIP.
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entry = archive.getinfo("payload.bin")
            start = entry.header_offset + 30 + len(entry.filename.encode())
        contents = bytearray(payload)
        contents[1016 - start] = 0
        contents[2040 - start] = 0x7c
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
            archive.writestr("manifest.json", '{"0_0":{"ViewParam":[{}]}}')
            archive.writestr("payload.bin", contents)
        device = object.__new__(UlanziDevice)
        firmware = DeferredFirmware()
        device.device = firmware
        device._send_file(buffer.getvalue())
        device._synchronize_firmware()
        with zipfile.ZipFile(io.BytesIO(firmware.received_archives[0])) as received:
            self.assertIsNone(received.testzip())
            self.assertEqual(contents, received.read("payload.bin"))

    def test_firmware_restart_restores_latest_saved_layout_without_ack_loop(self):
        from ulanzi_manager.daemon import UlanziDaemon

        firmware = DeferredFirmware()
        handles = []

        class Handle:
            def __init__(self):
                self.closed = False
                handles.append(self)

            def read(self, size):
                if self.closed:
                    raise OSError("closed HID handle")
                return firmware.read(size)

            def write(self, data):
                if self.closed:
                    raise OSError("closed HID handle")
                return firmware.write(data)

            def close(self):
                self.closed = True

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for name in ("red", "blue"):
                Image.new("RGB", (196, 196), name).save(root / f"{name}.png")
            config = root / "config.yaml"
            config.write_text("buttons:\n  - image: red.png\n    action_enabled: false\n")
            daemon = UlanziDaemon(str(config))
            clock = [0.0]
            crashed = [False]
            saved = "buttons:\n  - image: blue.png\n    action_enabled: false\n"

            def sleep(seconds):
                clock[0] += seconds
                if clock[0] < 0.15:
                    firmware.responses.append(b"||\x01\x03" + bytes(1020))
                if clock[0] >= 0.15 and not crashed[0]:
                    self.assertEqual((255, 0, 0), firmware.displayed[0].getpixel((98, 98)))
                    config.write_text(saved)
                    firmware.displayed[0] = Image.new("RGB", (196, 196), "green")
                    firmware.responses.extend([
                        b"||\x01\x03" + bytes(1020),
                        b"||\x01\x0b" + bytes(1020),
                    ])
                    crashed[0] = True
                if clock[0] >= 0.5:
                    daemon.request_stop()

            with (
                patch.object(UlanziDevice, "_connect", lambda device: setattr(device, "device", Handle())),
                patch.object(UlanziDaemon, "_init_obs_client"),
                patch("ulanzi_manager.daemon.signal.signal"),
                patch("ulanzi_manager.daemon.time.monotonic", side_effect=lambda: clock[0]),
                patch("ulanzi_manager.daemon.time.sleep", side_effect=sleep),
            ):
                daemon.run()

            self.assertEqual((0, 0, 255), firmware.displayed[0].getpixel((98, 98)))
            self.assertEqual(saved, config.read_text())
            self.assertEqual(2, firmware.full_uploads)
            self.assertTrue(all(handle.closed for handle in handles))

    def test_short_hid_write_is_not_reported_as_success(self):
        device = object.__new__(UlanziDevice)
        device.device = unittest.mock.Mock()
        device.device.write.return_value = -1
        with self.assertRaisesRegex(OSError, "HID write failed"):
            device.set_brightness(80)


    def test_button_fourteen_uses_wide_background_mode_and_keeps_gif(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            gif_path = Path(temp_dir) / "status.gif"
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
            sent = []
            device = object.__new__(UlanziDevice)
            device.device = DeferredFirmware()
            device._send_file = sent.append

            device.set_buttons({
                13: {"image": str(gif_path), "label": "", "state": 0}
            })

            with zipfile.ZipFile(io.BytesIO(sent[0])) as uploaded:
                manifest = __import__("json").loads(
                    uploaded.read("manifest.json")
                )
                self.assertEqual(2, manifest["3_2"]["SmallViewMode"])
                self.assertEqual(
                    "icons/status.gif",
                    manifest["3_2"]["ViewParam"][0]["Icon"],
                )
                self.assertEqual(
                    gif_path.read_bytes(),
                    uploaded.read("icons/status.gif"),
                )


    def test_button_fourteen_supports_native_statistics_mode(self):
        sent = []
        device = object.__new__(UlanziDevice)
        device.device = DeferredFirmware()
        device._send_file = sent.append

        device.set_buttons({
            13: {
                "label": "",
                "state": 0,
                "small_view_mode": 0,
            }
        })

        with zipfile.ZipFile(io.BytesIO(sent[0])) as uploaded:
            manifest = __import__("json").loads(
                uploaded.read("manifest.json")
            )
            wide = manifest["3_2"]
            self.assertEqual(0, wide["SmallViewMode"])
            self.assertNotIn("Icon", wide["ViewParam"][0])
    def test_partial_gif_frame_does_not_reset_wide_display_mode(self):
        image = io.BytesIO()
        Image.new("RGB", (458, 196), "blue").save(image, format="PNG")
        sent = []
        device = object.__new__(UlanziDevice)
        device._send_file = lambda data, command=None: sent.append(
            (data, command)
        )

        device.set_buttons({
            13: {
                "image_data": image.getvalue(),
                "image_name": "frame-blue.png",
                "state": 0,
            }
        }, partial=True)

        with zipfile.ZipFile(io.BytesIO(sent[0][0])) as uploaded:
            manifest = __import__("json").loads(uploaded.read("manifest.json"))
        self.assertNotIn("SmallViewMode", manifest["3_2"])
        self.assertEqual(13, sent[0][1])


    def test_background_mode_uses_complete_firmware_payload(self):
        sent = []
        device = object.__new__(UlanziDevice)
        device._send_command = lambda command, payload: sent.append(
            (command, payload)
        )

        device.set_small_window_data({"mode": 2})

        fields = sent[0][1].split(b"|")
        self.assertEqual([b"2", b"0", b"0"], fields[:3])
        self.assertEqual(b"0", fields[-1])

    def test_stale_reports_are_discarded_without_running_actions(self):
        class QueuedHid:
            def __init__(self):
                self.reports = [[1] * 1024, [2] * 1024]

            def read(self, _size):
                return self.reports.pop(0) if self.reports else []

        events = []
        device = object.__new__(UlanziDevice)
        device.device = QueuedHid()
        device._button_callback = events.append

        self.assertEqual(2, device.drain_input())
        self.assertIsNone(device.read_button_press())
        self.assertEqual([], events)


    def test_disconnected_hid_read_reaches_the_daemon(self):
        class DisconnectedHid:
            def read(self, _size):
                raise OSError("device disconnected")

        device = object.__new__(UlanziDevice)
        device.device = DisconnectedHid()
        device._button_callback = None

        with self.assertRaisesRegex(OSError, "device disconnected"):
            device.read_button_press()

    def test_full_layout_survives_immediate_wide_metrics_update(self):
        firmware = DeferredFirmware()
        device = object.__new__(UlanziDevice)
        device.device = firmware
        red, blue = io.BytesIO(), io.BytesIO()
        Image.new("RGB", (196, 196), "red").save(red, format="PNG")
        Image.new("RGB", (458, 196), "blue").save(blue, format="PNG")
        device.set_buttons({
            0: {"image_data": red.getvalue()},
            13: {"small_view_mode": 2},
        })
        device.set_buttons({13: {"image_data": blue.getvalue()}}, partial=True)
        self.assertEqual((255, 0, 0), firmware.displayed[0].getpixel((98, 98)))
        self.assertEqual((0, 0, 255), firmware.displayed[13].getpixel((229, 98)))

    def test_unready_firmware_does_not_replace_existing_layout(self):
        firmware = DeferredFirmware(error="1")
        device = object.__new__(UlanziDevice)
        device.device = firmware
        red = io.BytesIO()
        Image.new("RGB", (196, 196), "red").save(red, format="PNG")
        with self.assertRaisesRegex(RuntimeError, "D200"):
            device.set_buttons({0: {"image_data": red.getvalue()}})
        self.assertEqual((0, 128, 0), firmware.displayed[0].getpixel((98, 98)))

    def test_silent_firmware_times_out_without_replacing_layout(self):
        firmware = DeferredFirmware()
        firmware.read = lambda _size: []
        device = object.__new__(UlanziDevice)
        device.device = firmware
        with (
            patch("ulanzi_manager.device.time.monotonic", side_effect=[0, 0, 1000]),
            patch("ulanzi_manager.device.time.sleep"),
            self.assertRaisesRegex(TimeoutError, "D200"),
        ):
            device.set_buttons({0: {"label": "New layout"}})
        self.assertEqual((0, 128, 0), firmware.displayed[0].getpixel((98, 98)))

if __name__ == "__main__":
    unittest.main()
