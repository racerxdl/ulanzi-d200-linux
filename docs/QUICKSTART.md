# Quick Start Guide

Get your Ulanzi D200 up and running in 5 minutes!

## 1. Install

```bash
cd /home/lucas/Works/VibeCodedProjects/ulanzi
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

## 2. Install Udev Rule

```bash
sudo cp 99-ulanzi.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Reconnect your device after this step.

## 3. Create Config Directory

```bash
mkdir -p ~/.config/ulanzi
```

## 4. Generate Config

```bash
ulanzi-manager generate-config ~/.config/ulanzi/config.yaml
```

## 5. Edit Config

Open `~/.config/ulanzi/config.yaml` and customize your buttons:

```yaml
buttons:
  # Button 0 - Launch Firefox
  - image: ./icons/firefox.png
    label: Firefox
    action: app
    params:
      name: firefox

  # Button 1 - Execute command
  - image: ./icons/terminal.png
    label: Terminal
    action: command
    params:
      cmd: "gnome-terminal"

  # Button 2 - Keyboard shortcut
  - image: ./icons/keyboard.png
    label: Shortcut
    action: key
    params:
      keys: "ctrl+alt+t"

  # Buttons 3-12 - Empty
  - null
  - null
  # ... more nulls
```

## 6. Validate Config

```bash
ulanzi-manager validate ~/.config/ulanzi/config.yaml
```

## 7. Configure Device

```bash
ulanzi-manager configure ~/.config/ulanzi/config.yaml
```

## 8. Start Daemon

```bash
ulanzi-daemon ~/.config/ulanzi/config.yaml
```

Done! Your device is now ready to use.

## Common Actions

### Launch Application
```yaml
action: app
params:
  name: firefox
```

### Execute Command
```yaml
action: command
params:
  cmd: "notify-send 'Hello!'"
```

### Keyboard Shortcut
```yaml
action: key
params:
  keys: "ctrl+alt+t"
```

### Control OBS (requires OBS WebSocket enabled)
```yaml
action: obs
params:
  action: toggle_scene
  scene1: "Gaming"
  scene2: "Desktop"
```

## CLI Commands

```bash
# Check device status
ulanzi-manager status

# Set brightness
ulanzi-manager brightness 80

# Test image on button
ulanzi-manager test-image 0 ~/icon.png

# Validate config
ulanzi-manager validate ~/.config/ulanzi/config.yaml

# Start daemon
ulanzi-daemon ~/.config/ulanzi/config.yaml
```

## Systemd Service (Optional)

Run daemon automatically on startup:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/ulanzi-daemon.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable ulanzi-daemon
systemctl --user start ulanzi-daemon
```

Check status:
```bash
systemctl --user status ulanzi-daemon
journalctl --user -u ulanzi-daemon -f
```

## Troubleshooting

**Device not found?**
```bash
lsusb | grep 2207
sudo usermod -a -G plugdev $USER
newgrp plugdev
```

**OBS not connecting?**
- Open OBS
- Tools → WebSocket Server Settings
- Enable WebSocket Server

**Keyboard shortcuts not working?**
```bash
sudo apt install xdotool
```

## Next Steps

- Read [README.md](README.md) for detailed documentation
- Check [config.yaml](config.yaml) for more examples
- See [INSTALL.md](INSTALL.md) for advanced setup
