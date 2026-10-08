"""Launch a desktop file with a graphical context and await native activation.

Run with the system Python, whose PyGObject bindings match the installed GTK.
"""

import sys


def main() -> int:
    import gi

    gi.require_version("Gio", "2.0")
    gi.require_version("GioUnix", "2.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, GioUnix, GLib

    if len(sys.argv) != 2:
        raise ValueError("Usage: desktop_launcher.py DESKTOP_FILE")
    app = GioUnix.DesktopAppInfo.new_from_filename(sys.argv[1])
    if app is None:
        raise ValueError(f"Invalid desktop launcher: {sys.argv[1]}")
    Gdk.init_check([])
    display = Gdk.Display.get_default()
    if display is None:
        raise RuntimeError("No graphical display available for desktop activation")
    context = display.get_app_launch_context()
    loop = GLib.MainLoop()
    exit_code = 1

    def activated(source, result, _user_data):
        nonlocal exit_code
        try:
            if source.launch_uris_finish(result):
                exit_code = 0
                print(f"Activated desktop application: {sys.argv[1]}", flush=True)
            else:
                print(f"Desktop activation failed: {sys.argv[1]}", file=sys.stderr)
        except GLib.Error as error:
            print(f"Desktop activation failed: {error}", file=sys.stderr)
        finally:
            loop.quit()

    # Keep the launcher's D-Bus connection and main context alive until the
    # application handles activation; exiting after dispatch can lose it.
    app.launch_uris_async([], context, None, activated, None)
    loop.run()
    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"Desktop activation failed: {error}", file=sys.stderr)
        sys.exit(1)
