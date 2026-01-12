# Installation Guide

## Prerequisites

- Python 3.8 or higher
- Linux system with USB support
- `xdotool` for keyboard shortcuts (optional but recommended)

## Step 1: Install System Dependencies

### Ubuntu/Debian
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv xdotool libhidapi-hidraw0
```

### Fedora/RHEL
```bash
sudo dnf install python3 python3-pip xdotool hidapi
```

### Arch
```bash
sudo pacman -S python python-pip xdotool hidapi
```

## Step 2: Clone and Setup

```bash
cd /home/lucas/Works/VibeCodedProjects/ulanzi
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

```bash
ulanzi-manager generate-config ~/.config/ulanzi/config.yaml
```

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
cd /home/lucas/Works/VibeCodedProjects/ulanzi
rm -rf venv

# Remove configuration
rm -rf ~/.config/ulanzi
rm -rf ~/.local/share/ulanzi
```

## Next Steps

- Read [README.md](README.md) for usage documentation
- Check [config.yaml](config.yaml) for configuration examples
- Run `ulanzi-manager --help` for CLI help
