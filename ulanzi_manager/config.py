"""Configuration file parser for Ulanzi Manager"""

import yaml
import re
import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


METRICS_FONT_FILES = {
    "sans": {
        "normal": "DejaVuSans.ttf", "bold": "DejaVuSans-Bold.ttf",
        "italic": "DejaVuSans-Oblique.ttf", "bold-italic": "DejaVuSans-BoldOblique.ttf",
    },
    "mono": {
        "normal": "DejaVuSansMono.ttf", "bold": "DejaVuSansMono-Bold.ttf",
        "italic": "DejaVuSansMono-Oblique.ttf", "bold-italic": "DejaVuSansMono-BoldOblique.ttf",
    },
    "serif": {
        "normal": "DejaVuSerif.ttf", "bold": "DejaVuSerif-Bold.ttf",
        "italic": "DejaVuSerif-Italic.ttf", "bold-italic": "DejaVuSerif-BoldItalic.ttf",
    },
    "ubuntu": {
        "normal": "Ubuntu-R.ttf", "bold": "Ubuntu-R.ttf",
        "italic": "Ubuntu-RI.ttf", "bold-italic": "Ubuntu-RI.ttf",
    },
    "ubuntu-mono": {
        "normal": "UbuntuMono-R.ttf", "bold": "UbuntuMono-R.ttf",
        "italic": "UbuntuMono-RI.ttf", "bold-italic": "UbuntuMono-RI.ttf",
    },
    "noto-sans": {
        "normal": "NotoSans-Regular.ttf", "bold": "NotoSans-Bold.ttf",
        "italic": "NotoSans-Italic.ttf", "bold-italic": "NotoSans-BoldItalic.ttf",
    },
    "noto-serif": {
        "normal": "NotoSerif-Regular.ttf", "bold": "NotoSerif-Bold.ttf",
        "italic": "NotoSerif-Italic.ttf", "bold-italic": "NotoSerif-BoldItalic.ttf",
    },
    "liberation-sans": {
        "normal": "LiberationSans-Regular.ttf", "bold": "LiberationSans-Bold.ttf",
        "italic": "LiberationSans-Italic.ttf", "bold-italic": "LiberationSans-BoldItalic.ttf",
    },
    "liberation-serif": {
        "normal": "LiberationSerif-Regular.ttf", "bold": "LiberationSerif-Bold.ttf",
        "italic": "LiberationSerif-Italic.ttf", "bold-italic": "LiberationSerif-BoldItalic.ttf",
    },
}


def parse_metrics_style(raw=None) -> Dict[str, Any]:
    """Validate the shared UI/daemon metrics display contract."""
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("Estilo das métricas inválido")
    style = {
        "layout": raw.get("layout", "columns"),
        "view": raw.get("view", "text"),
        "size": raw.get("size", 30),
        "font_family": raw.get("font_family", "sans"),
        "font_style": raw.get("font_style", "normal"),
        "colors": {},
    }
    if style["layout"] not in ("columns", "rows", "compact"):
        raise ValueError("Layout das métricas inválido")
    if style["view"] not in ("text", "htop", "history"):
        raise ValueError("Visualização das métricas inválida")
    size = style["size"]
    if isinstance(size, bool) or not isinstance(size, int) or not 18 <= size <= 48:
        raise ValueError("Tamanho das métricas deve estar entre 18 e 48 px")
    family, font_style = style["font_family"], style["font_style"]
    if not isinstance(family, str) or family not in METRICS_FONT_FILES:
        raise ValueError("Família da fonte das métricas inválida")
    if not isinstance(font_style, str) or font_style not in METRICS_FONT_FILES[family]:
        raise ValueError("Estilo da fonte das métricas inválido")
    # Migrate layouts saved before per-metric colors; return only the new schema.
    colors = raw.get("colors", {})
    if not isinstance(colors, dict):
        raise ValueError("Cores individuais das métricas inválidas")
    for metric, line_color in (("cpu", "#ff6b35"), ("mem", "#52c97a"), ("gpu", "#00ccff")):
        palette = colors.get(metric, {})
        if not isinstance(palette, dict):
            raise ValueError("Cores individuais das métricas inválidas")
        style["colors"][metric] = {}
        for key in ("color", "label_color", "line_color"):
            default = line_color if key == "line_color" else raw.get(key, "#ffffff")
            color = palette.get(key, default)
            if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                raise ValueError("Cor das métricas deve estar no formato #RRGGBB")
            style["colors"][metric][key] = color.lower()
    return style


