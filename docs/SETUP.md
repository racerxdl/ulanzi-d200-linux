# Ulanzi D200 Manager - Setup Guide

## The Issue You Encountered

```
ERROR:ulanzi_manager.cli:Failed to connect: open failed
```

This happens because the device needs proper USB permissions. The Ulanzi D200 (Vendor ID: 2207, Product ID: 0019) requires a udev rule to be accessible without root.

## Solution: Install Udev Rule

### Option 1: Automatic Installation (Recommended)

Run the installation script:
```bash
cd /home/lucas/Works/VibeCodedProjects/ulanzi
bash install.sh
```

This will:
1. Create virtual environment
2. Install the package
3. Install the udev rule
4. Create configuration directories
5. Generate example configuration

### Option 2: Manual Installation

```bash
# 1. Setup Python environment
cd /home/lucas/Works/VibeCodedProjects/ulanzi
python3 -m venv venv
source venv/bin/activate
pip install -e .

# 2. Install udev rule
sudo cp 99-ulanzi.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger

# 3. Create config directories
mkdir -p ~/.config/ulanzi
mkdir -p ~/.local/share/ulanzi

# 4. Generate example config
ulanzi-manager generate-config ~/.config/ulanzi/config.yaml
```

## After Installation

### 1. Reconnect Your Device

After installing the udev rule, **reconnect your Ulanzi D200 device** via USB.

Verify it's recognized:
```bash
lsusb | grep 2207
```

You should see:
```
Bus 001 Device 005: ID 2207:0019 Fuzhou Rockchip Electronics Company
```

### 2. Test Connection

```bash
source venv/bin/activate
ulanzi-manager status
```

Should output:
```
INFO:ulanzi_manager.device:Connected to Ulanzi D200 device
INFO:ulanzi_manager.cli:Device connected and ready
```

### 3. Configure Your Buttons

Edit the configuration:
```bash
nano ~/.config/ulanzi/config.yaml
```

### 4. Apply Configuration

```bash
ulanzi-manager configure ~/.config/ulanzi/config.yaml
```

### 5. Start the Daemon

```bash
ulanzi-daemon ~/.config/ulanzi/config.yaml
```

## What the Udev Rule Does

The file `99-ulanzi.rules` contains:

```
SUBSYSTEM=="usb", ATTRS{idVendor}=="2207", ATTRS{idProduct}=="0019", MODE="0666"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="2207", ATTRS{idProduct}=="0019", MODE="0666"
```

This tells Linux to:
- Allow any user to read/write to the Ulanzi D200 device
- Apply to both USB and HID raw interfaces
- Automatically apply when the device is connected

## Troubleshooting

### Still Getting "open failed"?

1. **Verify udev rule is installed:**
   ```bash
   ls -la /etc/udev/rules.d/99-ulanzi.rules
   ```

2. **Reload udev rules:**
   ```bash
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   ```

3. **Reconnect the device** via USB

4. **Check device is recognized:**
   ```bash
   lsusb | grep 2207
   ```

### Device Not Showing in lsusb?

- Check USB cable connection
- Try a different USB port
- Try a different USB cable
- Check if device is powered on

### Still Having Issues?

1. Check the daemon logs:
   ```bash
   tail -f ~/.local/share/ulanzi/daemon.log
   ```

2. Run with verbose logging:
   ```bash
   source venv/bin/activate
   ulanzi-manager status
   ```

3. Verify Python installation:
   ```bash
   source venv/bin/activate
   python3 -c "import hid; print('hidapi OK')"
   ```

## Next Steps

Once the device is working:

1. **Edit configuration:**
   ```bash
   nano ~/.config/ulanzi/config.yaml
   ```

2. **Validate configuration:**
   ```bash
   ulanzi-manager validate ~/.config/ulanzi/config.yaml
   ```

3. **Configure device:**
   ```bash
   ulanzi-manager configure ~/.config/ulanzi/config.yaml
   ```

4. **Start daemon:**
   ```bash
   ulanzi-daemon ~/.config/ulanzi/config.yaml
   ```

5. **Enable systemd service (optional):**
   ```bash
   mkdir -p ~/.config/systemd/user
   cp systemd/ulanzi-daemon.service ~/.config/systemd/user/
   systemctl --user daemon-reload
   systemctl --user enable ulanzi-daemon
   systemctl --user start ulanzi-daemon
   ```

## Quick Reference

| Task | Command |
|------|---------|
| Install udev rule | `sudo cp 99-ulanzi.rules /etc/udev/rules.d/` |
| Reload udev | `sudo udevadm control --reload-rules && sudo udevadm trigger` |
| Check device | `lsusb \| grep 2207` |
| Test connection | `ulanzi-manager status` |
| Generate config | `ulanzi-manager generate-config ~/.config/ulanzi/config.yaml` |
| Validate config | `ulanzi-manager validate ~/.config/ulanzi/config.yaml` |
| Configure device | `ulanzi-manager configure ~/.config/ulanzi/config.yaml` |
| Start daemon | `ulanzi-daemon ~/.config/ulanzi/config.yaml` |
| View logs | `tail -f ~/.local/share/ulanzi/daemon.log` |

---

**Status**: Ready to use after udev rule installation
