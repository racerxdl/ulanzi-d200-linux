#!/bin/bash
# Ulanzi D200 Manager Installation Script

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     Ulanzi D200 Manager - Installation Script             ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo

# Check if running from correct directory
if [ ! -f "setup.py" ]; then
    echo "✗ Error: setup.py not found. Run this script from the project root."
    exit 1
fi

install_desktop_shortcut() {
    local applications_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
    local icon_theme_dir="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor"
    mkdir -p "$applications_dir"
    install -m 644 ulanzi-config.desktop "$applications_dir/ulanzi-config.desktop"
    install -D -m 644 icons/ulanzi-d200.svg "$icon_theme_dir/scalable/apps/ulanzi-d200.svg"
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache --force --ignore-theme-index "$icon_theme_dir"
    fi
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$applications_dir"
    fi
    echo "   ✓ Ulanzi D200 Configuration added to the applications menu"
}

if [ "$#" -eq 1 ] && [ "$1" = "--desktop-only" ]; then
    install_desktop_shortcut
    exit 0
elif [ "$#" -ne 0 ]; then
    echo "Usage: bash install.sh [--desktop-only]"
    exit 2
fi

# Step 1: Validate setup
echo "1. Validating setup..."
echo "   ✓ Ready to install"

# Step 2: Install udev rule
echo "2. Installing udev rule..."
if [ -w "/etc/udev/rules.d/" ]; then
    sudo cp 99-ulanzi.rules /etc/udev/rules.d/
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    echo "   ✓ Udev rule installed"
else
    echo "   ⚠ Udev rule requires sudo. Run:"
    echo "     sudo cp 99-ulanzi.rules /etc/udev/rules.d/"
    echo "     sudo udevadm control --reload-rules"
    echo "     sudo udevadm trigger"
fi

# Step 3: Create config directories
echo "3. Creating configuration directories..."
mkdir -p ~/.config/ulanzi
mkdir -p ~/.local/share/ulanzi
echo "   ✓ Directories created"

# Step 4: Setup ~/.local/ulanzi with venv
echo "4. Setting up ~/.local/ulanzi with virtual environment..."
mkdir -p ~/.local/ulanzi
mkdir -p ~/.local/bin

# Create venv in ~/.local/ulanzi
echo "   Creating virtual environment..."
python3 -m venv ~/.local/ulanzi/venv

# Install package in the new venv
echo "   Installing package..."
~/.local/ulanzi/venv/bin/pip install -q -e .

# Create a simple wrapper that uses the venv
cat > ~/.local/bin/ulanzi-daemon << 'WRAPPER'
#!/bin/bash
# Wrapper for ulanzi-daemon using ~/.local/ulanzi/venv
exec ~/.local/ulanzi/venv/bin/ulanzi-daemon "$@"
WRAPPER

chmod +x ~/.local/bin/ulanzi-daemon
echo "   ✓ Virtual environment setup complete at ~/.local/ulanzi"
echo "   ✓ Wrapper script installed at ~/.local/bin/ulanzi-daemon"

# Step 5: Install stock icons and generate example config
echo "5. Installing stock icons and generating example configuration..."
icons_dir="$HOME/.config/ulanzi/icons"
if [ ! -e "$icons_dir" ] && [ ! -L "$icons_dir" ]; then
    mkdir -p "$icons_dir"
fi
if [ -d "$icons_dir" ] && [ ! -L "$icons_dir" ]; then
    for icon in icons/*.png; do
        destination="$icons_dir/${icon##*/}"
        # Preserve every existing entry, including dangling symlinks.
        if [ ! -e "$destination" ] && [ ! -L "$destination" ]; then
            cp -n --no-dereference -- "$icon" "$destination"
        fi
    done
    echo "   ✓ Stock icons installed without replacing existing entries"
else
    echo "   ⚠ Existing icons path is not a regular directory; leaving it unchanged"
fi
if [ ! -e ~/.config/ulanzi/config.yaml ] && [ ! -L ~/.config/ulanzi/config.yaml ]; then
    ~/.local/ulanzi/venv/bin/ulanzi-manager generate-config ~/.config/ulanzi/config.yaml
    echo "   ✓ Configuration generated at ~/.config/ulanzi/config.yaml"
else
    echo "   ✓ Configuration already exists"
fi

# Step 6: Install the configuration app and start its local UI service
echo "6. Installing the configuration app..."
install_desktop_shortcut
mkdir -p ~/.config/systemd/user
install -m 644 systemd/ulanzi-web.service ~/.config/systemd/user/ulanzi-web.service
install -m 644 systemd/ulanzi-daemon.service ~/.config/systemd/user/ulanzi-daemon.service
systemctl --user daemon-reload
systemctl --user enable --now ulanzi-web.service
echo "   ✓ Local configuration UI enabled for automatic startup"

echo
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              ✓ Installation Complete!                     ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo
echo "Next steps:"
echo "1. Reconnect your Ulanzi D200 device (if not already connected)"
echo "2. Edit configuration: nano ~/.config/ulanzi/config.yaml"
echo "3. Validate: ulanzi-manager validate ~/.config/ulanzi/config.yaml"
echo "4. Configure device: ulanzi-manager configure ~/.config/ulanzi/config.yaml"
echo "5. Open Ulanzi D200 Configuration from the applications menu"
echo "6. Start daemon: ulanzi-daemon ~/.config/ulanzi/config.yaml"
echo
echo "Optional - Enable systemd user service:"
echo "  systemctl --user enable ulanzi-daemon"
echo "  systemctl --user start ulanzi-daemon"
echo
echo "For more info, see README.md or QUICKSTART.md"
echo
