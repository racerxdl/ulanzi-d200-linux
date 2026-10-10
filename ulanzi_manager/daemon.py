"""Background daemon for Ulanzi Manager"""

import hashlib
import io
import time
import logging
import signal
import threading
from collections import deque
from pathlib import Path
from typing import Optional
from PIL import Image, ImageSequence, ImageDraw, ImageFont, ImageOps

from ulanzi_manager.device import UlanziDevice, ButtonPress
from ulanzi_manager.config import ConfigParser, Config, METRICS_FONT_FILES, parse_content_margin
from ulanzi_manager.actions import ActionExecutor
from ulanzi_manager.metrics import SystemMetrics

# Setup logging
log_dir = Path.home() / '.local/share/ulanzi'
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'daemon.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

BUTTON_POLL_INTERVAL_SECONDS = 0.05
KEEPALIVE_INTERVAL_SECONDS = 1.0
METRICS_INTERVAL_SECONDS = 1.5
MIN_GIF_FRAME_SECONDS = 0.1
MAX_GIF_FRAME_SECONDS = 4.0


def _load_gif_frames(path: str, content_margin=0, background_tile=None):
    """Decode composited GIF frames, preserving source disposal and timing."""
    content_margin = parse_content_margin(content_margin)
    frames = []
    background = None
    if content_margin or background_tile:
        if background_tile:
            with Image.open(background_tile) as tile:
                background = ImageOps.fit(tile.convert('RGBA'), (458, 196))
        else:
            background = Image.new('RGBA', (458, 196), 'black')
    with Image.open(path) as image:
        for frame in ImageSequence.Iterator(image):
            duration = min(
                MAX_GIF_FRAME_SECONDS,
                max(
                    MIN_GIF_FRAME_SECONDS,
                    int(frame.info.get('duration', 100)) / 1000,
                ),
            )
            output = io.BytesIO()
            foreground = frame.convert('RGBA')
            if background is not None:
                foreground = ImageOps.contain(
                    foreground,
                    (458 - 2 * content_margin, 196 - 2 * content_margin),
                    Image.Resampling.LANCZOS,
                )
                composed = background.copy()
                position = ((458 - foreground.width) // 2, (196 - foreground.height) // 2)
                composed.alpha_composite(foreground, position)
                foreground = composed
            foreground.save(output, format='PNG')
            image_data = output.getvalue()
            digest = hashlib.sha256(image_data).hexdigest()[:16]
            frames.append((
                image_data,
                duration,
                f'button-14-{digest}.png',
            ))
    if len(frames) < 2:
        raise ValueError("Button 14 GIF must contain at least two frames")
    return frames



class UlanziDaemon:
    """Background daemon for Ulanzi device"""

    def __init__(self, config_path: str):
        """Initialize daemon"""
        self.config_path = config_path
        self.config: Optional[Config] = None
        self.device: Optional[UlanziDevice] = None
        self.executor: Optional[ActionExecutor] = None
        self.running = False
        self.obs_client = None
        self.small_window_mode = 1
        self.gif_frames = []
        self.gif_frame_index = 0
        self.metrics = SystemMetrics()
        self.stats_background = None
        self.stats_history = deque(maxlen=int(60 / METRICS_INTERVAL_SECONDS) + 1)
        self.stats_next_update = None
        self._stats_thread = None
        self._stats_stop = threading.Event()
        self._stats_requested = threading.Event()
        self._stats_lock = threading.Lock()
        self._stats_result = None

    def start(self):
        """Start the daemon"""
        logger.info("Starting Ulanzi daemon...")

        try:
            # Load configuration
            ConfigParser.ensure_default(self.config_path)
            self.config = ConfigParser.load(self.config_path)

            # Validate configuration
            errors = ConfigParser.validate(self.config)
            if errors:
                logger.error("Configuration errors:")
                for error in errors:
                    logger.error(f"  - {error}")
                return False

            # Connect to device
            self.device = UlanziDevice()

            # Initialize OBS client if configured
            self._init_obs_client()

            # Initialize action executor
            self.executor = ActionExecutor(self.obs_client)

            # Configure device
            self._configure_device()
            discarded_reports = self.device.drain_input()
            if discarded_reports:
                logger.info(
                    f"Discarded {discarded_reports} stale HID report(s)"
                )
            self.device.set_button_callback(self._on_button_press)

            self.running = True
            self._start_stats_worker()
            logger.info("Daemon started successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to start daemon: {e}")
            return False

    def request_stop(self, *_):
        """Request a graceful stop without closing HID from a signal handler."""
        logger.info("Stop requested")
        self.running = False

    def stop(self):
        """Release resources. Safe to call more than once."""
        self.running = False
        self._stop_stats_worker()
        device, self.device = self.device, None
        obs_client, self.obs_client = self.obs_client, None

        if device is None and obs_client is None:
            return

        logger.info("Stopping daemon...")
        if device:
            device.close()

        if obs_client:
            try:
                obs_client.disconnect()
            except Exception:
                logger.debug("Failed to disconnect from OBS", exc_info=True)

        logger.info("Daemon stopped")

    def run(self):
        """Run the daemon main loop."""
        if not self.start():
            self.stop()
            raise RuntimeError("Unable to start Ulanzi daemon")

        signal.signal(signal.SIGTERM, self.request_stop)
        signal.signal(signal.SIGINT, self.request_stop)

        next_keepalive = 0.0
        next_gif_frame = (
            time.monotonic() + self.gif_frames[0][1]
            if self.gif_frames else float('inf')
        )
        try:
            while self.running:
                self.device.read_button_press()
                if self.device.configuration_requested:
                    logger.warning("Firmware requested configuration; restoring saved layout")
                    self.stop()
                    if not self.start():
                        raise RuntimeError("Unable to restore configuration after firmware restart")
                    next_keepalive = 0.0
                    next_gif_frame = (
                        time.monotonic() + self.gif_frames[0][1]
                        if self.gif_frames else float('inf')
                    )
                    continue

                now = time.monotonic()
                if now >= next_keepalive:
                    self.device.set_small_window_data(
                        {'mode': self.small_window_mode}
                    )
                    next_keepalive = now + KEEPALIVE_INTERVAL_SECONDS

                if self.stats_background is not None and now >= self.stats_next_update:
                    self.stats_next_update = now + METRICS_INTERVAL_SECONDS
                    self._stats_requested.set()
                self._publish_stats_result()

                if now >= next_gif_frame:
                    self.gif_frame_index = (
                        self.gif_frame_index + 1
                    ) % len(self.gif_frames)
                    image_data, duration, image_name = self.gif_frames[
                        self.gif_frame_index
                    ]
                    self.device.set_buttons({
                        13: {
                            'image_data': image_data,
                            'image_name': image_name,
                            'label': '',
                            'state': 0,
                        }
                    }, partial=True)
                    next_gif_frame = now + duration

                time.sleep(BUTTON_POLL_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception:
            logger.exception("Daemon error")
            raise
        finally:
            self.stop()

    def _init_obs_client(self):
        """Initialize OBS WebSocket client"""
        if not any(button.action_enabled and button.action_type == 'obs' for button in self.config.buttons):
            logger.info("No OBS actions configured; skipping OBS connection")
            return

        try:
            import obsws_python as obs

            self.obs_client = obs.ReqClient(
                host=self.config.obs_host,
                port=self.config.obs_port,
                password=self.config.obs_password,
                timeout=3
            )
            logger.info(f"Connected to OBS at {self.config.obs_host}:{self.config.obs_port}")
        except ImportError:
            logger.warning("obsws-python not installed, OBS features disabled")
        except ConnectionRefusedError:
            logger.warning(f"Could not connect to OBS at {self.config.obs_host}:{self.config.obs_port} - is it running?")
        except Exception as e:
            logger.warning(f"Failed to connect to OBS: {type(e).__name__}: {e}")

    def _start_stats_worker(self):
        """Run one producer; the polling thread remains the sole HID writer."""
        if self.stats_background is None or self._stats_thread is not None:
            return
        self._stats_stop.clear()
        self._stats_requested.clear()
        worker = threading.Thread(target=self._stats_worker, name='ulanzi-stats')
        worker.start()
        self._stats_thread = worker

    def _stop_stats_worker(self):
        """Join before resetting any rendering state or replacing the device."""
        self._stats_stop.set()
        self._stats_requested.set()
        if self._stats_thread is not None:
            self._stats_thread.join()
            self._stats_thread = None
        with self._stats_lock:
            self._stats_result = None

    def _stats_worker(self):
        try:
            while True:
                self._stats_requested.wait()
                self._stats_requested.clear()
                if self._stats_stop.is_set():
                    return
                now = time.monotonic()
                frame = self._render_stats_background(now)
                with self._stats_lock:
                    if self._stats_stop.is_set():
                        return
                    # A slow consumer needs only the latest complete frame.
                    self._stats_result = (frame, None)
        except BaseException as error:
            with self._stats_lock:
                if not self._stats_stop.is_set():
                    self._stats_result = (None, error)

    def _publish_stats_result(self):
        with self._stats_lock:
            result, self._stats_result = self._stats_result, None
        if result is None:
            return
        frame, error = result
        if error is not None:
            raise RuntimeError("Statistics worker failed") from error
        self._send_stats_frame(frame)

    def _send_stats_frame(self, frame):
        self.device.set_buttons({13: {
            'image_data': frame, 'image_name': 'stats-background.png',
            'label': '', 'state': 0,
        }}, partial=True, cache=False)

    def _render_stats_background(self, now):
        """Collect and render, without touching the device."""
        metrics = self.metrics.sample()
        if self.stats_style['view'] == 'history':
            self.stats_history.append((now, metrics))
        image = self.stats_background.copy()
        style = self.stats_style
        margin = style.get('content_margin', 0)
        foreground = Image.new('RGBA', image.size) if margin else image
        draw = ImageDraw.Draw(foreground, 'RGBA')
        font, label_font = self.stats_fonts
        if style['view'] == 'history':
            self._draw_history_grid(draw)
        for index, (key, label) in enumerate((('cpu', 'CPU'), ('mem', 'RAM'), ('gpu', 'GPU'))):
            if style['view'] == 'htop':
                self._draw_htop_metric(draw, index, key, label, metrics[key])
                continue
            if style['view'] == 'history':
                self._draw_history_metric(draw, now, index, key, label, metrics[key])
                continue
            if style['layout'] == 'rows':
                y = int(16 + (index + 0.5) * (image.height - 32) / 3)
                value_position, value_anchor = (image.width - 24, y), "rm"
                label_position, label_anchor = (24, y), "lm"
            else:
                x = int((index + 0.5) * image.width / 3)
                if style['layout'] == 'compact':
                    value_position = (x, 110)
                    label_position = (x, 78)
                else:
                    value_position = (x, 98 - (label_font.size + 14) / 2)
                    label_position = (x, 98 + (font.size + 14) / 2)
                value_anchor = label_anchor = "mm"
            draw.text(value_position, f"{metrics[key]}%", font=font, anchor=value_anchor,
                      fill=style['colors'][key]['color'], stroke_width=2, stroke_fill="black")
            draw.text(label_position, label, font=label_font, anchor=label_anchor,
                      fill=style['colors'][key]['label_color'], stroke_width=2, stroke_fill="black")
        if margin:
            foreground = ImageOps.contain(
                foreground,
                (image.width - 2 * margin, image.height - 2 * margin),
                Image.Resampling.LANCZOS,
            )
            position = ((image.width - foreground.width) // 2, (image.height - foreground.height) // 2)
            image.paste(foreground, position, foreground)
        output = io.BytesIO()
        image.save(output, format='PNG')
        return output.getvalue()

    def _draw_htop_metric(self, draw, index, key, label, value):
        font, label_font = self.stats_fonts
        palette = self.stats_style['colors'][key]
        y = int((index + 0.5) * 196 / 3)
        left, right = 104, 446
        draw.rounded_rectangle((left, y - 23, right, y + 23), radius=4,
                               fill=(0, 0, 0, 190), outline=(255, 255, 255, 100))
        # Reserve enough room for 100% at the selected size, regardless of current value.
        end = right - 16 - int(self.stats_style['size'] * 3.2)
        count = max(1, (end - left - 8) // 6)
        filled = round(value * count / 100)
        for segment in range(filled):
            x = left + 8 + segment * 6
            draw.rectangle((x, y - 15, x + 3, y + 15), fill=palette['color'])
        draw.text((12, y), label, font=label_font, anchor="lm",
                  fill=palette['label_color'], stroke_width=2, stroke_fill="black")
        draw.text((right - 8, y), f"{value}%", font=font, anchor="rm",
                  fill=palette['color'], stroke_width=2, stroke_fill="black")

    def _draw_history_grid(self, draw):
        left, right, top, bottom = 12, 446, 92, 164
        draw.rectangle((left, top, right, bottom), fill=(0, 0, 0, 180))
        for percent in (0, 50, 100):
            y = bottom - percent * (bottom - top) / 100
            draw.line((left, y, right, y), fill=(255, 255, 255, 70), width=1)
        draw.text((left, 177), "-60s", font=self.stats_axis_font, anchor="lm",
                  fill="white", stroke_width=1, stroke_fill="black")
        draw.text((right, 177), "0s", font=self.stats_axis_font, anchor="rm",
                  fill="white", stroke_width=1, stroke_fill="black")

    def _draw_history_metric(self, draw, now, index, key, label, value):
        font, label_font = self.stats_fonts
        palette = self.stats_style['colors'][key]
        center = int((index + 0.5) * 458 / 3)
        left, right = 12, 446
        top, bottom = 92, 164
        draw.text((center, 22), label, font=label_font, anchor="mm",
                  fill=palette['label_color'], stroke_width=2, stroke_fill="black")
        draw.text((center, 58), f"{value}%", font=font, anchor="mm",
                  fill=palette['color'], stroke_width=2, stroke_fill="black")
        draw.line((center - 12, 83, center + 12, 83), fill=palette['line_color'], width=3)
        points = [
            (right - (now - timestamp) * (right - left) / 60,
             bottom - sample[key] * (bottom - top) / 100)
            for timestamp, sample in self.stats_history
            if 0 <= now - timestamp <= 60
        ]
        if len(points) > 1:
            draw.line(points, fill=palette['line_color'], width=2, joint="curve")
        if points:
            x, y = points[-1]
            draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=palette['line_color'])

    def _configure_device(self):
        """Configure device with settings from config."""
        self._stop_stats_worker()
        try:
            self.device.set_brightness(self.config.brightness)

            if self.config.label_style:
                self.device.set_label_style(self.config.label_style)

            button_dict = {}
            self.small_window_mode = 1
            self.gif_frames = []
            self.gif_frame_index = 0
            wide_background_image = None
            self.stats_background = None
            self.stats_history.clear()
            self.stats_next_update = None
            for button in self.config.buttons:
                button_data = {
                    'image': button.image,
                    'label': button.label,
                    'state': button.state
                }
                if button.index == 13:
                    if button.display_mode == 'gif' and button.image:
                        self.small_window_mode = 2
                        self.gif_frames = _load_gif_frames(
                            button.image, button.content_margin, button.background_tile
                        )
                        # Select background mode first; animate decoded PNG
                        # frames only after the full layout import is complete.
                        button_data.pop('image')
                        button_data['small_view_mode'] = 2
                    elif button.display_mode == 'background' and button.image:
                        self.small_window_mode = 2
                        wide_background_image = button.image
                        button_data.pop('image')
                        button_data['small_view_mode'] = 2
                    elif button.display_mode == 'stats':
                        self.small_window_mode = 2
                        background = button.background_tile or button.image
                        if background and background.lower().endswith('.png'):
                            with Image.open(background) as image:
                                self.stats_background = ImageOps.fit(image.convert('RGB'), (458, 196))
                        else:
                            self.stats_background = Image.new('RGB', (458, 196), 'black')
                        self.stats_style = {
                            **button.metrics_style, 'content_margin': button.content_margin,
                        }
                        size = self.stats_style['size']
                        compact_text = self.stats_style['view'] == 'text' and self.stats_style['layout'] == 'compact'
                        label_ratio = 0.45 if compact_text else 0.73
                        font_name = METRICS_FONT_FILES[self.stats_style['font_family']][self.stats_style['font_style']]
                        font_path = str(Path(__file__).parent / 'static' / 'fonts' / font_name)
                        self.stats_fonts = (
                            ImageFont.truetype(font_path, size),
                            ImageFont.truetype(font_path, max(12, int(size * label_ratio))),
                        )
                        if self.stats_style['font_family'] in ('ubuntu', 'ubuntu-mono'):
                            # These files are variable fonts; Pillow otherwise uses regular weight.
                            weight = 700 if self.stats_style['font_style'] in ('bold', 'bold-italic') else 400
                            axes = [100, weight] if self.stats_style['font_family'] == 'ubuntu' else [weight]
                            for font in self.stats_fonts:
                                font.set_variation_by_axes(axes)
                        self.stats_axis_font = ImageFont.truetype(font_path, 12)
                        button_data.pop('image')
                        button_data['small_view_mode'] = 2
                button_dict[button.index] = button_data

            if button_dict:
                self.device.set_buttons(button_dict)
                if self.small_window_mode == 2:
                    self.device.set_small_window_data({'mode': 2})
                    if self.stats_background is not None:
                        now = time.monotonic()
                        self.stats_next_update = now + METRICS_INTERVAL_SECONDS
                        self._send_stats_frame(self._render_stats_background(now))
                if self.gif_frames:
                    image_data, _, image_name = self.gif_frames[0]
                    self.device.set_buttons({
                        13: {
                            'image_data': image_data,
                            'image_name': image_name,
                            'label': '',
                            'state': 0,
                        }
                    }, partial=True)
                elif wide_background_image:
                    self.device.set_buttons({
                        13: {
                            'image': wide_background_image,
                            'label': '',
                            'state': 0,
                        }
                    }, partial=True)

            if self.small_window_mode != 2:
                self.device.set_small_window_data(
                    {'mode': self.small_window_mode}
                )

            logger.info("Device configured successfully")
        except Exception:
            logger.exception("Failed to configure device")
            raise

    def _on_button_press(self, button: ButtonPress):
        """Handle a button event and execute once when the button is pressed."""
        event = "pressed" if button.pressed else "released"
        logger.info(f"Button {button.index} {event} (state={button.state})")
        if not button.pressed:
            return

        button_config = next(
            (configured for configured in self.config.buttons
             if configured.index == button.index),
            None
        )
        if not button_config:
            logger.warning(f"No config for button {button.index}")
            return
        if not button_config.action_enabled:
            logger.info(f"Button {button.index} has no action configured")
            return

        logger.info(
            f"Executing action: {button_config.action_type} - "
            f"{button_config.label}"
        )
        if self.executor:
            self.executor.execute(
                button_config.action_type,
                button_config.action_params
            )


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Ulanzi D200 daemon')
    parser.add_argument('config', help='Path to configuration file')
    parser.add_argument('--log-level', default='INFO', help='Logging level')
    args = parser.parse_args()

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))

    # Create and run daemon
    daemon = UlanziDaemon(args.config)
    daemon.run()


if __name__ == '__main__':
    main()
