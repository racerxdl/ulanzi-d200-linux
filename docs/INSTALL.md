# Installation Guide

## Prerequisites

- Python 3.9 or higher
- Linux system with USB support
- `xdotool` for keyboard shortcuts (optional but recommended)
- Running user systemd manager and `systemd-run` with `--expand-environment` support for application and command actions

## Step 1: Install System Dependencies

### Ubuntu/Debian
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv xdotool libhidapi-hidraw0 python3-gi gir1.2-gtk-3.0 gir1.2-glib-2.0 librsvg2-common
```

### Fedora/RHEL
```bash
sudo dnf install python3 python3-pip xdotool hidapi python3-gobject gtk3 librsvg2
```

### Arch
```bash
sudo pacman -S python python-pip xdotool hidapi python-gobject gtk3 librsvg
```

Installed-app launch and icon import select a Python with native GTK/GIO bindings rather than assuming `/usr/bin/python3` exists. Set `ULANZI_DESKTOP_PYTHON` in both service environments to override discovery. GioUnix introspection requires GLib 2.80 or newer. GdkPixbuf and its SVG loader decode application icons; keep the system MIME database available when customizing `XDG_DATA_DIRS`.

### NixOS

Installing `pygobject3` in an unrelated Python environment is not enough: both
services need the same wrapped Python, typelibs, icon themes and SVG loader.
Merge this runtime configuration into your existing NixOS service definitions
(it does not install or redefine their `ExecStart` commands):

```nix
{ pkgs, lib, ... }:
let
  nativePython = pkgs.python3.withPackages (ps: [ ps.pygobject3 ]);
  desktopPython = pkgs.writeShellScript "ulanzi-desktop-python" ''
    export GI_TYPELIB_PATH="${lib.makeSearchPath "lib/girepository-1.0" (map lib.getLib [ pkgs.glib pkgs.gtk3 pkgs.gdk-pixbuf ])}''${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}"
    export LD_LIBRARY_PATH="${lib.makeLibraryPath [ pkgs.glib pkgs.gtk3 pkgs.gdk-pixbuf ]}''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export GDK_PIXBUF_MODULE_FILE="${pkgs.librsvg}/lib/gdk-pixbuf-2.0/2.10.0/loaders.cache"
    export XDG_DATA_DIRS="${lib.makeSearchPath "share" [ pkgs.shared-mime-info pkgs.adwaita-icon-theme pkgs.hicolor-icon-theme pkgs.gsettings-desktop-schemas ]}:/run/current-system/sw/share:$HOME/.local/share:$HOME/.nix-profile/share''${XDG_DATA_DIRS:+:$XDG_DATA_DIRS}"
    exec ${nativePython}/bin/python3 "$@"
  '';
in {
  systemd.user.services.ulanzi-web.environment.ULANZI_DESKTOP_PYTHON = "${desktopPython}";
  systemd.user.services.ulanzi-daemon.environment.ULANZI_DESKTOP_PYTHON = "${desktopPython}";
}
```

For Home Manager services, use the same wrapper value in each unit's
`Service.Environment` as `"ULANZI_DESKTOP_PYTHON=${desktopPython}"`.
Keep `systemd-run` on the daemon's `PATH`. The graphical session must provide
`DISPLAY`/`WAYLAND_DISPLAY`, `XAUTHORITY` when needed, and the user D-Bus session
to the user manager; importing those variables in a terminal does not change
an already running service. Restart both services after updating their
environment. Use the wrapper path, not its underlying unwrapped interpreter.

The [Nixpkgs introspection hook](https://github.com/NixOS/nixpkgs/blob/master/pkgs/development/libraries/gobject-introspection/setup-hook.sh)
uses `GI_TYPELIB_PATH`; the [native SVG loader example](https://github.com/NixOS/nixpkgs/blob/master/pkgs/applications/audio/quodlibet/default.nix)
uses librsvg's `GDK_PIXBUF_MODULE_FILE`.


## Step 2: Clone and Setup

```bash
cd /path/to/ulanzi-d200-linux
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

## Step 3: Install Udev Rule

```bash
sudo cp 99-ulanzi.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

## Step 4: Create Configuration Directory

```bash
mkdir -p ~/.config/ulanzi
mkdir -p ~/.local/share/ulanzi
```

## Step 5: Generate Configuration

Run from the project directory. Seed the referenced stock images without
overwriting existing files, then generate the configuration:

```bash
mkdir -p ~/.config/ulanzi/icons
cp -n --no-dereference -- icons/*.png ~/.config/ulanzi/icons/
ulanzi-manager generate-config ~/.config/ulanzi/config.yaml
```

The full `bash install.sh` workflow performs this seeding before starting the
web service, preserves existing configurations and icon symlinks, and installs
both the web and daemon user units. It enables only the web unit automatically;
daemon startup remains optional.

## Step 6: Edit Configuration

Edit `~/.config/ulanzi/config.yaml` with your button definitions and actions.

## Step 7: Test Configuration

```bash
ulanzi-manager validate ~/.config/ulanzi/config.yaml
```

## Step 8: Configure Device

```bash
ulanzi-manager configure ~/.config/ulanzi/config.yaml
```

## Step 9: Run Daemon

### Option A: Manual Start
```bash
ulanzi-daemon ~/.config/ulanzi/config.yaml
```

### Option B: Systemd Service (Recommended)

1. Copy service file:
```bash
mkdir -p ~/.config/systemd/user
cp systemd/ulanzi-daemon.service ~/.config/systemd/user/
```

2. Enable and start:
```bash
systemctl --user daemon-reload
systemctl --user enable ulanzi-daemon
systemctl --user start ulanzi-daemon
```

3. Check status:
```bash
systemctl --user status ulanzi-daemon
```

4. View logs:
```bash
journalctl --user -u ulanzi-daemon -f
```

## Troubleshooting

### Device Not Found
```
RuntimeError: Ulanzi D200 device not found
```

**Solution:**
1. Check USB connection: `lsusb | grep 2207`
2. Add user to plugdev group:
```bash
sudo usermod -a -G plugdev $USER
newgrp plugdev
```

### Permission Denied / Open Failed
```
PermissionError: [Errno 13] Permission denied
ERROR: open failed
```

**Solution:** Install udev rule:
```bash
sudo cp 99-ulanzi.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Then reconnect the device or restart.

### OBS Connection Failed
```
Failed to connect to OBS
```

**Solution:**
1. Ensure OBS is running
2. Enable WebSocket Server in OBS:
   - Tools → WebSocket Server Settings
   - Enable WebSocket Server
   - Note the port (default: 4444)
3. Update config with correct host/port

### Keyboard Shortcuts Not Working
```
xdotool not found
```

**Solution:** Install xdotool:
```bash
sudo apt install xdotool
```

## Uninstall

```bash
# Disable systemd service
systemctl --user disable ulanzi-daemon
systemctl --user stop ulanzi-daemon

# Remove virtual environment
cd /path/to/ulanzi-d200-linux
rm -rf venv

# Remove configuration
rm -rf ~/.config/ulanzi
rm -rf ~/.local/share/ulanzi
```

## Next Steps

- Read [README.md](../README.md) for usage documentation
- Check [config.example.yaml](../config.example.yaml) for configuration examples
- Run `ulanzi-manager --help` for CLI help
