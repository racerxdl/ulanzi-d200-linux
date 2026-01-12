#!/usr/bin/env python3
"""Example: How to use the IconGenerator programmatically"""

from pathlib import Path
from ulanzi_manager.icon_generator import IconGenerator

# Create an icon generator (icons will be saved in ./icons directory)
generator = IconGenerator(cache_dir=Path('./icons'))

# Example 1: Generate a simple solid color icon
solid_icon = generator.generate_from_dict({
    'type': 'solid',
    'color': '#0066FF'  # Blue
})
print(f"Solid icon saved to: {solid_icon}")

# Example 2: Generate a text icon
text_icon = generator.generate_from_dict({
    'type': 'text',
    'color': '#FF6600',     # Orange background
    'text': 'REC',
    'text_color': '#FFFFFF',  # White text
    'font_size': 70
})
print(f"Text icon saved to: {text_icon}")

# Example 3: Generate a gradient icon
gradient_icon = generator.generate_from_dict({
    'type': 'gradient',
    'color': '#0066FF',      # Start color
    'text_color': '#FF6600'  # End color
})
print(f"Gradient icon saved to: {gradient_icon}")

# All icons are automatically cached by hash
# If you call generate_from_dict with the same spec again,
# it will return the cached file instead of regenerating

print("\n✅ Icons generated successfully!")
print("Use these in your config.yaml with 'image: <path_to_icon>'")
