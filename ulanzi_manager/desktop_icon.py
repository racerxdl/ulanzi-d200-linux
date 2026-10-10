"""Resolve installed desktop icons with the native GTK stack, without launching.

Run with /usr/bin/python3. stdout is a single transparent 196×196 PNG on success;
exit 3 with empty stdout means no icon. Other failures are described on stderr.
Importing this module does not import GI or initialize a graphical display.
"""

import configparser
import os
import sys
from pathlib import Path

_ICON_SIZE = 196
_MISSING_ICON = 3


def _xdg_home(variable, fallback):
    value = Path(os.environ.get(variable) or fallback)
    return value if value.is_absolute() else Path(fallback)


def _headless_theme_name(Gio):
    """Use user GTK configuration and desktop settings even without a display."""
    config_home = _xdg_home("XDG_CONFIG_HOME", Path.home() / ".config")
    settings_path = config_home / "gtk-3.0" / "settings.ini"
    if settings_path.is_file():
        settings = configparser.ConfigParser(interpolation=None)
        settings.read(settings_path, encoding="utf-8")
        name = settings.get("Settings", "gtk-icon-theme-name", fallback="").strip()
        if name:
            return name

    # A systemd user service may have no DISPLAY but still has the user's dconf
    # settings. Avoid requiring gsettings to exist as a separate executable.
    desktops = os.environ.get("XDG_CURRENT_DESKTOP", "").lower().split(":")
    schema_id = (
        "org.cinnamon.desktop.interface" if "cinnamon" in desktops
        else "org.gnome.desktop.interface"
    )
    schema_source = Gio.SettingsSchemaSource.get_default()
    schema = schema_source.lookup(schema_id, True) if schema_source else None
    if schema is not None:
        settings = Gio.Settings.new_full(schema, None, None)
        user_value = settings.get_user_value("icon-theme")
        if user_value is not None:
            return user_value.get_string()
        if not any(desktops) or any(
            desktop in {"gnome", "ubuntu", "unity", "cinnamon"} for desktop in desktops
        ):
            return settings.get_string("icon-theme")
    return "Adwaita"


def _icon_theme(Gtk, Gio):
    Gtk.init_check([])
    theme = Gtk.IconTheme.new()
    settings = Gtk.Settings.get_default()
    name = settings.get_property("gtk-icon-theme-name") if settings is not None else None
    theme.set_custom_theme(name or _headless_theme_name(Gio))

    data_home = _xdg_home("XDG_DATA_HOME", Path.home() / ".local/share")
    data_dirs = [
        Path(value)
        for value in (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")
        if value and Path(value).is_absolute()
    ]
    # Flatpak/Snap exports may be absent from a user service's XDG_DATA_DIRS.
    roots = [
        Path.home() / ".icons",
        data_home / "icons",
        data_home / "flatpak/exports/share/icons",
        *(directory / "icons" for directory in data_dirs),
        Path("/var/lib/flatpak/exports/share/icons"),
        Path("/var/lib/snapd/desktop/icons"),
        *(directory / "pixmaps" for directory in data_dirs),
        *(Path(path) for path in theme.get_search_path()),
    ]
    theme.set_search_path([str(path) for path in dict.fromkeys(roots)])
    return theme


def _load_icon(desktop_file, Gio, GioUnix, Gtk, GdkPixbuf):
    app = GioUnix.DesktopAppInfo.new_from_filename(desktop_file)
    if app is None:
        raise ValueError(f"Invalid desktop launcher: {desktop_file}")
    if not app.get_string("Icon"):
        return None
    icon = app.get_icon()
    if icon is None:
        return None
    if isinstance(icon, Gio.FileIcon):
        filename = icon.get_file().get_path()
        if not filename or not Path(filename).is_file():
            return None
        # GdkPixbuf's installed SVG loader rasterizes vector icons natively.
        return GdkPixbuf.Pixbuf.new_from_file_at_scale(filename, _ICON_SIZE, _ICON_SIZE, True)
    theme = _icon_theme(Gtk, Gio)
    info = theme.lookup_by_gicon(icon, _ICON_SIZE, Gtk.IconLookupFlags.FORCE_SIZE)
    return info.load_icon() if info is not None else None


def _render_icon(source, GdkPixbuf):
    width, height = source.get_width(), source.get_height()
    ratio = min(_ICON_SIZE / width, _ICON_SIZE / height)
    target_width = max(1, min(_ICON_SIZE, round(width * ratio)))
    target_height = max(1, min(_ICON_SIZE, round(height * ratio)))
    if (width, height) != (target_width, target_height):
        source = source.scale_simple(target_width, target_height, GdkPixbuf.InterpType.BILINEAR)
    canvas = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, _ICON_SIZE, _ICON_SIZE)
    canvas.fill(0)
    source.copy_area(
        0, 0, target_width, target_height, canvas,
        (_ICON_SIZE - target_width) // 2, (_ICON_SIZE - target_height) // 2,
    )
    success, content = canvas.save_to_bufferv("png", [], [])
    if not success:
        raise RuntimeError("GdkPixbuf could not encode the application icon as PNG")
    return content


def main():
    if len(sys.argv) != 2:
        raise ValueError("Usage: desktop_icon.py DESKTOP_FILE")
    try:
        import gi

        gi.require_version("Gio", "2.0")
        gi.require_version("GioUnix", "2.0")
        gi.require_version("Gtk", "3.0")
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import Gio, GioUnix, Gtk, GdkPixbuf
    except (ImportError, ValueError) as error:
        raise RuntimeError(
            "Native icon import requires system Python PyGObject and GioUnix/GTK 3/"
            "GdkPixbuf introspection data (with an SVG loader for SVG icons): " + str(error)
        ) from error

    source = _load_icon(sys.argv[1], Gio, GioUnix, Gtk, GdkPixbuf)
    if source is None:
        return _MISSING_ICON
    sys.stdout.buffer.write(_render_icon(source, GdkPixbuf))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"Desktop icon import failed: {error}", file=sys.stderr)
        sys.exit(1)
