# Debug Guide - Ulanzi D200 Manager

Commands below use your local `config.yaml` in the repository root. For a new
configuration, run `cp config.example.yaml config.yaml` before editing; the local
copy is ignored by Git. Existing configurations do not need to be copied again.

The daemon and web UI automatically provision a missing configuration and its
parent directories on first launch. This fallback has 13 unconfigured buttons
and an action-free statistics display on button 14; it needs no external icons.
Existing configuration files are never replaced by first-run provisioning.
Explicit `ulanzi-manager validate` still reports a missing file rather than
creating one, so a mistyped validation path cannot silently create a profile.

## Background Editing and Application Icons

**Editar fundo atual** reopens the saved background settings. Newly uploaded originals are immutable `mosaic-source-<hash>` files in the configured icons directory; keep them alongside the generated tiles when backing up configurations and layouts. They are intentionally absent from the button icon picker. Legacy backgrounds are reconstructed from existing tiles, so previously cropped or darkened detail cannot be restored. The editor previews the actual generated tiles, including the wide crop when enabled; **Aplicar fundo nos botões** changes the draft and **Salvar e aplicar** persists it to the device.

Background-only disabled faces are saved as button entries with `enabled: false` and a PNG `background_tile`, rather than `null`. The daemon draws that tile without a label or foreground and forces `action_enabled` off, even if a saved action remains in the entry. Such actions do not establish OBS connections. Grid, editor, and saved-layout previews keep the background undimmed. Older `null` slots are rebuilt from the persisted background source when opened or saved; opening alone does not rewrite `config.yaml`. Use **Salvar e aplicar** to persist and display the repaired layout. The wide slot is filled only when **Include wide display in background** is selected.

**Margem do conteúdo** is per-button foreground padding, not a mosaic editor setting. Valid `content_margin` values are integers from 0 through 48 pixels; missing fields default to zero. Normal icon scaling uses the remaining inset area, while wide GIFs and statistics preserve their aspect ratio over a full-size background tile (or black when none exists). Wide **Imagem de fundo** ignores this setting. If content looks unexpectedly small, check both icon size and margin; large margins also reduce the rendered size of wide metrics. The UI preview updates immediately, but **Salvar e aplicar** is required to update the device.

Choosing an installed application on buttons 1–13 imports its icon without launching the app. Missing icons preserve the current image; import errors appear as a UI notification. Button 14 never replaces its GIF or statistics merely because an application action was selected. If PNG/SVG decoding or theme resolution fails, check the native GTK/GdkPixbuf dependencies in [INSTALL.md](INSTALL.md), the system MIME database, and the web-service journal:

```bash
journalctl --user -u ulanzi-web.service -n 100 --no-pager
```

For NixOS, inspect `ULANZI_GI_PYTHON` in both service environments and use
the runtime in [INSTALL.md](INSTALL.md#nixos). Missing `gi` means the selected
Python lacks PyGObject; missing namespaces require `GI_TYPELIB_PATH`; SVG
decoding requires the librsvg loader. The same selector is used for icons and
desktop activation. It tests available interpreters without launching an app.
An explicit invalid override fails instead of silently choosing another Python.
Wrappers may set their own Python paths; do not add `-I` or `-E`.
For activation errors, also check the daemon's graphical-session environment
and journal, not just the web service's environment.


## Applications Closing When Applying Configuration

**Salvar e aplicar** restarts `ulanzi-daemon.service`. Applications and commands must run in separate transient `run-*.scope` units, not inside that service's cgroup. Check membership with:

```bash
systemd-cgls --user-unit ulanzi-daemon.service
cat /proc/APP_PID/cgroup
```

If an application belongs to `ulanzi-daemon.service`, it was opened by an older direct-launch version and will be terminated by the service's normal `KillMode=control-group` shutdown. Open existing applications from the system menu before restarting to load the corrected launcher. New launches use independent user scopes and survive daemon restarts. Do not weaken the service's kill policy or rely on `nohup`/`setsid`: neither moves a process out of its systemd cgroup. If a new launch fails, inspect `journalctl --user -u ulanzi-daemon.service`; a running user manager and a compatible `systemd-run` are required.

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
  - image: /absolute/path/to/ulanzi-d200-linux/icons/firefox.png
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

### Issue: The default layout returns after a firmware crash or power cycle

**Cause**: The layout in `config.yaml` is host-managed. A firmware UI crash can
reset the visible buttons without disconnecting USB; reconnect detection alone
does not catch it. Separately, omitting hidapi's required Report ID 0 can truncate
ZIP continuation chunks. The old padding workaround could then exhaust its
retry search, preventing the daemon from restoring the saved layout.

**Solution**: Unsolicited firmware configuration/font requests (`0x010b`) now
reopen the HID session and reapply the current `~/.config/ulanzi/config.yaml`,
including app buttons and the wide display. The full-upload synchronization
consumes normal ZIP acknowledgements so they do not cause recovery loops.
Heartbeat/info packets are not treated as crashes. Correct HID report framing
preserves all ZIP bytes without padding retries.

HID transport failures still terminate the stale daemon. The enabled systemd
user service reconnects to a power-cycled or newly connected USB device.
Stale button reports are discarded before actions are enabled. Recovery does
not overwrite the active configuration or named presets.

Check the recovery service with:

```bash
systemctl --user is-enabled ulanzi-daemon.service
systemctl --user status ulanzi-daemon.service
```

The service should be `enabled` and `active` while the D200 is connected.

### Issue: Device flickers, freezes, or repeatedly asks to reconnect

**Causes**:
- Incorrect HID report framing could truncate ZIP data and make the former
  padding search consume a CPU core before startup failed.
- Rebuilding and recompressing the same partial frame archive on every GIF
  cycle wastes CPU and can make frame delivery uneven.
- An overly frequent firmware heartbeat causes unnecessary redraws.

**Solution**: Each hidapi write includes Report ID 0 followed by the complete
1024-byte protocol packet; failed or short writes are reported as errors. The
initial layout selects the wide-display mode, then sends its first decoded PNG
frame after the full import finishes. The complete GIF is never sent as an
image in the startup archive. Prepared frame archives are cached and reused on
subsequent animation cycles. Button polling remains at 50 ms, while the
firmware heartbeat runs once per second. A failed HID transfer reaches systemd
so the service can restart after USB reconnection.

After startup, confirm the daemon logged `Daemon started successfully`. CPU
and memory should remain stable instead of continuously increasing.


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

### Issue: Statistics updates delay button presses or grow memory usage

Statistics collection and image rendering run on a single worker. The main
loop continues button polling and keepalive requests, and remains the only HID
writer. Only one completed frame is retained for handoff. Reconfiguration and
shutdown join the producer before replacing the image/history state; unexpected
worker failures propagate to the supervisor rather than silently freezing the
display.

One-shot statistics frames are not stored in the archive cache. Reusable
layout/GIF archives use an LRU capped at 16 MiB of compressed payloads and
128 entries; an individual oversized archive is sent without retention.

If statistics stop updating, inspect the user service journal for the original
worker error and verify that the configured `Restart=on-failure` unit is active.

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
