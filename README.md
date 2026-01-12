# Ulanzi D200 Manager

A Linux application for managing the Ulanzi D200 StreamDeck device. Configure button images, labels, and actions to control OBS Studio, launch applications, execute commands, and more.

## Features

- 🎨 **Custom Button Images** - Set 196×196 PNG images for each button
- 🏷️ **Button Labels** - Add text labels to buttons with customizable styling
- 🎬 **OBS Integration** - Control OBS Studio scenes, sources, recording, and streaming
- 🚀 **App Launcher** - Launch applications with a button press
- ⌨️ **Keyboard Shortcuts** - Simulate keyboard input
- 💻 **Shell Commands** - Execute arbitrary shell commands
- 🔄 **Hot-Reload** - Update configuration without restarting
- 🌙 **Background Daemon** - Run as a systemd service

## Quick Start

1. **Install udev rule:**
   ```bash
   sudo cp 99-ulanzi.rules /etc/udev/rules.d/
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   ```

2. **Install package:**
   ```bash
   pip install -e .
   ```

3. **Configure:**
   ```bash
   ulanzi-manager generate-config ~/.config/ulanzi/config.yaml
   # Edit the file and then:
   ulanzi-manager configure ~/.config/ulanzi/config.yaml
   ```

4. **Run daemon:**
   ```bash
   ulanzi-daemon ~/.config/ulanzi/config.yaml
   ```

## Documentation

- [📖 Start Here](docs/START_HERE.md)
- [🚀 Quick Start & Setup](docs/QUICKSTART.md)
- [⚙️ Setup Guide](docs/SETUP.md)
- [🔧 Install Guide](docs/INSTALL.md)
- [🐛 Debug & Troubleshooting](docs/DEBUG.md)
- [📋 Quick Reference](docs/QUICK_REFERENCE.md)
- [🎨 Icon Generation](docs/ICON_GENERATION.md)
- [🎬 OBS API Reference](docs/OBS_API_REFERENCE.md)
- [📦 Project Summary](docs/PROJECT_SUMMARY.md)

## Configuration

See [docs/QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md) for complete config examples and [docs/START_HERE.md](docs/START_HERE.md) for guided setup.

**Button Layout:**
```
0  1  2  3  4
5  6  7  8  9
10 11 12 13 (clock)
```

**Action Types:** `command`, `app`, `key`, `obs` (scenes, sources, recording, streaming)

## Commands

| Task | Command |
|------|---------|
| Check device | `ulanzi-manager status` |
| Set brightness | `ulanzi-manager brightness 80` |
| Apply config | `ulanzi-manager configure config.yaml` |
| Validate config | `ulanzi-manager validate config.yaml` |
| Test button image | `ulanzi-manager test-image 0 icon.png` |
| Debug (show button presses) | `ulanzi-manager debug` |
| Start daemon | `ulanzi-daemon config.yaml` |

## Image Preparation

Button images: PNG, 196×196 pixels, RGB/RGBA.

**Auto-generate icons** (recommended):
```yaml
buttons:
  - icon_spec:
      type: text
      color: '#FF6B00'
      text: "REC"
      text_color: '#FFFFFF'
      font_size: 70
    label: "Record"
    action: obs
    params:
      action: toggle_recording
```

See [docs/ICON_GENERATION.md](docs/ICON_GENERATION.md) for full icon spec options.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Device not found | `sudo cp 99-ulanzi.rules /etc/udev/rules.d/`, reload, reconnect |
| OBS not connecting | Enable WebSocket Server in OBS (Tools → WebSocket Server Settings) |
| Keyboard shortcuts fail | Install xdotool: `sudo apt install xdotool` |
| Permission denied | Ensure udev rule installed; reconnect device |

See [docs/DEBUG.md](docs/DEBUG.md) for detailed troubleshooting.

## Project Info

**Logs:** `~/.local/share/ulanzi/daemon.log` (view with `tail -f`)

**License:** MIT

**References:**
- [Ulanzi D200 Protocol](https://github.com/redphx/strmdck)
- [OBS WebSocket](https://github.com/obsproject/obs-websocket)

---

*Yes, I vibecoded that and manually fixed some wrong stuff.*