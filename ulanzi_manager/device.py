"""USB device communication for Ulanzi D200"""

import hashlib
import struct
import io
import zipfile
import json
import logging
import time
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Optional, Callable
from dataclasses import dataclass
from enum import IntEnum

try:
    import hid
except ImportError:
    hid = None

logger = logging.getLogger(__name__)

# USB IDs
VENDOR_ID = 0x2207
PRODUCT_ID = 0x0019

# Retain reusable GIF/layout archives, never an unbounded stream of images.
BUTTON_ARCHIVE_CACHE_BYTES = 16 * 1024 * 1024
BUTTON_ARCHIVE_CACHE_ENTRIES = 128

# Command protocols
class CommandProtocol(IntEnum):
    OUT_SET_BUTTONS = 0x0001
    OUT_GET_BASE = 0x0003
    OUT_SET_SMALL_WINDOW_DATA = 0x0006
    OUT_SET_BRIGHTNESS = 0x000a
    OUT_SET_LABEL_STYLE = 0x000b
    OUT_PARTIALLY_UPDATE_BUTTONS = 0x000d
    IN_BUTTON = 0x0101
    IN_BUTTON_2 = 0x0102
    IN_CONFIGURATION_REQUEST = 0x010b
    IN_DEVICE_INFO = 0x0303


@dataclass
class ButtonPress:
    """Button press event"""
    index: int
    pressed: bool
    state: int


