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
- 🔌 **Automatic Restore** - Reapply the saved configuration after a firmware UI crash, D200 power cycle, or USB reconnect
- 🖥️ **Local Web UI** - Edit buttons, upload icons, and apply changes from a browser
- 💾 **Saved Layouts** - Store, preview, restore, update, and delete named layout presets
- **Wide Display** - Show live CPU, RAM, and GPU utilization or an animated GIF on button 14, with an optional button action
- **Background Editor** - Preview, zoom, and darken one static background across the 13 regular buttons, optionally extending it into the wide display while preserving overlaid app icons

## Quick Start

Requires Python 3.9 or newer.

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

When the daemon or web UI starts with a missing configuration file, it creates
the parent directories and a self-contained default profile automatically:
13 unconfigured app buttons and live statistics on the wide display, with no
button actions enabled. No external icons or application commands are required.
The complete file is published atomically without replacing an existing
configuration, including one created by another startup process.

## Web UI

Start the local configuration interface:

```bash
ulanzi-web --config ~/.config/ulanzi/config.yaml
```

Then open [http://127.0.0.1:8765](http://127.0.0.1:8765). The interface edits the 13 app buttons plus the fixed wide button 14, rearranges apps by drag and drop or by choosing a position, and previews saved layout presets before loading them.

Upload a static image or choose **Editar fundo atual** to reopen the background editor. Resize from 25% to 200%, darken from 0% to 80%, and preview the exact generated 5×3 tiles. Below 100%, the image is centered on black; at 100% it fills the screen; above 100% it zooms and crops. The original image and editing settings persist in the active configuration and saved layouts, so later edits do not repeatedly resize or darken an already processed image. Legacy backgrounds are reconstructed from their saved tiles without requiring another upload; previously cropped or darkened detail cannot be recovered.

Enable **Include wide display in background** to apply the final two cells to button 14, including behind its statistics; leave it disabled to preserve its current content. Existing app icons remain overlaid at their configured sizes, and button actions remain unchanged. The interface also configures brightness and OBS, validates the resulting YAML, and restarts `ulanzi-daemon` when **Save and apply** is selected. Saved layouts are stored under `~/.config/ulanzi/layouts/`; loading one opens it in the editor, and **Save and apply** makes it the active configuration used after device reconnects and power cycles.

IPv6 loopback is also supported: run `ulanzi-web --host ::1` and open
`http://[::1]:8765`. Requests accept only local IPv4, IPv6, or `localhost`
authorities; malformed or nonlocal Host headers are rejected.

Choose **Abrir aplicativo** in the button editor to search and select installed desktop applications. The list reads visible Linux `.desktop` entries from XDG application directories and Flatpak/Snap exports, using localized names and honoring user overrides. Selecting an app stores its stable launcher path in `params.name`; the daemon opens it with a native GTK/GIO helper, preserving launcher arguments, file placeholders, and packaging-specific commands. On buttons 1–13, selection also imports the application's native icon as a transparent 196×196 PNG, resolving theme inheritance, exported icons, and absolute raster/SVG paths. The configured icon size and background are preserved. A missing icon leaves the current image unchanged, and button 14 retains its GIF or statistics when an app action is selected. Labels are not changed automatically. **Informar executável manualmente** retains the existing executable-name workflow. Reload the page to discover newly installed apps.

The desktop helper waits for `launch_uris_async`/`launch_uris_finish` to complete before exiting, so a first press opens D-Bus-activated apps rather than merely starting their service. It uses the graphical launch context and does not retry or dispatch a second activation. Launch work runs in a separate process, keeping button polling and display updates responsive; activation failures reach the daemon journal. The helper uses `/usr/bin/python3` with system PyGObject, GDK 3, and GioUnix introspection (GLib 2.80+), not the virtualenv interpreter. On Ubuntu/Debian these bindings are supplied by `python3-gi`, `gir1.2-gtk-3.0`, and `gir1.2-glib-2.0`.

Icon import additionally uses the system GdkPixbuf decoders and SVG loader (`librsvg2-common` on Ubuntu/Debian). These native dependencies are installed outside the virtualenv; see [the installation guide](docs/INSTALL.md). Icon-loading failures are reported in the UI and web-service journal.

Application names honor inline `Name[locale]` translations first. Entries using `X-Ubuntu-Gettext-Domain` or `X-GNOME-Gettext-Domain` also read installed gettext catalogs from `/usr/share/locale` and `/usr/share/locale-langpack`; for example, GNOME **Settings** appears as **Configurações** in Brazilian Portuguese. When no translation is installed, the original application name remains available.

Saved layouts appear as selectable cards, each with its own visual preview of all 14 slots, including icon/background composition and the wide display. Click a card to select it for **Carregar** or **Excluir**; selection alone does not load or apply a layout. The gallery updates after saving or deleting a preset and highlights the selected card. **Carregar** still opens the preset in the editor, and **Salvar e aplicar** is required to change the device.

The server binds to `127.0.0.1` by default and is not exposed to the network.

### Desktop shortcut and startup

The full `bash install.sh` installation adds **Ulanzi D200 Configuration**
(**Ulanzi D200 — Configuração** in Brazilian Portuguese) to the applications
menu and enables `ulanzi-web.service` for automatic startup. The shortcut opens
the saved-layout gallery in the default browser at
`http://127.0.0.1:8765/#layoutsTitle`; it uses `xdg-open` from `xdg-utils`.

The installer seeds stock PNGs in `~/.config/ulanzi/icons` before starting the
UI, without replacing existing files or symlinks. It installs both user service
units; only the web service is enabled automatically. Enable the daemon as
shown below when automatic device restoration is desired.

The desktop icon uses the [official Ulanzi logo](https://www.ulanzi.com/cdn/shop/files/Ulanzi_logo.svg?v=1731031787)
from the [Ulanzi website](https://www.ulanzi.com/), installed locally as
`icons/hicolor/scalable/apps/ulanzi-d200.svg` under the XDG data directory.
Ulanzi retains its logo and trademark rights; the code's MIT license does not
grant rights to this third-party branding. This is an unofficial project;
confirm the upstream project's branding policy before redistributing the logo.

For an existing installation with the UI service already configured, install
only the shortcut without changing the environment, configuration, or services:

```bash
bash install.sh --desktop-only
```

The desktop entry is installed in
`${XDG_DATA_HOME:-$HOME/.local/share}/applications`. The UI must be running
when opening the shortcut. Select a saved layout, click **Carregar**, then
**Salvar e aplicar** to make it the active device configuration.

To restore that configuration automatically after restarting the computer,
keep both installed user services enabled:

```bash
systemctl --user enable --now ulanzi-daemon.service ulanzi-web.service
```

On startup, the daemon reads the last active `~/.config/ulanzi/config.yaml`.
Named presets remain saved, but saving a preset alone does not activate it.
If the D200 is disconnected during startup, the enabled daemon service retries
the connection and restores the active configuration when the device returns.

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

After a D200 power cycle or USB reconnect, the host daemon reloads the active saved configuration and restores all app buttons before starting wide-display updates. It also handles the firmware's unsolicited configuration/font request (`0x010b`) after an internal UI crash, reopening HID and reloading the saved YAML without requiring a USB disconnect or manual Apply. Normal full-upload acknowledgements use the same command and are consumed by the upload barrier, so they do not trigger restoration loops; ordinary heartbeat/info packets do not trigger restoration.

Full layout uploads use native `GETBASE` (`0x0003`) replies (`0x0303`) as barriers before and after the ZIP transfer. This serializes startup with the firmware worker and prevents wide-display traffic from interfering with the initial import through the shared `/tmp/temp.zip` file. Every hidapi write includes the required unnumbered Report ID byte (`0x00`) before the 1024-byte protocol report. Without that prefix, the USB backend can discard real ZIP bytes at chunk boundaries, producing corrupted archives; trying to compensate with ZIP padding can also exhaust the old retry search. Standard ZIP archives now preserve all byte values without dummy padding or sentinel files, and failed/short writes propagate as transport errors.

Missing, malformed, or negative synchronization replies fail startup instead of reporting a completed configuration. The enabled user service reconnects after USB removal. Restoration requires the host daemon to be running; the firmware may briefly show its factory menu while restarting. Active configuration and named presets remain stored on the computer and are never overwritten by the recovery process.

**Button Layout:**
```
0  1  2  3  4
5  6  7  8  9
10 11 12 [13: wide display]
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
| Start web UI | `ulanzi-web --config ~/.config/ulanzi/config.yaml` |

## Image Preparation

App buttons use 196×196 PNG images in RGB/RGBA. Button 14 can display host CPU, RAM, and GPU utilization, refreshed with a 1.5-second target cadence, or an animated GIF. The Web UI fits GIFs to the native 458×196 wide display, preserves frame timing, and limits them to 300 frames and 8 MB. Enable **Usar também como botão** to assign an application, command, keyboard shortcut, or OBS action independently of the selected display mode.

Uploads retain an 8 MiB decoded/prepared image limit; the bounded JSON request
limit separately accommodates base64 expansion. Composite icons are keyed by
both input images' contents, so replacing a source or background under the
same filename takes effect on the next save/apply.

Host CPU utilization is aggregated across all logical cores on a 0–100% scale, not a single core or a process's CPU column. `/proc/stat` guest counters are not added twice. RAM follows the htop 3.4 numeric used/total meter: `(MemTotal - MemFree - Buffers - Cached - SReclaimable + Shmem) / MemTotal`, rather than `MemTotal - MemAvailable`; see its [Linux accounting](https://github.com/htop-dev/htop/blob/3.4.1/linux/LinuxMachine.c) and [numeric memory meter](https://github.com/htop-dev/htop/blob/3.4.1/MemoryMeter.c). GPU utilization comes from Linux DRM `gpu_busy_percent`, or `nvidia-smi` when that sensor is absent. Device values are rounded to integer percentages. Collection and image updates use a separate 1.5-second timer, matching htop's configured `delay=15`; USB keepalive remains at 1 second, and GIF timing is unchanged. This aligns the target frequency, not the phase or the data snapshots of the two programs. Scheduler, processing, and USB latency can introduce small timing differences.
In **CPU, RAM e GPU** mode, choose columns, rows, or a compact layout; adjust the value text from 18 to 48 px; and pick separate value and label colors for each of CPU, RAM, and GPU. Older layouts retain their previous common colors until you customize them individually. The preview uses example values, while the device shows live utilization. Settings persist with the active configuration and saved layout presets. Metrics are rendered over the static wide background, or black when no background is configured. Applying a background with the wide-display option enabled preserves the statistics mode.
**Visualização das métricas** offers text, segmented utilization bars inspired by htop, or **Linhas contínuas · último minuto**: a single shared chart with three continuous lines and no area fill. Each metric has a separate **Linha** color selector, independent of its value and label colors; matching swatches below the values identify the lines. Existing layouts without line colors use orange for CPU, green for RAM, and cyan for GPU. Bars and charts retain the background, fonts, sizes, and per-metric colors. The chart uses a 0–100% vertical scale and a rolling 60-second time axis, with up to 41 real samples at the 1.5-second cadence; empty time is not fabricated. History starts fresh after restarting or applying a layout. The selected visualization and line colors persist with configurations and presets. Editor charts use example data; device charts collect host metrics at the configured cadence. Text-layout controls are shown only for text mode, and line-color controls only for history mode.
The metrics font selectors offer nine families: DejaVu Sans, DejaVu Sans Mono, DejaVu Serif, Ubuntu, Ubuntu Mono, Noto Sans, Noto Serif, Liberation Sans, and Liberation Serif. Each supports normal, bold, italic, and bold-italic styles. Browser previews and device rendering use the same bundled font files without external downloads or host-font dependencies; Ubuntu variable fonts explicitly select regular or bold weights. Font selections apply to values and labels, persist with layouts, and preserve existing selections. Redistribution licenses are included in `ulanzi_manager/static/fonts/LICENSE*`.
The wide-button editor places the GIF preview above its controls, without compositing the static background into GIF mode. Statistics preview text stays above the background; the desktop editor scrolls internally when its controls exceed the available height.

Statistics collection and rendering run on one background worker, handing off
only the latest complete frame to the polling loop. Only that loop writes HID;
slow GPU queries do not block button reads or keepalive requests. Shutdown and
configuration recovery join the worker before replacing rendering state.
Reusable layout/GIF ZIP archives use a 16 MiB, 128-entry LRU; transient statistics
frames bypass that cache.

Custom switches show a visible outline when reached with keyboard navigation.

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
Supported generated icon types are `solid`, `gradient`, and `text`.
Other types are rejected before consulting the image cache.


## Troubleshooting

| Issue | Solution |
|-------|----------|
| Device not found | `sudo cp 99-ulanzi.rules /etc/udev/rules.d/`, reload, reconnect |
| OBS not connecting | Enable WebSocket Server in OBS (Tools → WebSocket Server Settings) |
| Keyboard shortcuts fail | Install xdotool: `sudo apt install xdotool` |
| Permission denied | Ensure udev rule installed; reconnect device |

See [docs/DEBUG.md](docs/DEBUG.md) for detailed troubleshooting.

## Local configuration and contributing

The repository ships [config.example.yaml](config.example.yaml) as a generic
example. Keep your active configuration at `~/.config/ulanzi/config.yaml`.
For local experiments in the source tree, copy the example to `config.yaml`;
that local file is ignored and is not part of the shipped example.

Virtual environments (including `.venv/`), local configuration backups, saved
layout files in `/layouts/`, and generated icon caches are ignored by Git.
Do not include personal layouts, uploaded images, credentials, or device
identifiers in a pull request. Preserve bundled third-party license notices.
Only `hidapi`, `pyyaml`, `obsws-python`, and `pillow` are runtime Python
dependencies; system desktop integration dependencies are described above.

Before submitting changes, run:

```bash
python -m unittest discover -q
python verify.py
ulanzi-manager validate config.example.yaml
```

## Project Info

**Logs:** `~/.local/share/ulanzi/daemon.log` (view with `tail -f`)

**License:** MIT

**References:**
- [Ulanzi D200 Protocol](https://github.com/redphx/strmdck)
- [OBS WebSocket](https://github.com/obsproject/obs-websocket)

---

*Yes, I vibecoded that and manually fixed some wrong stuff.*