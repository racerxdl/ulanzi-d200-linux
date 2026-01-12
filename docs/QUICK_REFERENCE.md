# Quick Reference Card

## Debug Mode - Identify Buttons

```bash
source venv/bin/activate
ulanzi-manager debug
```

Press buttons to see their index:
```
Button layout:
  0  1  2  3  4
  5  6  7  8  9
 10 11 12
 13 (Clock/Big Button)
```

## Common Commands

| Task | Command |
|------|---------|
| Identify buttons | `ulanzi-manager debug` |
| Check device | `ulanzi-manager status` |
| Set brightness | `ulanzi-manager brightness 80` |
| Validate config | `ulanzi-manager validate config.yaml` |
| Configure device | `ulanzi-manager configure config.yaml` |
| Test image | `ulanzi-manager test-image 0 icon.png` |
| Generate config | `ulanzi-manager generate-config config.yaml` |
| Start daemon | `ulanzi-daemon config.yaml` |
| View logs | `tail -f ~/.local/share/ulanzi/daemon.log` |

## Configuration Template

```yaml
brightness: 100

buttons:
  # Button 0
  - image: ./icons/button0.png
    label: Button 0
    action: command
    params:
      cmd: "echo 'Button 0 pressed'"

  # Button 1
  - image: ./icons/button1.png
    label: Button 1
    action: app
    params:
      name: firefox

  # Button 2
  - image: ./icons/button2.png
    label: Button 2
    action: key
    params:
      keys: "ctrl+alt+t"

  # Button 3
  - image: ./icons/button3.png
    label: Button 3
    action: obs
    params:
      action: toggle_scene
      scene1: "Scene 1"
      scene2: "Scene 2"

  # Buttons 4-12 (empty)
  - null
  - null
  - null
  - null
  - null
  - null
  - null
  - null
  - null

  # Button 13 (Clock/Big Button)
  - null
```

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

## Action Types

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

### OBS - Set Scene
```yaml
action: obs
params:
  action: set_scene
  scene: "Gaming"
```

### OBS - Toggle Source
```yaml
action: obs
params:
  action: toggle_source
  scene: "Gaming"
  source: "Webcam"
```

### OBS - Toggle Recording
```yaml
action: obs
params:
  action: toggle_recording
```

### OBS - Toggle Streaming
```yaml
action: obs
params:
  action: toggle_streaming
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Device not found | `sudo cp 99-ulanzi.rules /etc/udev/rules.d/ && sudo udevadm control --reload-rules && sudo udevadm trigger` |
| Images not showing | Check image paths, verify 196×196 PNG format, check logs |
| Button 13 error | Use debug mode to identify buttons (only 0-12 exist) |
| OBS not connecting | Enable WebSocket Server in OBS (Tools → WebSocket Server Settings) |
| Keyboard shortcuts not working | Install xdotool: `sudo apt install xdotool` |

## Logs

```bash
# Real-time logs
tail -f ~/.local/share/ulanzi/daemon.log

# Last 50 lines
tail -50 ~/.local/share/ulanzi/daemon.log

# Search for errors
grep ERROR ~/.local/share/ulanzi/daemon.log

# Search for button presses
grep "Button.*pressed" ~/.local/share/ulanzi/daemon.log
```

## Setup Checklist

- [ ] Install udev rule: `sudo cp 99-ulanzi.rules /etc/udev/rules.d/`
- [ ] Reload udev: `sudo udevadm control --reload-rules && sudo udevadm trigger`
- [ ] Reconnect device
- [ ] Run debug mode: `ulanzi-manager debug`
- [ ] Note button indices
- [ ] Create/prepare images (196×196 PNG)
- [ ] Update config.yaml
- [ ] Validate: `ulanzi-manager validate config.yaml`
- [ ] Configure device: `ulanzi-manager configure config.yaml`
- [ ] Check logs: `tail -f ~/.local/share/ulanzi/daemon.log`
- [ ] Start daemon: `ulanzi-daemon config.yaml`

## File Locations

| File | Location |
|------|----------|
| Config | `~/.config/ulanzi/config.yaml` |
| Logs | `~/.local/share/ulanzi/daemon.log` |
| Icons | `./icons/` (relative to project) |
| Udev rule | `/etc/udev/rules.d/99-ulanzi.rules` |

## Useful Links

- [README.md](README.md) - Full documentation
- [DEBUG.md](DEBUG.md) - Debug guide
- [SETUP.md](SETUP.md) - Setup guide
- [QUICKSTART.md](QUICKSTART.md) - Quick start
- [FIXES.md](FIXES.md) - Recent fixes

---

**Tip**: Use `ulanzi-manager debug` to identify which button is which!