class UlanziDevice:
    """Ulanzi D200 device controller"""

    PACKET_SIZE = 1024
    HEADER = b'\x7c\x7c'

    def __init__(self, device_path: Optional[str] = None):
        """Initialize device connection"""
        if hid is None:
            raise ImportError("hidapi not installed. Run: pip install hidapi")

        self.device = None
        self.device_path = device_path
        self._button_callback: Optional[Callable[[ButtonPress], None]] = None
        self.configuration_requested = False
        self._connect()

    def _connect(self):
        """Connect to device"""
        if self.device_path:
            self.device = hid.device()
            self.device.open_path(self.device_path.encode())
        else:
            # Find device by vendor/product ID
            devices = hid.enumerate(VENDOR_ID, PRODUCT_ID)
            if not devices:
                raise RuntimeError(
                    f"Ulanzi D200 device not found (VID: {VENDOR_ID:04x}, PID: {PRODUCT_ID:04x})"
                )
            device_info = next(
                (
                    candidate for candidate in devices
                    if candidate.get('interface_number') == 0
                ),
                devices[0]
            )
            self.device = hid.device()
            self.device.open_path(device_info['path'])

        self.device.set_nonblocking(True)
        logger.info("Connected to Ulanzi D200 device")

    def close(self):
        """Close device connection. Safe to call more than once."""
        device, self.device = self.device, None
        if device:
            device.close()
            logger.info("Disconnected from device")

    def drain_input(self, limit: int = 256) -> int:
        """Discard reports queued before actions become active."""
        if not self.device:
            return 0

        discarded = 0
        for _ in range(limit):
            data = self.device.read(self.PACKET_SIZE)
            if not data:
                break
            discarded += 1
        return discarded

    def set_button_callback(self, callback: Callable[[ButtonPress], None]):
        """Set callback for button presses"""
        self._button_callback = callback

    def read_button_press(self) -> Optional[ButtonPress]:
        """Read one button report without hiding transport failures."""
        if not self.device:
            return None

        # A hidapi handle remains bound to the removed USB device after a
        # power cycle. Let read failures reach the daemon so systemd starts a
        # fresh process, opens the new device, and reapplies the saved layout.
        data = self.device.read(self.PACKET_SIZE)
        if not data or len(data) < 8:
            return None

        header = bytes(data[0:2])
        if header != self.HEADER:
            return None

        command = struct.unpack('>H', bytes(data[2:4]))[0]
        if command == CommandProtocol.IN_CONFIGURATION_REQUEST:
            # Full-upload font/ZIP ACKs are consumed by the post-upload barrier.
            # An unsolicited request during normal operation means the firmware
            # UI needs its saved configuration again (e.g. after a hot restart).
            self.configuration_requested = True
            return None
        if command not in (
            CommandProtocol.IN_BUTTON,
            CommandProtocol.IN_BUTTON_2
        ):
            return None

        button_data = bytes(data[8:12])
        state = button_data[0]
        index = button_data[1]
        pressed = button_data[3] == 0x01

        button_press = ButtonPress(index=index, pressed=pressed, state=state)
        if self._button_callback:
            self._button_callback(button_press)
        return button_press

    def set_brightness(self, brightness: int):
        """Set display brightness (0-100)"""
        brightness = max(0, min(100, brightness))
        payload = str(brightness).encode('ascii')
        self._send_command(CommandProtocol.OUT_SET_BRIGHTNESS, payload)
        logger.debug(f"Set brightness to {brightness}%")

    def set_label_style(self, style: Dict):
        """Set label styling for buttons"""
        default_style = {
            'Align': 'bottom',
            'Color': 0xFFFFFF,
            'FontName': 'Roboto',
            'ShowTitle': True,
            'Size': 10,
            'Weight': 80,
        }
        default_style.update(style)
        payload = json.dumps(default_style).encode('utf-8')
        self._send_command(CommandProtocol.OUT_SET_LABEL_STYLE, payload)
        logger.debug("Set label style")

    def set_small_window_data(self, data: Dict):
        """Set small window data (status display)"""
        from datetime import datetime

        mode = data.get('mode', 1)  # 0=STATS, 1=CLOCK, 2=BACKGROUND
        cpu = data.get('cpu', 0)
        mem = data.get('mem', 0)
        gpu = data.get('gpu', 0)
        time_str = data.get('time', datetime.now().strftime('%H:%M:%S'))
        payload = f'{mode}|{cpu}|{mem}|{time_str}|{gpu}'.encode('utf-8')
        self._send_command(CommandProtocol.OUT_SET_SMALL_WINDOW_DATA, payload)

    def _synchronize_firmware(self):
        """Use GETBASE as a barrier before reusing the firmware's shared ZIP file."""
        self.drain_input()
        self._send_command(CommandProtocol.OUT_GET_BASE, b'')
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            data = bytes(self.device.read(self.PACKET_SIZE))
            if (
                len(data) >= 8 and data[:2] == self.HEADER
                and struct.unpack('>H', data[2:4])[0] == CommandProtocol.IN_DEVICE_INFO
            ):
                try:
                    info = json.loads(data[8:].split(b'\x00', 1)[0])
                except (ValueError, UnicodeDecodeError) as error:
                    raise RuntimeError("Invalid D200 firmware response") from error
                if not isinstance(info, dict) or info.get('error') not in (0, '0'):
                    raise RuntimeError(f"D200 firmware is not ready: {info}")
                return
            time.sleep(0.01)
        raise TimeoutError("D200 firmware did not respond to synchronization")

    def set_buttons(
        self, buttons: Dict[int, Dict], partial: bool = False, *, cache: bool = True
    ) -> bool:
        """Update buttons; disable archive reuse for one-off statistics frames."""
        manifest = {}
        icons = {}

        for idx, config in buttons.items():
            row = idx // 5
            col = idx % 5
            key = f"{col}_{row}"
            button_data = {
                'State': config.get('state', 0),
                'ViewParam': [{}],
            }
            if idx == 13 and not partial:
                # Slot 3_2 is the 458×196 information display. Its native
                # modes are statistics (0), clock (1), and background (2).
                button_data['SmallViewMode'] = int(
                    config.get('small_view_mode', 2)
                )

            if config:
                if idx != 13 and 'label' in config:
                    button_data['ViewParam'][0]['Text'] = config['label']

                image_data = config.get('image_data')
                image_path = config.get('image')
                if image_data is not None:
                    icon_name = config.get('image_name', f'button-{idx}.png')
                    archive_path = f'icons/{icon_name}'
                    icons[archive_path] = image_data
                    button_data['ViewParam'][0]['Icon'] = archive_path
                elif image_path:
                    image_path_obj = Path(image_path)
                    if image_path_obj.exists():
                        icon_name = image_path_obj.name
                        archive_path = f'icons/{icon_name}'
                        icons[archive_path] = image_path_obj.read_bytes()
                        button_data['ViewParam'][0]['Icon'] = archive_path
                        logger.debug(
                            f"Added image for button {idx}: {image_path}"
                        )
                    else:
                        logger.warning(
                            f"Image not found for button {idx}: {image_path}"
                        )

            manifest[key] = button_data

        manifest_data = json.dumps(
            manifest,
            sort_keys=True,
            separators=(',', ':')
        )
        logger.debug(f"Manifest: {json.dumps(manifest, indent=2)}")

        cached_archive = None
        if cache:
            archive_cache = getattr(self, '_button_archive_cache', None)
            if archive_cache is None:
                archive_cache = self._button_archive_cache = OrderedDict()
                self._button_archive_cache_bytes = 0
            cache_digest = hashlib.sha256()
            cache_digest.update(b'partial' if partial else b'full')
            cache_digest.update(manifest_data.encode('utf-8'))
            for archive_path in sorted(icons):
                cache_digest.update(archive_path.encode('utf-8'))
                cache_digest.update(b'\0')
                cache_digest.update(icons[archive_path])
            cache_key = cache_digest.digest()
            cached_archive = archive_cache.get(cache_key)

        if cached_archive is not None:
            archive_cache.move_to_end(cache_key)
            zip_data = cached_archive
        else:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(
                zip_buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=1
            ) as zf:
                zf.writestr('manifest.json', manifest_data)
                for archive_path, image_data in icons.items():
                    zf.writestr(archive_path, image_data)
            zip_data = zip_buffer.getvalue()
            if cache and len(zip_data) <= BUTTON_ARCHIVE_CACHE_BYTES:
                while archive_cache and (
                    self._button_archive_cache_bytes + len(zip_data) > BUTTON_ARCHIVE_CACHE_BYTES
                    or len(archive_cache) >= BUTTON_ARCHIVE_CACHE_ENTRIES
                ):
                    _, evicted = archive_cache.popitem(last=False)
                    self._button_archive_cache_bytes -= len(evicted)
                archive_cache[cache_key] = zip_data
                self._button_archive_cache_bytes += len(zip_data)

        if partial:
            self._send_file(
                zip_data,
                CommandProtocol.OUT_PARTIALLY_UPDATE_BUTTONS
            )
        else:
            self._synchronize_firmware()
            self._send_file(zip_data)
            self._synchronize_firmware()
        log = logger.debug if partial else logger.info
        log(
            f"Set {len(buttons)} button(s) with {len(icons)} image(s)"
        )
        return True

    def _send_file(
        self,
        data: bytes,
        command: CommandProtocol = CommandProtocol.OUT_SET_BUTTONS
    ):
        """Send file data in chunks."""
        chunk_size = 1024
        file_size = len(data)

        # First chunk with header (1016 bytes of data)
        first_chunk = data[:chunk_size - 8]
        packet = self._build_packet(
            command,
            first_chunk.ljust(chunk_size - 8, b'\x00'),
            file_size
        )
        packets = [packet]

        # Remaining chunks (raw, no header)
        for i in range(chunk_size - 8, len(data), chunk_size):
            chunk = data[i:i + chunk_size]
            chunk = chunk.ljust(chunk_size, b'\x00')
            packets.append(chunk)

        # Write all packets at once
        for packet in packets:
            self._write_report(packet)

        logger.debug(f"Sent {file_size} bytes in {len(packets)} chunks")

    def _send_command(self, command: CommandProtocol, payload: bytes):
        """Send command to device"""
        packet = self._build_packet(command, payload, len(payload))
        self._write_report(packet)

    def _write_report(self, packet: bytes):
        # hidapi requires Report ID 0 for this unnumbered interface. The ID is
        # stripped by the backend; all 1024 protocol bytes reach the USB device.
        report = b'\x00' + packet
        written = self.device.write(report)
        if written != len(report):
            raise OSError(f"D200 HID write failed: {written}/{len(report)} bytes")

    def _build_packet(self, command: CommandProtocol, data: bytes, length: int) -> bytes:
        """Build USB packet"""
        packet = bytearray(self.PACKET_SIZE)

        # Header
        packet[0:2] = self.HEADER

        # Command protocol
        packet[2:4] = struct.pack('>H', command)

        # Length (big-endian)
        packet[4:8] = struct.pack('<I', length)

        # Data
        packet[8:8 + len(data)] = data

        return bytes(packet)
