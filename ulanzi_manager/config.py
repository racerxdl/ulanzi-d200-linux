"""Configuration file parser for Ulanzi Manager"""

import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ButtonConfig:
    """Button configuration"""
    index: int
    image: Optional[str]
    label: str
    action_type: str  # 'command', 'obs', 'app', 'key'
    action_params: Dict[str, Any]
    state: int = 0
    icon_spec: Optional[Dict[str, Any]] = field(default=None)  # Icon generation spec


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
        state = data.get('state', 0)
        icon_spec = data.get('icon_spec')

        return ButtonConfig(
            index=index,
            image=image,
            label=label,
            action_type=action_type,
            action_params=action_params,
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
            # Image is required either from file or icon_spec
            if not button.image and not button.icon_spec:
                errors.append(f"Button {button.index}: must specify either 'image' or 'icon_spec'")

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
