# Icon Auto-Generation Feature

## Overview

A new feature has been added that allows users to automatically generate and cache button icons directly from configuration files, eliminating the need to manually create PNG images.

## How It Works

1. **Define icon specifications** in the config.yaml file using `icon_spec`
2. **Automatic generation** happens when the config is loaded
3. **Smart caching** stores generated icons with unique filenames based on their spec hash
4. **Reusable** - if the same spec is used multiple times, the cached version is reused

## Features

- **No PIL knowledge required** - simple YAML configuration
- **Three icon types**: solid colors, text-based, and gradients
- **Automatic caching** - icons are generated only once per unique spec
- **Type validation** - unsupported icon types are rejected, even if a matching cached image exists
- **Fallback fonts** - uses system fonts if custom fonts aren't available

## Module Structure

### `icon_generator.py`
Main module for icon generation:
- `IconSpec`: Represents an icon specification
- `IconGenerator`: Generates icons from specs
- Supports: solid colors, text icons, and gradients

### Updated `config.py`
- Added `icon_spec` field to `ButtonConfig`
- New `_generate_icons()` method processes specs on config load
- Updated validation to check icon specs
- Graceful fallback if Pillow is not installed

## Usage Examples

### Solid Color Icon
```yaml
- icon_spec:
    type: solid
    color: '#0066FF'
  label: "Blue Button"
  action: command
  params:
    cmd: "echo 'pressed'"
```

### Text Icon
```yaml
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

### Gradient Icon
```yaml
- icon_spec:
    type: gradient
    color: '#0066FF'
    text_color: '#FF6600'
  label: "Gradient"
  action: command
  params:
    cmd: "echo 'gradient'"
```

## Configuration Options

All icon specs:
- `type`: 'solid', 'text', or 'gradient' (default: 'solid'); 'emoji' and 'icon' are not supported
- `color`: Background or start color (hex: '#RRGGBB' or name: 'blue', 'red', etc.)
- `size`: Icon dimensions (default: 196×196)

Text type specific:
- `text`: Text to display (required for text type)
- `text_color`: Text color (default: white)
- `font_size`: Font size 1-150 pixels (default: 40)
- `font`: Path to TTF font file (optional)

## Files Modified

1. **ulanzi_manager/icon_generator.py** (new)
   - IconSpec class for spec validation
   - IconGenerator class for generation and caching

2. **ulanzi_manager/config.py**
   - Added `icon_spec` field to ButtonConfig
   - Added `_generate_icons()` method
   - Updated parsing and validation logic

3. **README.md**
   - Added "Auto-Generate Icons" section with examples
   - Documentation of all icon spec options

## Testing

The isolated unittest suite runs with:

```bash
python -m unittest test_icon_generation
```

1. **test_icon_generation.py**
   - Checks solid, text, and gradient pixel output and dimensions
   - Checks unsupported-type rejection with and without cached images
   - Uses temporary directories; does not create repository icons or load user configuration

2. **examples_icon_usage.py** (usage examples, not a test suite)
   - Simple usage examples
   - Shows programmatic API usage

3. **config.example-autogen.yaml**
   - Example configuration with various icon specs
   - Demonstrates all feature types and options

## Benefits

✅ **Faster setup** - No need to create icons manually
✅ **Easy maintenance** - Change icon appearance by editing config
✅ **Consistent quality** - All icons are properly sized and formatted
✅ **Smart caching** - Generated icons are reused automatically
✅ **Flexible** - Mix manual PNG files and auto-generated icons
✅ **Compatible** - Works alongside existing 'image' field approach

## Backward Compatibility

The feature is fully backward compatible:
- Existing configs with `image` field work unchanged
- Users can mix `image` and `icon_spec` across buttons
- All validation handles both approaches

## Error Handling

The system provides clear error messages:
- Invalid icon specs are reported during config validation
- Missing required fields (e.g., text for text type) are caught
- Invalid color formats are detected
- Unsupported types raise `ValueError` from both `generate()` and `generate_from_dict()` before cache lookup
- Font issues fall back to system defaults gracefully
