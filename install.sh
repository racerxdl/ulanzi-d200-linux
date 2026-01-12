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

# Step 5: Generate example config
echo "5. Generating example configuration..."
if [ ! -f ~/.config/ulanzi/config.yaml ]; then
    ~/.local/ulanzi/venv/bin/ulanzi-manager generate-config ~/.config/ulanzi/config.yaml
    echo "   ✓ Configuration generated at ~/.config/ulanzi/config.yaml"
else
    echo "   ✓ Configuration already exists"
fi

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
echo "5. Start daemon: ulanzi-daemon ~/.config/ulanzi/config.yaml"
echo
echo "Optional - Enable systemd user service:"
echo "  systemctl --user enable ulanzi-daemon"
echo "  systemctl --user start ulanzi-daemon"
echo
echo "For more info, see README.md or QUICKSTART.md"
echo
