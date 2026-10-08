#!/usr/bin/env python3
"""Final verification script"""

import sys
from pathlib import Path

print("=" * 60)
print("ULANZI D200 MANAGER - FINAL VERIFICATION")
print("=" * 60)

# Check all required files
required_files = [
    'ulanzi_manager/__init__.py',
    'ulanzi_manager/device.py',
    'ulanzi_manager/config.py',
    'ulanzi_manager/actions.py',
    'ulanzi_manager/daemon.py',
    'ulanzi_manager/cli.py',
    'ulanzi_manager/web.py',
    'ulanzi_manager/static/index.html',
    'ulanzi_manager/static/style.css',
    'ulanzi_manager/static/app.js',
    'setup.py',
    'requirements.txt',
    'config.example.yaml',
    'README.md',
    'docs/QUICKSTART.md',
    'docs/INSTALL.md',
    'docs/PROJECT_SUMMARY.md',
    'systemd/ulanzi-daemon.service',
]

print("\n1. Checking required files...")
all_exist = True
for file in required_files:
    exists = Path(file).exists()
    status = "✓" if exists else "✗"
    print(f"   {status} {file}")
    if not exists:
        all_exist = False

if not all_exist:
    print("\n✗ Some files are missing!")
    sys.exit(1)

# Check icons
print("\n2. Checking placeholder icons...")
icons_dir = Path('icons')
if icons_dir.exists():
    icon_files = list(icons_dir.glob('*.png'))
    print(f"   ✓ Found {len(icon_files)} icon files")
else:
    print("   ✗ Icons directory not found!")
    sys.exit(1)

# Test imports
print("\n3. Testing Python imports...")
try:
    from ulanzi_manager.device import UlanziDevice, CommandProtocol
    print("   ✓ device module")
    from ulanzi_manager.config import ConfigParser, Config
    print("   ✓ config module")
    from ulanzi_manager.actions import ActionExecutor
    print("   ✓ actions module")
    from ulanzi_manager.daemon import UlanziDaemon
    print("   ✓ daemon module")
    from ulanzi_manager.cli import UlanziCLI
    print("   ✓ cli module")
except Exception as e:
    print(f"   ✗ Import failed: {e}")
    sys.exit(1)

# Test configuration
print("\n4. Testing configuration...")
try:
    config = ConfigParser.load('config.example.yaml')
    print(f"   ✓ Config loaded with {len(config.buttons)} buttons")
    
    errors = ConfigParser.validate(config)
    if errors:
        print(f"   ✗ Validation errors: {errors}")
        sys.exit(1)
    print("   ✓ Config validation passed")
except Exception as e:
    print(f"   ✗ Config test failed: {e}")
    sys.exit(1)

# Test CLI
print("\n5. Testing CLI...")
try:
    from ulanzi_manager.cli import UlanziCLI
    cli = UlanziCLI()
    print("   ✓ CLI initialized")
except Exception as e:
    print(f"   ✗ CLI test failed: {e}")
    sys.exit(1)

# Test action executor
print("\n6. Testing action executor...")
try:
    executor = ActionExecutor()
    print("   ✓ Action executor initialized")
    print(f"   ✓ Handlers: {list(executor.handlers.keys())}")
except Exception as e:
    print(f"   ✗ Action executor test failed: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✓ ALL VERIFICATION TESTS PASSED!")
print("=" * 60)
print("\nNext steps:")
print("1. Activate venv: source venv/bin/activate")
print("2. Generate config: ulanzi-manager generate-config ~/.config/ulanzi/config.yaml")
print("3. Edit config: nano ~/.config/ulanzi/config.yaml")
print("4. Validate: ulanzi-manager validate ~/.config/ulanzi/config.yaml")
print("5. Configure device: ulanzi-manager configure ~/.config/ulanzi/config.yaml")
print("6. Start daemon: ulanzi-daemon ~/.config/ulanzi/config.yaml")
print("\nFor more info, see README.md or QUICKSTART.md")
