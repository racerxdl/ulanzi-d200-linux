# Debug Guide - Ulanzi D200 Manager

## Debug Mode - Identify Button Presses

The easiest way to figure out which physical button corresponds to which index is to use debug mode.

### Run Debug Mode

```bash
source venv/bin/activate
ulanzi-manager debug
```

You'll see:
```
INFO:ulanzi_manager.cli:Debug mode: Press buttons to see their index
INFO:ulanzi_manager.cli:Button layout:
INFO:ulanzi_manager.cli:  0  1  2  3  4
INFO:ulanzi_manager.cli:  5  6  7  8  9
INFO:ulanzi_manager.cli: 10 11 12
INFO:ulanzi_manager.cli:
INFO:ulanzi_manager.cli:Waiting for button presses (Ctrl+C to exit)...
```

### Press Buttons and Note the Index

Press each button on your device. The output will show:
```
INFO:ulanzi_manager.cli:>>> BUTTON 0 PRESSED <<<
INFO:ulanzi_manager.cli:>>> BUTTON 1 PRESSED <<<
```

This tells you which button index corresponds to each physical button.

### Button Layout Reference

```
Top Row:     0  1  2  3  4
Middle Row:  5  6  7  8  9
Bottom Row: 10 11 12
Clock:       13 (Big button with clock display)
```

## Troubleshooting Images Not Showing

If images aren't displaying on the device, check the logs:

### 1. Check Configuration

```bash
source venv/bin/activate
ulanzi-manager validate config.yaml
```

Look for errors like:
```
ERROR:ulanzi_manager.cli:  - Button 0: image file not found: ./icons/firefox.png
```

### 2. Check Image Paths

Make sure image paths in config.yaml are correct:
```yaml
buttons:
  - image: ./icons/firefox.png    # Relative to config file location
    label: Firefox
    action: app
    params:
      name: firefox
```

Or use absolute paths:
```yaml
buttons:
  - image: /home/lucas/Works/VibeCodedProjects/ulanzi/icons/firefox.png
    label: Firefox
    action: app
    params:
      name: firefox
```

### 3. Check Image Format

Images must be:
- **Format**: PNG
- **Size**: 196×196 pixels
- **Color Space**: RGB or RGBA

Verify with:
```bash
file icons/firefox.png
identify icons/firefox.png  # If ImageMagick is installed
```

### 4. View Daemon Logs

Check what's happening when configuring:
```bash
tail -f ~/.local/share/ulanzi/daemon.log
```

Or run configure with verbose output:
```bash
source venv/bin/activate
ulanzi-manager configure config.yaml
```

Look for messages like:
```
INFO:ulanzi_manager.device:Set 10 button(s) with 10 image(s)
```

If it says `0 image(s)`, the images aren't being found.

### 5. Test Single Image

Test a single button with a known image:
```bash
source venv/bin/activate
ulanzi-manager test-image 0 ./icons/firefox.png --label "Test"
```

Check the logs to see if the image was sent:
```
DEBUG:ulanzi_manager.device:Added image for button 0: ./icons/firefox.png
```

## Common Issues

### Issue: "No config for button 13"

**Cause**: You pressed button 12 (the last button), but there's no button 13.

**Solution**: The device only has 13 buttons (0-12). Use debug mode to identify which button you pressed.

### Issue: Images not showing but no errors

**Cause**: Images might be in the ZIP but not displaying correctly.

**Solution**:
1. Check image format (must be PNG, 196×196)
2. Try regenerating images:
   ```bash
   python3 create_icons.py
   ```
3. Reconfigure device:
   ```bash
   ulanzi-manager configure config.yaml
   ```

### Issue: Some buttons show images, others don't

**Cause**: Missing or invalid image files for some buttons.

**Solution**:
1. Check config.yaml for missing image paths
2. Verify all referenced images exist
3. Use debug mode to identify which buttons need images

## Verbose Logging

For more detailed output, check the daemon logs:

```bash
# Real-time logs
tail -f ~/.local/share/ulanzi/daemon.log

# Last 50 lines
tail -50 ~/.local/share/ulanzi/daemon.log

# Search for errors
grep ERROR ~/.local/share/ulanzi/daemon.log
```

## Button Press Logging

When running the daemon, button presses are logged:

```
INFO:ulanzi_manager.daemon:Button 0 pressed (state=0)
INFO:ulanzi_manager.daemon:Executing action: app - Firefox
```

This shows:
- Which button was pressed (index)
- The button state
- What action was executed
- The button label

## Creating Custom Images

### Using Python PIL

```python
from PIL import Image, ImageDraw, ImageFont

# Create 196x196 image
img = Image.new('RGB', (196, 196), color='blue')
draw = ImageDraw.Draw(img)

# Add text
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
draw.text((98, 98), "OBS", fill='white', font=font, anchor='mm')

# Save
img.save('obs.png')
```

### Using ImageMagick

```bash
convert -size 196x196 xc:blue -pointsize 40 -fill white -gravity center \
  -annotate +0+0 "OBS" obs.png
```

### Using GIMP

1. Create new image: 196×196 pixels
2. Add your design
3. Export as PNG

## Testing Workflow

1. **Identify buttons**:
   ```bash
   ulanzi-manager debug
   ```

2. **Create/prepare images**:
   - 196×196 PNG files
   - Place in `icons/` directory

3. **Update config**:
   ```bash
   nano config.yaml
   ```

4. **Validate**:
   ```bash
   ulanzi-manager validate config.yaml
   ```

5. **Test single button**:
   ```bash
   ulanzi-manager test-image 0 icons/myimage.png
   ```

6. **Configure device**:
   ```bash
   ulanzi-manager configure config.yaml
   ```

7. **Check logs**:
   ```bash
   tail -f ~/.local/share/ulanzi/daemon.log
   ```

8. **Start daemon**:
   ```bash
   ulanzi-daemon config.yaml
   ```

## Getting Help

If images still aren't showing:

1. Run debug mode to identify buttons
2. Check logs for errors
3. Verify image files exist and are correct format
4. Test with a single button first
5. Check config.yaml syntax

Example debug session:
```bash
# Terminal 1: Run debug mode
source venv/bin/activate
ulanzi-manager debug

# Terminal 2: Check logs
tail -f ~/.local/share/ulanzi/daemon.log

# Terminal 3: Test configuration
source venv/bin/activate
ulanzi-manager configure config.yaml
```

---

**Need more help?** Check README.md or SETUP.md
