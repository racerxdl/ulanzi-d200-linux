import base64
import errno
import io
import json
import socket
import tempfile
import struct
import threading
import unittest
from contextlib import contextmanager
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import yaml
from PIL import Image, ImageChops

from ulanzi_manager.web import IPv6HTTPServer, RequestHandler, ValidationError, WebApp


class WebAppTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.icons = self.root / "icons"
        self.icons.mkdir()
        Image.new("RGB", (196, 196), "#ff6b35").save(self.icons / "default.png")
        self.config_path = self.root / "config.yaml"
        self.config_path.write_text(
            yaml.safe_dump(
                {
                    "brightness": 80,
                    "label_style": {"Align": "bottom", "Color": 0xFFFFFF, "ShowTitle": True},
                    "obs": {"host": "localhost", "port": 4444, "password": None},
                    "buttons": [
                        {
                            "image": "./icons/default.png",
                            "label": "Teste",
                            "action": "command",
                            "params": {"cmd": "true"},
                        }
                    ] + [None] * 13,
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        self.app = WebApp(self.config_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_first_run_http_config_can_be_read_and_saved_without_icons(self):
        from ulanzi_manager.config import ConfigParser

        path = self.root / "new" / "profile" / "config.yaml"
        self.app = WebApp(path)
        with self._http_server() as server:
            status, config = self._http_request(server, "GET", "/api/config")
            self.assertEqual(200, status)
            self.assertEqual(14, len(config["buttons"]))
            self.assertFalse(any(button["enabled"] for button in config["buttons"][:13]))
            self.assertEqual("stats", config["buttons"][13]["display_mode"])
            self.assertFalse(any(
                button["enabled"] and button["action_enabled"] for button in config["buttons"]
            ))
            config["brightness"] = 62
            status, saved = self._http_request(server, "PUT", "/api/config", config)
            self.assertEqual(200, status)
            self.assertEqual(62, saved["brightness"])
        loaded = ConfigParser.load(str(path))
        self.assertEqual([], ConfigParser.validate(loaded))
        self.assertEqual(62, loaded.brightness)

    def test_web_start_preserves_existing_config_comments_and_values(self):
        original = b"# Keep this comment\n" + self.config_path.read_bytes()
        self.config_path.write_bytes(original)
        self.app = WebApp(self.config_path)
        with self._http_server() as server:
            status, config = self._http_request(server, "GET", "/api/config")
            self.assertEqual(200, status)
            self.assertEqual(80, config["brightness"])
            self.assertEqual("Teste", config["buttons"][0]["label"])
        self.assertEqual(original, self.config_path.read_bytes())

    @contextmanager
    def _http_server(self, host="127.0.0.1", server_type=ThreadingHTTPServer):
        try:
            server = server_type((host, 0), RequestHandler)
        except OSError as exc:
            if host == "::1" and exc.errno in {
                errno.EAFNOSUPPORT, errno.EPROTONOSUPPORT, errno.EADDRNOTAVAIL,
            }:
                self.skipTest(f"IPv6 loopback unavailable: {exc}")
            raise
        server.app = self.app
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

    def _http_request(self, server, method, path, payload=None, headers=None):
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request_headers = {"Content-Type": "application/json"} if body is not None else {}
        request_headers.update(headers or {})
        connection = HTTPConnection(server.server_address[0], server.server_port, timeout=15)
        try:
            connection.request(method, path, body=body, headers=request_headers)
            response = connection.getresponse()
            result = response.read()
            if response.getheader("Content-Type", "").startswith("application/json"):
                result = json.loads(result)
            return response.status, result
        finally:
            connection.close()

    def _png_upload_bytes(self, dimension):
        output = io.BytesIO()
        Image.new("RGB", (dimension, dimension), "#2463eb").save(
            output, format="PNG", compress_level=0,
        )
        return output.getvalue()

    def _animated_gif_with_metadata(self, size):
        output = io.BytesIO()
        frames = [Image.new("RGB", (32, 32), color) for color in ("red", "blue")]
        frames[0].save(
            output, format="GIF", save_all=True, append_images=frames[1:],
            duration=100, loop=0,
        )
        image_bytes = output.getvalue()
        # GIF application metadata uses length-prefixed blocks of at most 255 bytes.
        # Keep all raster data and the trailer intact while exercising the file limit.
        block_count, remainder = divmod(size - len(image_bytes) - 15, 256)
        blocks = (b"\xff" + b"\0" * 255) * block_count
        if remainder > 1:
            blocks += bytes([remainder - 1]) + b"\0" * (remainder - 1)
        metadata = b"\x21\xff\x0bUPLOADSIZE!" + blocks + b"\0"
        return image_bytes[:-1] + metadata + image_bytes[-1:]

    def test_http_upload_accepts_near_eight_mib_images(self):
        png = self._png_upload_bytes(1670)
        gif = self._animated_gif_with_metadata(8 * 1024 * 1024 - 16)
        with self._http_server() as server:
            for path, image_bytes, wide in (
                ("/api/icons", png, False),
                ("/api/mosaic", png, False),
                ("/api/icons", gif, True),
            ):
                with self.subTest(path=path, wide=wide):
                    self.assertGreater(len(image_bytes), 8 * 1024 * 1024 - 64 * 1024)
                    self.assertLessEqual(len(image_bytes), 8 * 1024 * 1024)
                    status, response = self._http_request(server, "POST", path, {
                        "name": "near-limit.gif" if wide else "near-limit.png",
                        "data": base64.b64encode(image_bytes).decode("ascii"),
                        "wide": wide,
                    })
                    self.assertEqual(201, status, response)
                    filenames = response.get("filenames", [response.get("filename")])
                    self.assertTrue(filenames)
                    for filename in filenames:
                        status, rendered = self._http_request(
                            server, "GET", f"/api/icons/{filename}",
                        )
                        self.assertEqual(200, status)
                        with Image.open(io.BytesIO(rendered)) as image:
                            image.load()
                            if wide:
                                self.assertEqual(2, image.n_frames)
                                self.assertEqual((458, 196), image.size)
                            else:
                                self.assertEqual((196, 196), image.size)

    def test_http_upload_rejects_decoded_images_over_eight_mib(self):
        png = self._png_upload_bytes(1675)
        gif = self._animated_gif_with_metadata(8 * 1024 * 1024 + 4096)
        original_icons = set(self.icons.iterdir())
        original_config = self.config_path.read_bytes()
        with self._http_server() as server:
            for path, image_bytes, wide in (
                ("/api/icons", png, False),
                ("/api/mosaic", png, False),
                ("/api/icons", gif, True),
            ):
                with self.subTest(path=path, wide=wide):
                    self.assertGreater(len(image_bytes), 8 * 1024 * 1024)
                    status, response = self._http_request(server, "POST", path, {
                        "name": "over-limit.gif" if wide else "over-limit.png",
                        "data": base64.b64encode(image_bytes).decode("ascii"),
                        "wide": wide,
                    })
                    self.assertEqual(400, status, response)
                    self.assertEqual(original_icons, set(self.icons.iterdir()))
                    self.assertEqual(original_config, self.config_path.read_bytes())

    def test_http_upload_rejects_oversized_request_before_reading_body(self):
        original_icons = set(self.icons.iterdir())
        original_config = self.config_path.read_bytes()
        with self._http_server() as server:
            for path in ("/api/icons", "/api/mosaic"):
                with self.subTest(path=path):
                    status, response = self._http_request(
                        server, "POST", path,
                        headers={
                            "Content-Type": "application/json",
                            "Content-Length": str(16 * 1024 * 1024),
                        },
                    )
                    self.assertEqual(400, status, response)
                    self.assertEqual(original_icons, set(self.icons.iterdir()))
                    self.assertEqual(original_config, self.config_path.read_bytes())

    def test_http_allows_loopback_hosts_including_bracketed_ipv6(self):
        with self._http_server() as server:
            for host in ("localhost", "LOCALHOST:8765", "127.0.0.1:8765", "[::1]", "[::1]:8765"):
                with self.subTest(host=host):
                    status, response = self._http_request(
                        server, "GET", "/api/config", headers={"Host": host},
                    )
                    self.assertEqual(200, status, response)
            config = self.app.get_config()
            status, response = self._http_request(
                server, "PUT", "/api/config", config, {"Host": "[::1]:8765"},
            )
            self.assertEqual(200, status, response)

    @unittest.skipUnless(socket.has_ipv6, "Python was built without IPv6 support")
    def test_http_reads_and_saves_config_over_actual_ipv6_loopback(self):
        with self._http_server(host="::1", server_type=IPv6HTTPServer) as server:
            status, config = self._http_request(server, "GET", "/api/config")
            self.assertEqual(200, status, config)
            config["brightness"] = 42
            status, saved = self._http_request(server, "PUT", "/api/config", config)
            self.assertEqual(200, status, saved)
            self.assertEqual(42, saved["brightness"])
            persisted = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
            self.assertEqual(42, persisted["brightness"])
            original = self.config_path.read_bytes()
            config["brightness"] = 21
            status, _ = self._http_request(
                server, "PUT", "/api/config", config, {"Host": "evil.example"},
            )
            self.assertEqual(403, status)
            self.assertEqual(original, self.config_path.read_bytes())

    def test_http_forbids_nonlocal_or_malformed_hosts_without_changing_config(self):
        original = self.config_path.read_bytes()
        config = self.app.get_config()
        config["brightness"] = 42
        hosts = (
            "", "evil.example", "localhost.evil.example", "127.0.0.1.evil.example",
            "[::2]:8765", "::1", "[::1", "[::1]:invalid", "[::1]:65536",
            "[::1]evil", "[::1]:", "localhost:", "localhost:invalid",
            "localhost:65536", "user@localhost", "evil.example@localhost",
            "localhost@evil.example", "localhost/path", "localhost?query",
            "localhost#fragment", "localhost:8765:123", "localhost\t:8765",
        )
        with self._http_server() as server:
            for host in hosts:
                for method, payload in (("GET", None), ("PUT", config)):
                    with self.subTest(host=host, method=method):
                        status, _ = self._http_request(
                            server, method, "/api/config", payload, {"Host": host},
                        )
                        self.assertEqual(403, status)
                        self.assertEqual(original, self.config_path.read_bytes())

    def test_http_composite_refreshes_when_source_or_background_is_replaced(self):
        source = self.icons / "logo.png"
        background = self.icons / "background.png"
        Image.new("RGBA", (196, 196), "red").save(source)
        Image.new("RGBA", (196, 196), "black").save(background)
        config = self.app.get_config()
        config["buttons"][0].update({
            "icon_source": source.name,
            "image": source.name,
            "icon_scale": 50,
            "background_tile": background.name,
        })
        rendered_names = []
        with self._http_server() as server:
            for source_color, background_color in (
                ("red", "black"), ("blue", "black"), ("blue", "green"),
            ):
                with self.subTest(source=source_color, background=background_color):
                    Image.new("RGBA", (196, 196), source_color).save(source)
                    Image.new("RGBA", (196, 196), background_color).save(background)
                    source_bytes, background_bytes = source.read_bytes(), background.read_bytes()
                    status, response = self._http_request(server, "PUT", "/api/config", config)
                    self.assertEqual(200, status, response)
                    name = response["buttons"][0]["image"]
                    rendered_names.append(name)
                    status, rendered = self._http_request(server, "GET", f"/api/icons/{name}")
                    self.assertEqual(200, status)
                    with Image.open(io.BytesIO(rendered)) as image:
                        self.assertEqual(
                            Image.new("RGBA", (1, 1), source_color).getpixel((0, 0)),
                            image.getpixel((98, 98)),
                        )
                        self.assertEqual(
                            Image.new("RGBA", (1, 1), background_color).getpixel((0, 0)),
                            image.getpixel((0, 0)),
                        )
                    self.assertEqual(source_bytes, source.read_bytes())
                    self.assertEqual(background_bytes, background.read_bytes())
        self.assertEqual(3, len(set(rendered_names)))

    def test_scaled_icon_refreshes_when_source_is_replaced(self):
        config = self.app.get_config()
        config["buttons"][0]["icon_scale"] = 50
        source = self.icons / "default.png"
        for color in ("red", "blue"):
            with self.subTest(color=color):
                Image.new("RGBA", (196, 196), color).save(source)
                original = source.read_bytes()
                saved = self.app.save_config(config)
                with Image.open(self.icons / saved["buttons"][0]["image"]) as image:
                    self.assertEqual(
                        Image.new("RGBA", (1, 1), color).getpixel((0, 0)),
                        image.getpixel((98, 98)),
                    )
                self.assertEqual(original, source.read_bytes())

    def test_loads_all_fourteen_slots_including_wide_display(self):
        config = self.app.get_config()
        self.assertEqual(14, len(config["buttons"]))
        self.assertTrue(config["buttons"][0]["enabled"])
        self.assertFalse(config["buttons"][13]["enabled"])
        self.assertEqual(["default.png"], config["icons"])

    def test_saves_valid_configuration_and_backup(self):
        config = self.app.get_config()
        config["brightness"] = 42
        config["buttons"][0]["label"] = "Novo"

        saved = self.app.save_config(config)

        persisted = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(42, persisted["brightness"])
        self.assertEqual("Novo", persisted["buttons"][0]["label"])
        self.assertEqual("./icons/default.png", persisted["buttons"][0]["image"])
        self.assertEqual(42, saved["brightness"])
        self.assertTrue(self.config_path.with_suffix(".yaml.backup").exists())

    def test_rejects_missing_action_parameter(self):
        config = self.app.get_config()
        config["buttons"][0]["params"] = {"cmd": ""}

        with self.assertRaisesRegex(ValidationError, "preencha cmd"):
            self.app.save_config(config)

    def test_scales_logo_without_overwriting_source(self):
        config = self.app.get_config()
        config["buttons"][0]["icon_scale"] = 50

        saved = self.app.save_config(config)

        persisted = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        button = persisted["buttons"][0]
        self.assertEqual("./icons/default.png", button["icon_source"])
        self.assertEqual(50, button["icon_scale"])
        self.assertEqual("default.png", saved["buttons"][0]["icon_source"])
        self.assertEqual(50, saved["buttons"][0]["icon_scale"])
        self.assertEqual(["default.png"], saved["icons"])
        with Image.open(self.icons / Path(button["image"]).name) as resized:
            self.assertEqual((196, 196), resized.size)
            self.assertEqual((49, 49, 147, 147), resized.getchannel("A").getbbox())

    def test_icon_margin_and_scale_combine_without_modifying_source(self):
        original = (self.icons / "default.png").read_bytes()
        config = self.app.get_config()
        config["buttons"][0].update(content_margin=24, icon_scale=50)
        saved = self.app.save_config(config)
        with Image.open(self.icons / saved["buttons"][0]["image"]) as rendered:
            self.assertEqual((61, 61, 135, 135), rendered.getchannel("A").getbbox())
        self.assertEqual(original, (self.icons / "default.png").read_bytes())

    def test_icon_margin_preserves_background_pixels_and_invalidates_composite(self):
        background = Image.new("RGB", (196, 196))
        background.putdata([(x, y, 40) for y in range(196) for x in range(196)])
        background.save(self.icons / "background.png")
        config = self.app.get_config()
        button = config["buttons"][0]
        button.update(background_tile="background.png", content_margin=24)
        saved = self.app.save_config(config)
        with Image.open(self.icons / saved["buttons"][0]["image"]) as image:
            rendered = image.convert("RGB")
        for area in ((0, 0, 196, 24), (0, 172, 196, 196),
                     (0, 24, 24, 172), (172, 24, 196, 172)):
            self.assertIsNone(ImageChops.difference(
                background.crop(area), rendered.crop(area),
            ).getbbox())
        self.assertEqual((255, 107, 53), rendered.getpixel((30, 98)))
        button["content_margin"] = 48
        saved = self.app.save_config(config)
        with Image.open(self.icons / saved["buttons"][0]["image"]) as image:
            self.assertEqual(background.getpixel((30, 98)), image.convert("RGB").getpixel((30, 98)))
            self.assertEqual((255, 107, 53), image.convert("RGB").getpixel((98, 98)))

    def test_content_margin_survives_http_save_and_named_layout_restore(self):
        config = self.app.get_config()
        config["buttons"][0]["content_margin"] = 17
        config["buttons"][13].update(
            enabled=True, display_mode="stats", content_margin=31, action_enabled=False,
        )
        with self._http_server() as server:
            status, saved = self._http_request(server, "PUT", "/api/config", config)
            self.assertEqual(200, status)
            self.assertEqual(17, saved["buttons"][0]["content_margin"])
            self.assertEqual(31, saved["buttons"][13]["content_margin"])
        layout = self.app.save_layout({"name": "Margens", "config": saved})
        saved["buttons"][0]["content_margin"] = 0
        saved["buttons"][13]["content_margin"] = 0
        self.app.save_config(saved)
        restored = self.app.load_layout(layout["id"])["config"]
        self.app.save_config(restored)
        from ulanzi_manager.config import ConfigParser
        loaded = ConfigParser.load(str(self.config_path))
        self.assertEqual(17, loaded.buttons[0].content_margin)
        self.assertEqual(31, loaded.buttons[-1].content_margin)

    def test_http_rejects_out_of_range_or_fractional_content_margin_without_saving(self):
        config = self.app.get_config()
        original = self.config_path.read_bytes()
        with self._http_server() as server:
            for value in (-1, 49, 1.5):
                with self.subTest(value=value):
                    config["buttons"][0]["content_margin"] = value
                    status, _ = self._http_request(server, "PUT", "/api/config", config)
                    self.assertEqual(400, status)
                    self.assertEqual(original, self.config_path.read_bytes())

    def test_upload_normalizes_image_and_filename(self):
        source = io.BytesIO()
        Image.new("RGB", (400, 200), "#2463eb").save(source, format="JPEG")
        filename = self.app.upload_icon(
            {
                "name": "Meu ícone estranho.jpg",
                "data": base64.b64encode(source.getvalue()).decode("ascii"),
            }
        )

        self.assertEqual("Meu-cone-estranho.png", filename)
        with Image.open(self.icons / filename) as uploaded:
            self.assertEqual((196, 196), uploaded.size)
            self.assertEqual("RGBA", uploaded.mode)

    def test_upload_mosaic_splits_only_thirteen_regular_buttons(self):
        colors = [
            (index * 17 % 256, index * 37 % 256, index * 67 % 256)
            for index in range(15)
        ]
        source = Image.new("RGB", (500, 300))
        for index, color in enumerate(colors):
            row, column = divmod(index, 5)
            source.paste(
                color,
                (column * 100, row * 100, (column + 1) * 100, (row + 1) * 100),
            )
        encoded = io.BytesIO()
        source.save(encoded, format="PNG")

        result = self.app.upload_mosaic({
            "name": "fundo.png",
            "data": base64.b64encode(encoded.getvalue()).decode("ascii"),
        })
        filenames = result["filenames"]

        self.assertEqual(13, len(filenames))
        self.assertNotIn("mosaic", self.app.get_config()["buttons"][13]["image"])
        for index, filename in enumerate(filenames):
            self.assertRegex(filename, rf"^mosaic-[0-9a-f]{{10}}-{index + 1:02d}\.png$")
            with Image.open(self.icons / filename) as tile:
                self.assertEqual((196, 196), tile.size)
                self.assertEqual(colors[index], tile.convert("RGB").getpixel((98, 98)))

        logo = Image.new("RGBA", (196, 196), (0, 0, 0, 0))
        logo.paste((255, 0, 0, 255), (66, 66, 130, 130))
        logo.save(self.icons / "logo.png")
        config = self.app.get_config()
        config["background"] = result["background"]
        for index, filename in enumerate(filenames):
            config["buttons"][index].update({
                "enabled": True,
                "image": "logo.png",
                "icon_source": "logo.png",
                "icon_scale": 50,
                "background_tile": filename,
                "action": "command",
                "params": {"cmd": f"echo {index + 1}"},
            })
        gif_name = "preservado.gif"
        (self.icons / gif_name).write_bytes(b"available")
        config["buttons"][13].update({
            "enabled": True,
            "image": gif_name,
            "icon_source": gif_name,
            "display_mode": "gif",
            "action_enabled": False,
        })

        saved = self.app.save_config(config)

        self.assertEqual(gif_name, saved["buttons"][13]["image"])
        self.assertEqual("gif", saved["buttons"][13]["display_mode"])
        self.assertEqual(
            {"cmd": "echo 1"},
            saved["buttons"][0]["params"],
        )
        self.assertEqual(filenames[0], saved["buttons"][0]["background_tile"])
        self.assertEqual("logo.png", saved["buttons"][0]["icon_source"])
        self.assertNotEqual("logo.png", saved["buttons"][0]["image"])
        self.assertNotIn(filenames[0], saved["icons"])
        with Image.open(self.icons / saved["buttons"][0]["image"]) as composite:
            self.assertEqual((0, 0, 0, 255), composite.convert("RGBA").getpixel((0, 0)))
            self.assertEqual((255, 0, 0, 255), composite.convert("RGBA").getpixel((98, 98)))

    def test_upload_mosaic_applies_zoom_and_darkness(self):
        source = Image.new("RGB", (980, 588), "#008000")
        source.paste("#ff0000", (0, 0, 980, 100))
        source.paste("#ff0000", (0, 488, 980, 588))
        source.paste("#ff0000", (0, 0, 100, 588))
        source.paste("#ff0000", (880, 0, 980, 588))
        encoded = io.BytesIO()
        source.save(encoded, format="PNG")
        data = base64.b64encode(encoded.getvalue()).decode("ascii")

        original = self.app.upload_mosaic({
            "name": "fundo.png",
            "data": data,
            "scale": 100,
            "darkness": 0,
        })["filenames"]
        edited = self.app.upload_mosaic({
            "name": "fundo.png",
            "data": data,
            "scale": 200,
            "darkness": 50,
            "include_wide": True,
        })["filenames"]

        self.assertNotEqual(original[0], edited[0])
        with Image.open(self.icons / original[0]) as tile:
            self.assertEqual((255, 0, 0), tile.convert("RGB").getpixel((0, 0)))
        with Image.open(self.icons / edited[0]) as tile:
            self.assertEqual((0, 64, 0), tile.convert("RGB").getpixel((0, 0)))
        self.assertEqual(14, len(edited))
        self.assertRegex(edited[13], r"^mosaic-[0-9a-f]{10}-wide\.png$")
        with Image.open(self.icons / edited[13]) as wide:
            self.assertEqual((458, 196), wide.size)

        config = self.app.get_config()
        config["buttons"][13].update({
            "enabled": True,
            "image": edited[13],
            "icon_source": edited[13],
            "display_mode": "background",
            "action_enabled": False,
        })
        saved = self.app.save_config(config)
        self.assertEqual("background", saved["buttons"][13]["display_mode"])
        self.assertEqual(edited[13], saved["buttons"][13]["image"])
        self.assertNotIn(edited[13], saved["icons"])

    def test_background_original_and_settings_survive_http_and_layout_reload(self):
        source = Image.new("RGB", (980, 588), "#20c080")
        source.paste("#ff0000", (0, 0, 180, 588))
        encoded = io.BytesIO()
        source.save(encoded, format="PNG")
        original_bytes = encoded.getvalue()
        with self._http_server() as server:
            status, rendered = self._http_request(server, "POST", "/api/mosaic", {
                "data": base64.b64encode(original_bytes).decode("ascii"),
                "scale": 50, "darkness": 35, "include_wide": True,
            })
            self.assertEqual(201, status, rendered)
            metadata = rendered["background"]
            self.assertEqual(original_bytes, (self.icons / metadata["source"]).read_bytes())
            self.assertNotIn(metadata["source"], self.app.list_icons())
            config = self.app.get_config()
            config["background"] = metadata
            config["buttons"][0]["background_tile"] = rendered["filenames"][0]
            config["buttons"][0]["icon_scale"] = 50
            config["buttons"][13].update({
                "enabled": True, "display_mode": "stats", "action_enabled": False,
                "background_tile": rendered["filenames"][13],
            })
            status, saved = self._http_request(server, "PUT", "/api/config", config)
            self.assertEqual(200, status, saved)
            self.assertEqual(metadata, saved["background"])
            self.assertEqual("stats", saved["buttons"][13]["display_mode"])
            layout = self.app.save_layout({"name": "Fundo editável", "config": saved})
            self.app = WebApp(self.config_path)
            server.app = self.app
            status, reloaded = self._http_request(server, "GET", "/api/config")
            self.assertEqual(200, status)
            self.assertEqual(metadata, reloaded["background"])
            self.assertEqual({"cmd": "true"}, reloaded["buttons"][0]["params"])
            self.assertEqual("default.png", reloaded["buttons"][0]["icon_source"])
            self.assertEqual(50, reloaded["buttons"][0]["icon_scale"])
            layout_config = self.app.load_layout(layout["id"])["config"]
            self.assertEqual(metadata, layout_config["background"])
            expected_pixels = [
                (self.icons / name).read_bytes() for name in rendered["filenames"]
            ]
            for settings in (reloaded["background"], layout_config["background"]):
                status, reopened = self._http_request(server, "POST", "/api/mosaic", settings)
                self.assertEqual(201, status, reopened)
                self.assertEqual(rendered, reopened)
                self.assertEqual(expected_pixels, [
                    (self.icons / name).read_bytes() for name in reopened["filenames"]
                ])
            status, resized = self._http_request(server, "POST", "/api/mosaic", {
                **metadata, "scale": 150, "darkness": 0, "include_wide": False,
            })
            self.assertEqual(201, status, resized)
            self.assertEqual(13, len(resized["filenames"]))
            self.assertEqual(metadata["source"], resized["background"]["source"])
            self.assertEqual(original_bytes, (self.icons / metadata["source"]).read_bytes())
            with Image.open(self.icons / resized["filenames"][0]) as tile:
                self.assertEqual((32, 192, 128), tile.convert("RGB").getpixel((98, 98)))

    def test_shrinking_background_uses_centered_black_padding_and_exact_wide_crop(self):
        encoded = io.BytesIO()
        Image.new("RGBA", (980, 588), "white").save(encoded, format="PNG")
        data = base64.b64encode(encoded.getvalue()).decode("ascii")
        for scale in (25, 50, 100):
            with self.subTest(scale=scale):
                result = self.app.upload_mosaic({
                    "data": data, "scale": scale, "include_wide": True,
                })
                expected = Image.new("RGBA", (980, 588), (0, 0, 0, 255))
                width, height = round(980 * scale / 100), round(588 * scale / 100)
                left, top = (980 - width) // 2, (588 - height) // 2
                expected.paste((255, 255, 255, 255), (left, top, left + width, top + height))
                for index, filename in enumerate(result["filenames"][:13]):
                    row, column = divmod(index, 5)
                    face = expected.crop((
                        column * 196, row * 196, (column + 1) * 196, (row + 1) * 196,
                    ))
                    with Image.open(self.icons / filename) as tile:
                        self.assertEqual(face.tobytes(), tile.convert("RGBA").tobytes())
                wide_expected = expected.crop((588, 392, 980, 588)).resize(
                    (458, 196), Image.Resampling.LANCZOS,
                )
                with Image.open(self.icons / result["filenames"][13]) as wide:
                    self.assertEqual(wide_expected.tobytes(), wide.convert("RGBA").tobytes())

    def test_legacy_background_is_recovered_without_icons_or_config_rewrite(self):
        original_config = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        original_config["buttons"][0]["background_tile"] = "./icons/legacy-tile.png"
        Image.new("RGB", (196, 196), "#128040").save(self.icons / "legacy-tile.png")
        Image.new("RGB", (458, 196), "#403080").save(self.icons / "legacy-wide.png")
        original_config["buttons"][13] = {
            "image": "./icons/legacy-wide.png", "display_mode": "background",
            "action_enabled": False, "action": "command", "params": {"cmd": ""},
        }
        self.config_path.write_text(yaml.safe_dump(original_config), encoding="utf-8")
        before = self.config_path.read_bytes()
        presented = self.app.get_config()
        metadata = presented["background"]
        self.assertIsNotNone(metadata)
        self.assertEqual((100, 0, True), (
            metadata["scale"], metadata["darkness"], metadata["include_wide"],
        ))
        self.assertEqual(before, self.config_path.read_bytes())
        reopened = self.app.upload_mosaic(metadata)
        with Image.open(self.icons / reopened["filenames"][0]) as tile:
            self.assertEqual((18, 128, 64), tile.convert("RGB").getpixel((98, 98)))
        with Image.open(self.icons / reopened["filenames"][1]) as tile:
            self.assertEqual((0, 0, 0), tile.convert("RGB").getpixel((98, 98)))
        with Image.open(self.icons / reopened["filenames"][13]) as wide:
            self.assertEqual((64, 48, 128), wide.convert("RGB").getpixel((229, 98)))
        resized = self.app.upload_mosaic({**metadata, "scale": 50})
        self.assertEqual(metadata["source"], resized["background"]["source"])
        self.assertEqual(metadata, self.app.save_config(presented)["background"])
        self.assertEqual("default.png", self.app.get_config()["buttons"][0]["icon_source"])

    def test_mosaic_rejects_invalid_settings_and_untrusted_source_paths(self):
        encoded = io.BytesIO()
        Image.new("RGB", (20, 20), "red").save(encoded, format="PNG")
        data = base64.b64encode(encoded.getvalue()).decode("ascii")
        for invalid in (
            {"scale": 24}, {"scale": 201}, {"darkness": -1}, {"darkness": 81},
            {"scale": "invalid"}, {"include_wide": "false"},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                self.app.upload_mosaic({"data": data, **invalid})
        rendered = self.app.upload_mosaic({"data": data})
        source = rendered["background"]["source"]
        for name in ("../" + source, str(self.icons / source), "default.png", rendered["filenames"][0]):
            with self.subTest(name=name), self.assertRaisesRegex(ValidationError, "Origem"):
                self.app.upload_mosaic({"source": name})
        original = (self.icons / source).read_bytes()
        external = self.root / "outside.png"
        external.write_bytes(original)
        (self.icons / source).unlink()
        (self.icons / source).symlink_to(external)
        with self.assertRaisesRegex(ValidationError, "Origem"):
            self.app.upload_mosaic({"source": source})
        (self.icons / source).unlink()
        (self.icons / source).write_bytes(b"tampered")
        with self.assertRaisesRegex(ValidationError, "Origem"):
            self.app.upload_mosaic({"source": source})
        config = self.app.get_config()
        config["background"] = rendered["background"]
        with self.assertRaisesRegex(ValidationError, "Origem"):
            self.app.save_config(config)

    def test_upload_preserves_animated_gif_for_wide_display(self):
        source = io.BytesIO()
        frames = [
            Image.new("RGB", (320, 180), color)
            for color in ("#ff0000", "#0000ff")
        ]
        frames[0].save(
            source,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=[80, 120],
            loop=0,
        )

        filename = self.app.upload_icon(
            {
                "name": "animacao.gif",
                "data": base64.b64encode(source.getvalue()).decode("ascii"),
                "wide": True,
            }
        )

        self.assertRegex(filename, r"^animacao-[0-9a-f]{10}\.gif$")
        with Image.open(self.icons / filename) as uploaded:
            self.assertEqual((458, 196), uploaded.size)
            self.assertEqual(2, uploaded.n_frames)
            self.assertEqual(0, uploaded.info["loop"])

        config = self.app.get_config()
        config["buttons"][13] = {
            "enabled": True,
            "image": filename,
            "icon_source": filename,
        }
        self.app.save_config(config)
        persisted = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(f"./icons/{filename}", persisted["buttons"][13]["image"])
        self.assertFalse(persisted["buttons"][13]["action_enabled"])
        self.assertEqual("", persisted["buttons"][13]["params"]["cmd"])

    def test_wide_display_can_optionally_run_an_action(self):
        gif_name = "wide.gif"
        (self.icons / gif_name).write_bytes(b"available")
        config = self.app.get_config()
        config["buttons"][13] = {
            "enabled": True,
            "image": gif_name,
            "icon_source": gif_name,
            "action_enabled": True,
            "label": "Terminal",
            "action": "command",
            "params": {"cmd": "xterm"},
        }

        self.app.save_config(config)

        persisted = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        wide = persisted["buttons"][13]
        self.assertTrue(wide["action_enabled"])
        self.assertEqual("Terminal", wide["label"])
        self.assertEqual({"cmd": "xterm"}, wide["params"])

    def test_wide_display_stats_mode_does_not_require_a_gif(self):
        config = self.app.get_config()
        config["buttons"][13] = {
            "enabled": True,
            "display_mode": "stats",
            "action_enabled": False,
        }

        saved = self.app.save_config(config)

        persisted = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        wide = persisted["buttons"][13]
        self.assertEqual("stats", wide["display_mode"])
        self.assertEqual("", wide["image"])
        self.assertEqual("stats", saved["buttons"][13]["display_mode"])


    def test_rejects_invalid_metric_style_without_changing_active_config(self):
        config = self.app.get_config()
        config["buttons"][13] = {
            "enabled": True, "display_mode": "stats", "action_enabled": False,
        }
        original = self.config_path.read_bytes()
        for invalid in (
            {"size": 17}, {"size": 49}, {"size": 18.5}, {"size": True},
            {"layout": "unknown"}, {"colors": []},
            {"colors": {"cpu": "red"}},
            {"colors": {"mem": {"color": "red"}}},
            {"colors": {"gpu": {"label_color": "#zz0000"}}},
            {"colors": {"cpu": {"line_color": "red"}}},
            {"colors": {"gpu": {"line_color": None}}},
            {"font_family": "../fonts/private"}, {"font_family": []},
            {"font_style": "unknown"}, {"font_style": {}},
            {"view": "unknown"}, {"view": ["history"]},
        ):
            with self.subTest(style=invalid):
                config["buttons"][13]["metrics_style"] = invalid
                with self.assertRaises(ValidationError):
                    self.app.save_config(config)
                self.assertEqual(original, self.config_path.read_bytes())

    def test_legacy_metric_colors_migrate_without_changing_appearance(self):
        raw = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        raw["buttons"][13] = {
            "display_mode": "stats", "action_enabled": False,
            "metrics_style": {"layout": "compact", "size": 38,
                              "color": "#FFFFFF", "label_color": "#bd0000"},
        }
        self.config_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
        config = self.app.get_config()
        expected = {
            key: {"color": "#ffffff", "label_color": "#bd0000"}
            for key in ("cpu", "mem", "gpu")
        }
        style = config["buttons"][13]["metrics_style"]
        self.assertEqual(expected, {
            key: {field: palette[field] for field in ("color", "label_color")}
            for key, palette in style["colors"].items()
        })
        self.assertEqual(3, len({palette["line_color"] for palette in style["colors"].values()}))
        self.assertEqual(("compact", 38), (style["layout"], style["size"]))
        self.app.save_config(config)
        persisted = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        saved_style = persisted["buttons"][13]["metrics_style"]
        self.assertEqual(style["colors"], saved_style["colors"])
        self.assertEqual(("compact", 38), (saved_style["layout"], saved_style["size"]))
        self.assertNotIn("color", saved_style)
        self.assertNotIn("label_color", saved_style)

    def test_saves_loads_updates_and_deletes_named_layout(self):
        config = self.app.get_config()
        config["brightness"] = 35
        config["buttons"][0]["label"] = "Layout salvo"

        saved = self.app.save_layout({"name": "Trabalho", "config": config})

        self.assertEqual(
            [{"id": saved["id"], "name": "Trabalho"}],
            self.app.list_layouts(),
        )
        self.assertEqual(
            "Teste",
            self.app.get_config()["buttons"][0]["label"],
            "saving a layout must not replace the active configuration",
        )
        loaded = self.app.load_layout(saved["id"])
        self.assertEqual(35, loaded["config"]["brightness"])
        self.assertEqual("Layout salvo", loaded["config"]["buttons"][0]["label"])

        config["brightness"] = 70
        updated = self.app.save_layout({"name": "trabalho", "config": config})
        self.assertEqual(saved["id"], updated["id"])
        self.assertEqual(70, self.app.load_layout(saved["id"])["config"]["brightness"])
        self.assertEqual(1, len(self.app.list_layouts()))

        self.assertEqual({"deleted": True}, self.app.delete_layout(saved["id"]))
        self.assertEqual([], self.app.list_layouts())

    def test_rejects_invalid_layout_names_and_identifiers(self):
        config = self.app.get_config()
        with self.assertRaisesRegex(ValidationError, "Informe um nome"):
            self.app.save_layout({"name": "  ", "config": config})
        with self.assertRaisesRegex(ValidationError, "Identificador"):
            self.app.load_layout("../../config")

    def _application_catalog(self, directories, language="pt_BR.UTF-8"):
        with patch("ulanzi_manager.web._application_dirs", return_value=directories), \
                patch.dict("os.environ", {
                    "LC_ALL": language,
                    "LC_MESSAGES": language,
                    "LANG": language,
                    "LANGUAGE": "",
                    "XDG_CURRENT_DESKTOP": "GNOME",
                }):
            return self.app.list_applications()

    def test_application_overrides_hide_system_duplicates(self):
        user = self.root / "user-applications"
        system = self.root / "system-applications"
        user.mkdir()
        system.mkdir()
        for name in ("editor", "hidden", "private"):
            (system / f"{name}.desktop").write_text(
                f"[Desktop Entry]\nType=Application\nName=System {name}\nExec=true\n",
                encoding="utf-8",
            )
        (user / "editor.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Editor\n"
            "Name[pt]=Editor português\nName[pt_BR]=Editor brasileiro\nExec=true\n",
            encoding="utf-8",
        )
        (user / "hidden.desktop").write_text(
            "[Desktop Entry]\nHidden=true\n", encoding="utf-8"
        )
        (user / "private.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Private\nExec=true\nNoDisplay=true\n",
            encoding="utf-8",
        )

        applications = self._application_catalog([user, system])

        self.assertEqual(["editor.desktop"], [app["id"] for app in applications])
        self.assertEqual("Editor brasileiro", applications[0]["name"])
        self.assertEqual(str(user / "editor.desktop"), applications[0]["desktop_file"])

    def test_application_locale_and_desktop_visibility(self):
        directory = self.root / "applications"
        directory.mkdir()
        entries = {
            "localized": "Type=Application\nName=Tool\nName[pt]=Ferramenta\nExec=true\n",
            "dbus": "Type=Application\nName=Ativação D-Bus\nDBusActivatable=true\nOnlyShowIn=GNOME;\n",
            "other": "Type=Application\nName=Other\nExec=true\nOnlyShowIn=KDE;\n",
            "excluded": "Type=Application\nName=Excluded\nExec=true\nNotShowIn=GNOME;\n",
            "link": "Type=Link\nName=Link\nURL=https://example.com\n",
            "no-launcher": "Type=Application\nName=No launcher\n",
        }
        for name, body in entries.items():
            (directory / f"{name}.desktop").write_text(
                "[Desktop Entry]\n" + body, encoding="utf-8"
            )
        (directory / "broken.desktop").write_text("not a desktop file", encoding="utf-8")

        applications = self._application_catalog([directory], language="pt_PT.UTF-8")

        self.assertEqual(
            ["Ativação D-Bus", "Ferramenta"],
            [app["name"] for app in applications],
        )

    def test_application_tryexec_and_stable_export_path(self):
        directory = self.root / "exported-applications"
        directory.mkdir()
        executable = self.root / "installed-tool"
        executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        executable.chmod(0o755)
        target = self.root / "release-specific.desktop"
        target.write_text(
            f"[Desktop Entry]\nType=Application\nName=Installed\n"
            f"Exec={executable}\nTryExec={executable}\n",
            encoding="utf-8",
        )
        exported = directory / "installed.desktop"
        exported.symlink_to(target)
        (directory / "missing.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Removed\nExec=missing\n"
            f"TryExec={self.root / 'not-installed'}\n",
            encoding="utf-8",
        )

        applications = self._application_catalog([directory])

        self.assertEqual(["Installed"], [app["name"] for app in applications])
        self.assertEqual(str(exported), applications[0]["desktop_file"])

    def _write_application_messages(self):
        messages = {
            "": "Content-Type: text/plain; charset=UTF-8\nLanguage: pt_BR\n",
            "Settings": "Configurações",
        }
        keys = sorted(messages)
        originals = [key.encode("utf-8") for key in keys]
        translations = [messages[key].encode("utf-8") for key in keys]
        count = len(keys)
        offset = 28 + count * 16
        tables = []
        strings = b""
        for group in (originals, translations):
            table = b""
            for text in group:
                table += struct.pack("<2I", len(text), offset + len(strings))
                strings += text + b"\0"
            tables.append(table)
        catalog = self.root / "locale-langpack/pt_BR/LC_MESSAGES/settings-test.mo"
        catalog.parent.mkdir(parents=True)
        catalog.write_bytes(
            struct.pack("<7I", 0x950412DE, 0, count, 28, 28 + count * 8, 0, 0)
            + b"".join(tables) + strings
        )

    def test_application_name_uses_ubuntu_gettext_catalog(self):
        self._write_application_messages()
        directory = self.root / "applications"
        directory.mkdir()
        (directory / "settings.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Settings\nExec=true\n"
            "X-Ubuntu-Gettext-Domain=settings-test\n",
            encoding="utf-8",
        )
        with patch("ulanzi_manager.web.APPLICATION_LOCALE_DIRS", [
            self.root / "locale", self.root / "locale-langpack",
        ]):
            applications = self._application_catalog([directory])

        self.assertEqual("Configurações", applications[0]["name"])

    def test_inline_application_translation_wins_and_missing_catalog_keeps_app(self):
        self._write_application_messages()
        directory = self.root / "applications"
        directory.mkdir()
        (directory / "custom.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Settings\nExec=true\n"
            "Name[pt_BR]=Preferências pessoais\n"
            "X-Ubuntu-Gettext-Domain=settings-test\n",
            encoding="utf-8",
        )
        (directory / "untranslated.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Untranslated app\nExec=true\n"
            "X-Ubuntu-Gettext-Domain=missing-test-catalog\n",
            encoding="utf-8",
        )
        with patch("ulanzi_manager.web.APPLICATION_LOCALE_DIRS", [
            self.root / "locale", self.root / "locale-langpack",
        ]):
            applications = self._application_catalog([directory])

        self.assertEqual(
            {"custom.desktop": "Preferências pessoais", "untranslated.desktop": "Untranslated app"},
            {app["id"]: app["name"] for app in applications},
        )


if __name__ == "__main__":
    unittest.main()
