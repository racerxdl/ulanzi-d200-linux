# Ulanzi D200 Manager - Project Summary

## Overview

A complete Linux application for managing the Ulanzi D200 StreamDeck device with USB control, button configuration, and action execution.

## Project Structure

```
ulanzi/
├── ulanzi_manager/              # Main package
│   ├── __init__.py
│   ├── device.py                # USB device communication (1024-byte packets, ZIP file transfer)
│   ├── config.py                # YAML configuration parser and validator
│   ├── actions.py               # Action handlers (command, app, key, OBS)
│   ├── daemon.py                # Background daemon service
│   └── cli.py                   # Command-line interface
├── systemd/
│   └── ulanzi-daemon.service    # Systemd user service
├── icons/                       # Placeholder button icons (196×196 PNG)
├── setup.py                     # Package setup
├── requirements.txt             # Python dependencies
├── config.yaml                  # Example configuration
├── README.md                    # Full documentation
├── QUICKSTART.md                # Quick start guide
├── INSTALL.md                   # Installation guide
└── .gitignore                   # Git ignore rules
```

## Key Features

### Device Communication (device.py)
- USB HID protocol implementation for Ulanzi D200
- Packet structure: Header (0x7C7C) + Command + Length + Data (1024 bytes total)
- ZIP file transfer for button images with protocol bug workaround
- Button press event reading (non-blocking)
- Brightness, label style, and small window data control

### Configuration (config.py)
- YAML-based configuration format
- Button definitions with image paths and labels
- Action type validation (command, app, key, obs)
- OBS WebSocket settings
- Global brightness and label styling

### Action Handlers (actions.py)
- **Command**: Execute shell commands
- **App**: Launch applications
- **Key**: Simulate keyboard input (via xdotool)
- **OBS**: Control OBS Studio via WebSocket
  - Toggle scenes
  - Set specific scene
  - Toggle source visibility
  - Toggle recording/streaming

### Daemon (daemon.py)
- Background service for continuous button monitoring
- Configuration hot-reload support
- OBS WebSocket client integration
- Keep-alive mechanism
- Logging to ~/.local/share/ulanzi/daemon.log

### CLI (cli.py)
- `ulanzi-manager status` - Check device connection
- `ulanzi-manager brightness <0-100>` - Set brightness
- `ulanzi-manager configure <config.yaml>` - Apply configuration
- `ulanzi-manager test-image <button> <image>` - Test button image
- `ulanzi-manager validate <config.yaml>` - Validate configuration
- `ulanzi-manager generate-config <output>` - Generate example config
- `ulanzi-daemon <config.yaml>` - Start background daemon

## Button Layout

```
0  1  2  3  4
5  6  7  8  9
10 11 12
```

13 buttons total, indexed 0-12.

## Configuration Example

```yaml
brightness: 100

label_style:
  Align: bottom
  Color: 0xFFFFFF
  FontName: Roboto
  ShowTitle: true
  Size: 10
  Weight: 80

obs:
  host: localhost
  port: 4444
  password: null

buttons:
  - image: ./icons/firefox.png
    label: Firefox
    action: app
    params:
      name: firefox

  - image: ./icons/obs.png
    label: Scene
    action: obs
    params:
      action: toggle_scene
      scene1: "Gaming"
      scene2: "Desktop"

  - image: ./icons/terminal.png
    label: Terminal
    action: command
    params:
      cmd: "gnome-terminal"

  - null  # Empty button
  # ... more buttons
```

## Installation

```bash
cd /home/lucas/Works/VibeCodedProjects/ulanzi
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

## Quick Start

```bash
# Generate config
ulanzi-manager generate-config ~/.config/ulanzi/config.yaml

# Edit config
nano ~/.config/ulanzi/config.yaml

# Validate
ulanzi-manager validate ~/.config/ulanzi/config.yaml

# Configure device
ulanzi-manager configure ~/.config/ulanzi/config.yaml

# Start daemon
ulanzi-daemon ~/.config/ulanzi/config.yaml
```

## Dependencies

- **pyusb** - USB device communication
- **hidapi** - HID protocol support
- **pyyaml** - Configuration parsing
- **obs-websocket-py** - OBS Studio control
- **pillow** - Image processing
- **python-daemon** - Daemon utilities

## Testing

All modules have been syntax-checked and tested:
- ✓ Config parsing and validation
- ✓ Action executor initialization
- ✓ CLI command execution
- ✓ Configuration file generation

## Systemd Integration

```bash
mkdir -p ~/.config/systemd/user
cp systemd/ulanzi-daemon.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable ulanzi-daemon
systemctl --user start ulanzi-daemon
```

## Logging

Daemon logs: `~/.local/share/ulanzi/daemon.log`

View real-time logs:
```bash
tail -f ~/.local/share/ulanzi/daemon.log
```

## Protocol Details

### USB IDs
- Vendor ID: 0x2207
- Product ID: 0x0019

### Command Protocols
- 0x0001: OUT_SET_BUTTONS (send button images)
- 0x0006: OUT_SET_SMALL_WINDOW_DATA (status display)
- 0x000a: OUT_SET_BRIGHTNESS (brightness control)
- 0x000b: OUT_SET_LABEL_STYLE (text styling)
- 0x0101: IN_BUTTON (button press event)

### Button Image Format
- PNG format, 196×196 pixels
- Sent as ZIP file containing:
  - page/manifest.json (button configuration)
  - page/icons/icon_*.png (button images)
  - page/dummy.txt (padding for protocol bug workaround)

## Future Enhancements

- Web UI for configuration
- Button animation support
- Custom fonts for labels
- Profile switching
- Macro recording
- Device firmware updates
- Multi-device support

## License

MIT

## References

- [Ulanzi D200 Protocol](https://github.com/redphx/strmdck)
- [OBS WebSocket Protocol](https://github.com/obsproject/obs-websocket)
- [PyUSB Documentation](https://pyusb.github.io/pyusb/)