@dataclass
class ButtonConfig:
    """Button configuration"""
    index: int
    image: Optional[str]
    label: str
    action_type: str  # 'command', 'obs', 'app', 'key'
    action_params: Dict[str, Any]
    action_enabled: bool = True
    display_mode: str = "buttons"
    state: int = 0
    icon_spec: Optional[Dict[str, Any]] = field(default=None)  # Icon generation spec
    background_tile: Optional[str] = None
    metrics_style: Dict[str, Any] = field(default_factory=parse_metrics_style)


@dataclass
class Config:
    """Main configuration"""
    brightness: int = 100
    label_style: Dict[str, Any] = None
    buttons: List[ButtonConfig] = None
    obs_host: str = "localhost"
    obs_port: int = 4444
    obs_password: Optional[str] = None

    def __post_init__(self):
        if self.label_style is None:
            self.label_style = {}
        if self.buttons is None:
            self.buttons = []


class ConfigParser:
    """Parse YAML configuration files"""

    @staticmethod
    def ensure_default(config_path: str) -> None:
        """Publish a self-contained first-run profile without replacing user data."""
        config_file = Path(config_path)
        if config_file.exists() or config_file.is_symlink():
            return

        config_file.parent.mkdir(parents=True, exist_ok=True)
        document = {
            'brightness': 100,
            'label_style': {
                'Align': 'bottom', 'Color': 0xFFFFFF, 'FontName': 'Roboto',
                'ShowTitle': True, 'Size': 10, 'Weight': 80,
            },
            'obs': {'host': 'localhost', 'port': 4444, 'password': None},
            'buttons': [None] * 13 + [{
                'display_mode': 'stats', 'action_enabled': False,
            }],
        }
        candidate = None
        try:
            with tempfile.NamedTemporaryFile(
                'w', encoding='utf-8', dir=config_file.parent,
                prefix='.config-default-', suffix='.yaml', delete=False,
            ) as handle:
                candidate = Path(handle.name)
                yaml.safe_dump(document, handle, sort_keys=False)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                # Link only after the complete file is durable. A competing
                # startup or user save wins without exposing a partial profile.
                os.link(candidate, config_file)
            except FileExistsError:
                pass
        finally:
            if candidate is not None:
                candidate.unlink()

    @staticmethod
    def load(config_path: str) -> Config:
        """Load configuration from YAML file"""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_file, 'r') as f:
            data = yaml.safe_load(f) or {}

        config = ConfigParser._parse_config(data, config_file.parent)

        # Generate icons from specs if needed
        ConfigParser._generate_icons(config, config_file.parent)

        return config

    @staticmethod
    def _parse_config(data: Dict, base_path: Path) -> Config:
        """Parse configuration dictionary"""
        config = Config()

        # Global settings
        if 'brightness' in data:
            config.brightness = int(data['brightness'])

        if 'label_style' in data:
            config.label_style = data['label_style']

        # OBS settings
        if 'obs' in data:
            obs_config = data['obs']
            config.obs_host = obs_config.get('host', 'localhost')
            config.obs_port = obs_config.get('port', 4444)
            config.obs_password = obs_config.get('password')

        # Parse buttons
        buttons = []
        if 'buttons' in data:
            for idx, button_data in enumerate(data['buttons']):
                if button_data is None:
                    continue

                button = ConfigParser._parse_button(idx, button_data, base_path)
                buttons.append(button)

        config.buttons = buttons
        logger.info(f"Loaded config with {len(buttons)} button(s)")
        return config

    @staticmethod
    def _parse_button(index: int, data: Dict, base_path: Path) -> ButtonConfig:
        """Parse button configuration"""
        # Resolve image path relative to config file
        image = data.get('image')
        if image:
            image_path = Path(image)
            if not image_path.is_absolute():
                image_path = base_path / image_path
            image = str(image_path)

        label = data.get('label', '')
        action_type = data.get('action', 'command')
        action_params = data.get('params', {})
        action_enabled = bool(data.get('action_enabled', index != 13))
        default_display_mode = 'stats'
        if index == 13 and image:
            default_display_mode = (
                'gif' if Path(image).suffix.lower() == '.gif' else 'background'
            )
        display_mode = str(data.get('display_mode', default_display_mode))
        state = data.get('state', 0)
        icon_spec = data.get('icon_spec')
        background_tile = data.get('background_tile')
        if background_tile:
            background_tile = str(base_path / background_tile)

        return ButtonConfig(
            index=index,
            image=image,
            label=label,
            action_type=action_type,
            action_params=action_params,
            action_enabled=action_enabled,
            display_mode=display_mode,
            background_tile=background_tile,
            metrics_style=parse_metrics_style(data.get('metrics_style')),
            state=state,
            icon_spec=icon_spec
        )

    @staticmethod
    def _generate_icons(config: Config, base_path: Path) -> None:
        """Generate icons from specs and update image paths"""
        try:
            from .icon_generator import IconGenerator
        except ImportError:
            logger.warning("Pillow not installed, skipping icon generation")
            return

        icon_dir = base_path / 'icons'
        icon_dir.mkdir(exist_ok=True)
        generator = IconGenerator(cache_dir=icon_dir)

        for button in config.buttons:
            if button.icon_spec:
                try:
                    logger.info(f"Generating icon for button {button.index}")
                    # Use specific filename and always regenerate
                    icon_path = generator.generate_from_dict(button.icon_spec, button_index=button.index, force=True)
                    button.image = str(icon_path)
                except Exception as e:
                    logger.error(f"Failed to generate icon for button {button.index}: {e}")
                    raise

    @staticmethod
    def validate(config: Config) -> List[str]:
        """Validate configuration and return list of errors"""
        errors = []

        if config.brightness < 0 or config.brightness > 100:
            errors.append("brightness must be between 0 and 100")

        if config.obs_port < 1 or config.obs_port > 65535:
            errors.append("obs.port must be between 1 and 65535")

        for button in config.buttons:
            stats_display = (
                button.index == 13 and button.display_mode == 'stats'
            )
            if (
                button.index == 13
                and button.display_mode not in ('gif', 'stats', 'background')
            ):
                errors.append(
                    "Button 13: display_mode must be 'gif', 'stats', or 'background'"
                )

            # Statistics are rendered by the host and do not require an image.
            if not stats_display and not button.image and not button.icon_spec:
                errors.append(
                    f"Button {button.index}: must specify either 'image' or 'icon_spec'"
                )

            if button.image and not Path(button.image).exists():
                errors.append(f"Button {button.index}: image file not found: {button.image}")

            # Validate icon_spec if present
            if button.icon_spec:
                try:
                    from .icon_generator import IconSpec
                    spec = IconSpec(button.icon_spec)
                    spec_errors = spec.validate()
                    for error in spec_errors:
                        errors.append(f"Button {button.index}: icon_spec error: {error}")
                except ImportError:
                    logger.warning("Pillow not installed, cannot validate icon_spec")
                except Exception as e:
                    errors.append(f"Button {button.index}: icon_spec error: {str(e)}")
            if not button.action_enabled:
                continue


            if button.action_type not in ['command', 'obs', 'app', 'key']:
                errors.append(f"Button {button.index}: invalid action type: {button.action_type}")

            if button.action_type == 'command' and 'cmd' not in button.action_params:
                errors.append(f"Button {button.index}: 'command' action requires 'cmd' parameter")

            if button.action_type == 'obs':
                action = button.action_params.get('action', 'toggle_scene')
                if action == 'toggle_scene' and ('scene1' not in button.action_params or 'scene2' not in button.action_params):
                    errors.append(f"Button {button.index}: 'toggle_scene' action requires 'scene1' and 'scene2' parameters")
                elif action == 'set_scene' and 'scene' not in button.action_params:
                    errors.append(f"Button {button.index}: 'set_scene' action requires 'scene' parameter")
                elif action == 'toggle_source' and ('scene' not in button.action_params or 'source' not in button.action_params):
                    errors.append(f"Button {button.index}: 'toggle_source' action requires 'scene' and 'source' parameters")

            if button.action_type == 'app' and 'name' not in button.action_params:
                errors.append(f"Button {button.index}: 'app' action requires 'name' parameter")

            if button.action_type == 'key' and 'keys' not in button.action_params:
                errors.append(f"Button {button.index}: 'key' action requires 'keys' parameter")

        return errors
