# Quick Guide: Icon Auto-Generation

## Minimal Example

Add this to your `config.yaml`:

```yaml
buttons:
  - icon_spec:
      type: text
      color: '#FF6600'
      text: "REC"
      text_color: '#FFFFFF'
      font_size: 70
    label: "Record"
    action: obs
    params:
      action: toggle_recording
```

That's it! The icon will be automatically generated and cached.

## Common Patterns

### Recording Button (Red)
```yaml
- icon_spec:
    type: text
    color: '#CC0000'
    text: "REC"
    text_color: '#FFFFFF'
    font_size: 70
  label: "Record"
  action: obs
  params:
    action: toggle_recording
```

### Scene Switch (Green)
```yaml
- icon_spec:
    type: text
    color: '#009900'
    text: "S1"
    text_color: '#FFFFFF'
    font_size: 80
  label: "Scene 1"
  action: obs
  params:
    action: set_scene
    scene: "Gaming"
```

### Simple Solid Color
```yaml
- icon_spec:
    type: solid
    color: 'blue'
  label: "Action"
  action: command
  params:
    cmd: "firefox"
```

### Gradient Background
```yaml
- icon_spec:
    type: gradient
    color: '#0066FF'
    text_color: '#FF0000'
  label: "Power"
  action: command
  params:
    cmd: "shutdown"
```

## Color Names

You can use hex colors (`'#RRGGBB'`) or names:
- `red`, `green`, `blue`
- `yellow`, `cyan`, `magenta`
- `white`, `black`, `gray`

## Mixing Old and New

You can use both approaches in the same config:

```yaml
buttons:
  # Old way - manual PNG file
  - image: ./icons/custom.png
    label: "Custom"
    action: command
    params:
      cmd: "echo 'custom'"

  # New way - auto-generated
  - icon_spec:
      type: text
      color: '#0066FF'
      text: "AUTO"
    label: "Generated"
    action: command
    params:
      cmd: "echo 'auto'"
```

## No More Manual Work!

Before:
```python
from PIL import Image, ImageDraw

img = Image.new('RGB', (196, 196), color='blue')
draw = ImageDraw.Draw(img)
draw.text((98, 98), "TEXT", fill='white', anchor='mm')
img.save('icon.png')
```

Now:
```yaml
- icon_spec:
    type: text
    color: 'blue'
    text: "TEXT"
    text_color: 'white'
  label: "Button"
  ...
```

Much simpler! ✨
