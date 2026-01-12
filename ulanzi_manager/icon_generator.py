"""Icon generation and caching for Ulanzi buttons"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Any, Tuple
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Default icon size for Ulanzi D200
DEFAULT_ICON_SIZE = (196, 196)


class IconSpec:
    """Represents an icon specification for generation"""

    def __init__(self, spec_dict: Dict[str, Any]):
        """
        Initialize IconSpec from a dictionary

        Expected keys:
        - type: 'solid', 'gradient', 'text', 'emoji', 'icon' (required)
        - color: background color as hex string '#RRGGBB' or name
        - text: text to display (for type='text')
        - text_color: color of text as hex string or name (default: white)
        - font_size: font size (default: 60)
        - font: font name or path (default: system default)
        - size: tuple (width, height) or single int (default: 196x196)
        """
        self.spec_dict = spec_dict
        self.type = spec_dict.get('type', 'solid')
        self.color = spec_dict.get('color', '#0000FF')
        self.text = spec_dict.get('text', '')
        self.text_color = spec_dict.get('text_color', '#FFFFFF')
        self.font_size = spec_dict.get('font_size', 40)
        self.font = spec_dict.get('font', None)

        # Parse size
        size = spec_dict.get('size', DEFAULT_ICON_SIZE)
        if isinstance(size, (list, tuple)):
            self.size = tuple(size)
        else:
            self.size = (size, size)

    def get_hash(self) -> str:
        """Get unique hash for this icon spec"""
        spec_str = json.dumps(self.spec_dict, sort_keys=True)
        return hashlib.sha256(spec_str.encode()).hexdigest()[:16]

    def validate(self) -> list:
        """Validate the icon spec and return list of errors"""
        errors = []

        valid_types = ['solid', 'gradient', 'text', 'emoji', 'icon']
        if self.type not in valid_types:
            errors.append(f"Invalid icon type '{self.type}'. Must be one of: {', '.join(valid_types)}")

        if self.type in ['solid', 'gradient', 'text']:
            if not self._is_valid_color(self.color):
                errors.append(f"Invalid color '{self.color}'")

        if self.type == 'text' and not self.text:
            errors.append("Text type requires 'text' field")

        if self.font_size < 1 or self.font_size > 150:
            errors.append(f"font_size must be between 1 and 150, got {self.font_size}")

        if not isinstance(self.size, (tuple, list)) or len(self.size) != 2:
            errors.append(f"size must be a tuple/list of 2 integers")

        return errors

    @staticmethod
    def _is_valid_color(color: str) -> bool:
        """Check if color string is valid (hex or named color)"""
        if isinstance(color, str):
            if color.startswith('#'):
                try:
                    int(color[1:], 16)
                    return True
                except ValueError:
                    return False
            # Named colors are handled by PIL
            return True
        return False


class IconGenerator:
    """Generates icon images from specifications"""

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize icon generator

        Args:
            cache_dir: Directory to cache generated icons (default: ./icons)
        """
        self.cache_dir = cache_dir or Path('./icons')
        self.cache_dir.mkdir(exist_ok=True)

    def generate(self, spec: IconSpec, force: bool = False, button_index: Optional[int] = None) -> Path:
        """
        Generate an icon from spec or return cached version

        Args:
            spec: IconSpec instance
            force: Force regeneration even if cached
            button_index: Optional button index for specific filenames

        Returns:
            Path to generated icon file
        """
        if button_index is not None:
            cache_path = self.cache_dir / f"button_icon_{button_index}.png"
        else:
            cache_path = self.cache_dir / f"icon_{spec.get_hash()}.png"

        # Return cached version if exists and not forcing
        if cache_path.exists() and not force:
            logger.info(f"Using cached icon: {cache_path}")
            return cache_path

        logger.info(f"Generating icon: {spec.type}")

        # Generate based on type
        if spec.type == 'solid':
            img = self._generate_solid(spec)
        elif spec.type == 'text':
            img = self._generate_text(spec)
        elif spec.type == 'gradient':
            img = self._generate_gradient(spec)
        else:
            raise ValueError(f"Unsupported icon type: {spec.type}")

        # Save and return
        img.save(cache_path, 'PNG')
        logger.info(f"Saved icon to: {cache_path}")
        return cache_path

    def generate_from_dict(self, spec_dict: Dict[str, Any], force: bool = False, button_index: Optional[int] = None) -> Path:
        """Generate icon from a dictionary specification"""
        spec = IconSpec(spec_dict)
        errors = spec.validate()
        if errors:
            raise ValueError(f"Invalid icon spec: {', '.join(errors)}")
        return self.generate(spec, force=force, button_index=button_index)

    def _generate_solid(self, spec: IconSpec) -> Image.Image:
        """Generate solid color icon"""
        img = Image.new('RGB', spec.size, color=spec.color)
        return img

    def _generate_text(self, spec: IconSpec) -> Image.Image:
        """Generate text icon"""
        img = Image.new('RGB', spec.size, color=spec.color)
        draw = ImageDraw.Draw(img)

        # Try to use specified font, fall back to default
        font = None
        if spec.font:
            try:
                font = ImageFont.truetype(spec.font, spec.font_size)
            except (OSError, IOError):
                logger.warning(f"Font not found: {spec.font}, using default")

        if font is None:
            try:
                # Try common system fonts - Bold variant for better appearance
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", spec.font_size)
            except (OSError, IOError):
                try:
                    # Try regular if bold not available
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", spec.font_size)
                except (OSError, IOError):
                    # Fall back to default font
                    font = ImageFont.load_default()

        # Draw text centered — support multiline like ImageMagick's gravity center
        center_x = spec.size[0] // 2
        center_y = spec.size[1] // 2

        text_value = spec.text or ""
        # If multiline (contains \n), use multiline_text with center alignment
        if "\n" in text_value:
            # spacing ~15% of font size for balanced line separation
            spacing = max(1, int(spec.font_size * 0.15))
            draw.multiline_text(
                (center_x, center_y),
                text_value,
                fill=spec.text_color,
                font=font,
                anchor='mm',
                align='center',
                spacing=spacing,
            )
        else:
            draw.text((center_x, center_y), text_value, fill=spec.text_color, font=font, anchor='mm')

        return img

    def _generate_gradient(self, spec: IconSpec) -> Image.Image:
        """Generate gradient icon (simple vertical gradient)"""
        img = Image.new('RGB', spec.size)
        pixels = img.load()

        # Parse colors
        start_color = self._parse_color(spec.color)
        end_color = self._parse_color(spec.text_color)

        width, height = spec.size

        # Create vertical gradient
        for y in range(height):
            ratio = y / height
            r = int(start_color[0] * (1 - ratio) + end_color[0] * ratio)
            g = int(start_color[1] * (1 - ratio) + end_color[1] * ratio)
            b = int(start_color[2] * (1 - ratio) + end_color[2] * ratio)

            for x in range(width):
                pixels[x, y] = (r, g, b)

        return img

    @staticmethod
    def _parse_color(color: str) -> Tuple[int, int, int]:
        """Parse color string to RGB tuple"""
        if isinstance(color, str) and color.startswith('#'):
            color = color[1:]
            return tuple(int(color[i:i+2], 16) for i in (0, 2, 4))

        # Named colors - common ones
        color_map = {
            'red': (255, 0, 0),
            'green': (0, 255, 0),
            'blue': (0, 0, 255),
            'white': (255, 255, 255),
            'black': (0, 0, 0),
            'yellow': (255, 255, 0),
            'cyan': (0, 255, 255),
            'magenta': (255, 0, 255),
            'gray': (128, 128, 128),
            'grey': (128, 128, 128),
        }
        return color_map.get(color.lower(), (0, 0, 255))  # Default to blue
