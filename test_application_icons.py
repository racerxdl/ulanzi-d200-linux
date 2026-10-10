"""Application icon behavior using isolated desktop files, themes and storage.

These tests use the real system-Python helper, not mocked icon lookup. They skip
only if its native dependencies are unavailable; no installed app is required.
"""

import hashlib
import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image

from ulanzi_manager.application_icons import import_application_icon


class ApplicationIconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        probe = subprocess.run(
            [os.environ.get("ULANZI_GI_PYTHON", "/usr/bin/python3"), "-c", (
                "import gi; "
                "gi.require_version('GioUnix', '2.0'); "
                "gi.require_version('Gtk', '3.0'); "
                "gi.require_version('GdkPixbuf', '2.0'); "
                "from gi.repository import GioUnix, Gtk, GdkPixbuf"
            )], capture_output=True, check=False,
        )
        if probe.returncode != 0:
            raise unittest.SkipTest("Native PyGObject/GTK 3/GioUnix/GdkPixbuf unavailable")

    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = self.root / "data"
        self.config = self.root / "config"
        self.icons = self.root / "imported"
        self.marker = self.root / "must-not-launch"
        environment = patch.dict(os.environ, {
            "HOME": str(self.root),
            "XDG_DATA_HOME": str(self.data),
            # Native decoders need the installed MIME database, not host app icons.
            "XDG_DATA_DIRS": f"{self.root / 'system'}:/usr/local/share:/usr/share",
            "XDG_CONFIG_HOME": str(self.config),
            "XDG_CURRENT_DESKTOP": "",
            "GSETTINGS_BACKEND": "memory",
            "DISPLAY": "",
            "WAYLAND_DISPLAY": "",
        })
        environment.start()
        self.addCleanup(environment.stop)
        gtk_config = self.config / "gtk-3.0"
        gtk_config.mkdir(parents=True)
        (gtk_config / "settings.ini").write_text(
            "[Settings]\ngtk-icon-theme-name=UlanziFixtureChild\n", encoding="utf-8",
        )

    def desktop_file(self, icon=None, name="application.desktop"):
        path = self.root / name
        path.write_text(
            "[Desktop Entry]\nType=Application\nName=Ulanzi fixture\n"
            f"Exec=/bin/sh -c 'touch {self.marker}'\n"
            + (f"Icon={icon}\n" if icon is not None else ""),
            encoding="utf-8",
        )
        return str(path)

    def raster(self, path, size=(80, 40), color=(17, 83, 149, 255)):
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", size, color).save(path)
        return path

    def theme(self, root, name, inherits="", size=64):
        path = root / name
        directory = path / f"{size}x{size}" / "apps"
        directory.mkdir(parents=True)
        (path / "index.theme").write_text(
            f"[Icon Theme]\nName={name}\nDirectories={size}x{size}/apps\n"
            f"Inherits={inherits}\n\n[{size}x{size}/apps]\n"
            f"Size={size}\nType=Fixed\nContext=Applications\n", encoding="utf-8",
        )
        return directory

    def assert_icon(self, filename, bounds, color=(17, 83, 149, 255)):
        self.assertIsNotNone(filename)
        self.assertEqual(Path(filename).name, filename)
        content = (self.icons / filename).read_bytes()
        self.assertEqual(filename, f"application-{hashlib.sha256(content).hexdigest()}.png")
        with Image.open(self.icons / filename) as image:
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.mode, "RGBA")
            self.assertEqual(image.size, (196, 196))
            self.assertEqual(image.getchannel("A").getbbox(), bounds)
            self.assertEqual(image.getpixel((98, 98)), color)
            self.assertEqual(image.getpixel((0, 0)), (0, 0, 0, 0))
        self.assertFalse(self.marker.exists(), "Importing an icon must not launch its application")

    def test_absolute_raster_preserves_aspect_and_deduplicates_content(self):
        source = self.raster(self.root / "wide.png")
        desktop = self.desktop_file(source)
        first = import_application_icon(desktop, self.icons)
        second = import_application_icon(desktop, self.icons)
        self.assertEqual(first, second)
        self.assert_icon(first, (0, 49, 196, 147))
        self.assertEqual({path.name for path in self.icons.iterdir()}, {first})
        source.write_bytes(b"The imported icon must remain independent of its source")
        self.assert_icon(first, (0, 49, 196, 147))

    def test_absolute_svg_uses_native_loader_and_preserves_aspect(self):
        source = self.root / "portrait.svg"
        source.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="80" '
            'viewBox="0 0 40 80"><rect width="40" height="80" fill="#115395"/></svg>',
            encoding="utf-8",
        )
        filename = import_application_icon(self.desktop_file(source), self.icons)
        self.assert_icon(filename, (49, 0, 147, 196))

    def test_source_transparency_survives_native_rasterization(self):
        source = self.root / "transparent.png"
        image = Image.new("RGBA", (196, 196), (0, 0, 0, 0))
        image.paste((17, 83, 149, 128), (20, 40, 176, 156))
        image.save(source)
        filename = import_application_icon(self.desktop_file(source), self.icons)
        self.assert_icon(filename, (20, 40, 176, 156), color=(17, 83, 149, 128))

    def test_theme_name_resolves_configured_headless_theme_inheritance(self):
        self.theme(self.data / "icons", "UlanziFixtureChild", "UlanziFixtureParent")
        parent = self.theme(self.data / "icons", "UlanziFixtureParent")
        self.raster(parent / "ulanzi-fixture-inherited.png", size=(64, 32))
        filename = import_application_icon(
            self.desktop_file("ulanzi-fixture-inherited"), self.icons,
        )
        self.assert_icon(filename, (0, 49, 196, 147))

    def test_flatpak_export_icons_work_without_export_in_xdg_data_dirs(self):
        exported = self.theme(self.data / "flatpak/exports/share/icons", "hicolor", size=128)
        self.raster(exported / "org.ulanzi.Fixture.png", size=(64, 128))
        filename = import_application_icon(
            self.desktop_file("org.ulanzi.Fixture", "org.ulanzi.Fixture.desktop"), self.icons,
        )
        self.assert_icon(filename, (49, 0, 147, 196))

    def test_missing_icon_returns_none_without_changing_existing_files(self):
        self.icons.mkdir()
        manual = self.raster(self.icons / "manual.png")
        before = manual.read_bytes()
        for icon in (None, self.root / "missing.svg", "ulanzi-fixture-no-such-icon"):
            with self.subTest(icon=icon):
                self.assertIsNone(import_application_icon(self.desktop_file(icon), self.icons))
                self.assertEqual(manual.read_bytes(), before)
                self.assertEqual({path.name for path in self.icons.iterdir()}, {"manual.png"})

    def test_corrupt_source_is_a_logged_error_not_a_missing_icon(self):
        source = self.root / "corrupt.png"
        source.write_bytes(b"not an image")
        with self.assertLogs("ulanzi_manager.application_icons", level="ERROR"):
            with self.assertRaisesRegex(RuntimeError, "Desktop icon import failed"):
                import_application_icon(self.desktop_file(source), self.icons)
        self.assertFalse(self.icons.exists())

    def test_failed_atomic_write_preserves_previous_icon_and_removes_temporary_file(self):
        source = self.raster(self.root / "wide.png")
        desktop = self.desktop_file(source)
        filename = import_application_icon(desktop, self.icons)
        before = (self.icons / filename).read_bytes()
        with patch("ulanzi_manager.application_icons.os.replace", side_effect=OSError("disk error")):
            with self.assertLogs("ulanzi_manager.application_icons", level="ERROR"):
                with self.assertRaisesRegex(RuntimeError, "disk error"):
                    import_application_icon(desktop, self.icons)
        self.assertEqual((self.icons / filename).read_bytes(), before)
        self.assertEqual({path.name for path in self.icons.iterdir()}, {filename})


if __name__ == "__main__":
    unittest.main()
