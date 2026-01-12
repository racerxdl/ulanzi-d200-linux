# 🚀 START HERE - Ulanzi D200 Manager

## What You Just Got

A complete Linux application for controlling your Ulanzi D200 StreamDeck device with:
- ✓ Button press detection
- ✓ Custom button images and labels
- ✓ Action execution (commands, apps, keyboard, OBS)
- ✓ Background daemon service
- ✓ Debug mode to identify buttons

## Quick Start (5 minutes)

### 1. Identify Your Buttons

```bash
source venv/bin/activate
ulanzi-manager debug
```

Press each button on your device. You'll see:
```
Button layout:
  0  1  2  3  4
  5  6  7  8  9
 10 11 12
 13 (Clock/Big Button)

>>> BUTTON 0 PRESSED (index=0, state=0) <<<
>>> CLOCK PRESSED (index=13, state=0) <<<
```

**Note the index of each button you press.**

### 2. Update Configuration

Edit `config.yaml`:
```bash
nano config.yaml
```

Example:
```yaml
brightness: 100

buttons:
  # Button 0 - Firefox
  - image: ./icons/firefox.png
    label: Firefox
    action: app
    params:
      name: firefox

  # Button 1 - Terminal
  - image: ./icons/terminal.png
    label: Terminal
    action: command
    params:
      cmd: "gnome-terminal"

  # Buttons 2-12 (empty)
  - null
  - null
  - null
  - null
  - null
  - null
  - null
  - null
  - null
  - null
  - null
```

### 3. Configure Device

```bash
ulanzi-manager configure config.yaml
```

Check output for:
```
INFO:ulanzi_manager.device:Set 2 button(s) with 2 image(s)
```

### 4. Start Daemon

```bash
ulanzi-daemon config.yaml
```

Done! Your buttons are now active.

## Troubleshooting

### Images Not Showing?

1. **Check image paths**:
   ```bash
   ulanzi-manager validate config.yaml
   ```

2. **Verify image format**:
   - Must be PNG
   - Must be 196×196 pixels
   - RGB or RGBA color space

3. **Check logs**:
   ```bash
   tail -f ~/.local/share/ulanzi/daemon.log
   ```

### Device Not Found?

```bash
sudo cp 99-ulanzi.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
# Reconnect device
```

## Available Actions

### Command
```yaml
action: command
params:
  cmd: "notify-send 'Hello!'"
```

### App
```yaml
action: app
params:
  name: firefox
```

### Keyboard
```yaml
action: key
params:
  keys: "ctrl+alt+t"
```

### OBS - Toggle Scene
```yaml
action: obs
params:
  action: toggle_scene
  scene1: "Gaming"
  scene2: "Desktop"
```

## Commands

```bash
ulanzi-manager status              # Check device
ulanzi-manager brightness 80       # Set brightness
ulanzi-manager configure config.yaml  # Apply config
ulanzi-manager validate config.yaml   # Check config
ulanzi-manager debug               # Show button presses
ulanzi-daemon config.yaml          # Start daemon
```

## Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - 5-minute setup
- **[DEBUG.md](DEBUG.md)** - Debug guide
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Commands & templates
- **[README.md](README.md)** - Full documentation
- **[INDEX.md](INDEX.md)** - Complete index

## Image Requirements

- **Format**: PNG
- **Size**: 196×196 pixels
- **Color Space**: RGB or RGBA

Create with Python:
```python
from PIL import Image, ImageDraw, ImageFont

img = Image.new('RGB', (196, 196), color='blue')
draw = ImageDraw.Draw(img)
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
draw.text((98, 98), "Text", fill='white', font=font, anchor='mm')
img.save('button.png')
```

## Next Steps

1. ✓ Run debug mode: `ulanzi-manager debug`
2. ✓ Note button indices
3. ✓ Create/prepare images (196×196 PNG)
4. ✓ Update config.yaml
5. ✓ Validate: `ulanzi-manager validate config.yaml`
6. ✓ Configure: `ulanzi-manager configure config.yaml`
7. ✓ Start daemon: `ulanzi-daemon config.yaml`

## Need Help?

- **Setup issues?** → See [SETUP.md](SETUP.md)
- **Debugging?** → See [DEBUG.md](DEBUG.md)
- **Quick reference?** → See [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
- **Full docs?** → See [README.md](README.md)

---

**Ready?** Start with: `source venv/bin/activate && ulanzi-manager debug`
