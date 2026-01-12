#!/usr/bin/env python3
"""Test script for icon generation functionality"""

import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from ulanzi_manager.icon_generator import IconGenerator, IconSpec

def test_icon_generation():
    """Test icon generation with various specs"""

    test_dir = project_root / "test_icons"
    test_dir.mkdir(exist_ok=True)

    generator = IconGenerator(cache_dir=test_dir)

    # Test 1: Solid color
    print("Test 1: Solid color icon...")
    spec1 = IconSpec({
        'type': 'solid',
        'color': '#0066FF'
    })
    path1 = generator.generate(spec1, force=True)
    print(f"  ✓ Generated: {path1}")

    # Test 2: Text icon
    print("Test 2: Text icon...")
    spec2 = IconSpec({
        'type': 'text',
        'color': '#FF6600',
        'text': 'REC',
        'text_color': '#FFFFFF',
        'font_size': 70
    })
    path2 = generator.generate(spec2, force=True)
    print(f"  ✓ Generated: {path2}")

    # Test 3: Gradient icon
    print("Test 3: Gradient icon...")
    spec3 = IconSpec({
        'type': 'gradient',
        'color': '#0066FF',
        'text_color': '#FF6600'
    })
    path3 = generator.generate(spec3, force=True)
    print(f"  ✓ Generated: {path3}")

    # Test 4: Test caching (should use cached version)
    print("Test 4: Testing cache...")
    path2_cached = generator.generate(spec2)
    assert path2 == path2_cached, "Cache not working correctly"
    print(f"  ✓ Cache working correctly: {path2_cached}")

    print("\n✅ All tests passed!")
    return True

def test_config_parsing():
    """Test configuration with icon specs"""
    from ulanzi_manager.config import ConfigParser

    print("\nTesting config parsing with icon specs...")

    config_path = project_root / "config.example-autogen.yaml"
    if not config_path.exists():
        print(f"  ⚠ Config file not found: {config_path}")
        return False

    try:
        config = ConfigParser.load(str(config_path))
        print(f"  ✓ Loaded config with {len(config.buttons)} buttons")

        # Check if icons were generated
        for button in config.buttons:
            if button.icon_spec and button.image:
                print(f"  ✓ Button {button.index}: Generated icon at {button.image}")

        # Validate config
        errors = ConfigParser.validate(config)
        if errors:
            print(f"  ⚠ Validation errors: {errors}")
            return False

        print("  ✓ Config validation passed")
        return True

    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    try:
        test_icon_generation()
        test_config_parsing()
    except ImportError as e:
        print(f"Error: {e}")
        print("Make sure Pillow (PIL) is installed: pip install pillow")
        sys.exit(1)
