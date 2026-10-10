"""Action handlers for button presses"""

import subprocess
import logging
from pathlib import Path
from typing import Dict, Any
from abc import ABC, abstractmethod

from ulanzi_manager.native import native_python

logger = logging.getLogger(__name__)


def _launch_independent(command, *, desktop=False, env=None):
    """Keep launched applications outside the daemon's restart/stop cgroup."""
    return subprocess.Popen(
        [
            'systemd-run', '--user', '--scope', '--collect', '--quiet',
            '--expand-environment=no', '--', *command,
        ],
        stdout=None if desktop else subprocess.DEVNULL,
        stderr=None,
        env=env,
    )


class ActionHandler(ABC):
    """Base class for action handlers"""

    @abstractmethod
    def execute(self, params: Dict[str, Any]):
        """Execute the action"""
        pass


class CommandAction(ActionHandler):
    """Execute shell commands"""

    def execute(self, params: Dict[str, Any]):
        """Execute shell command"""
        cmd = params.get('cmd')
        if not cmd:
            logger.error("Command action requires 'cmd' parameter")
            return

        try:
            _launch_independent(['/bin/sh', '-c', cmd])
            logger.info(f"Executed command: {cmd}")
        except Exception as e:
            logger.error(f"Failed to execute command: {e}")


class AppAction(ActionHandler):
    """Launch applications"""

    def execute(self, params: Dict[str, Any]):
        """Launch application"""
        app_name = params.get('name')
        if not app_name:
            logger.error("App action requires 'name' parameter")
            return

        try:
            app_path = Path(app_name)
            desktop = app_path.is_absolute() and app_path.suffix == '.desktop'
            environment = None
            if desktop:
                python, environment = native_python()
                command = [*python, str(Path(__file__).with_name('desktop_launcher.py')), app_name]
            else:
                command = [app_name]
            _launch_independent(command, desktop=desktop, env=environment)
            logger.info(f"Requested application launch: {app_name}")
        except Exception as e:
            logger.error(f"Failed to launch application: {e}")


class KeyAction(ActionHandler):
    """Simulate keyboard input"""

    def execute(self, params: Dict[str, Any]):
        """Simulate keyboard input"""
        keys = params.get('keys')
        if not keys:
            logger.error("Key action requires 'keys' parameter")
            return

        try:
            # Try xdotool first (most common on Linux)
            subprocess.run(['xdotool', 'key', keys], check=True, capture_output=True)
            logger.info(f"Sent keys: {keys}")
        except FileNotFoundError:
            logger.error("xdotool not found. Install it with: sudo apt install xdotool")
        except Exception as e:
            logger.error(f"Failed to send keys: {e}")


class OBSAction(ActionHandler):
    """Control OBS Studio via WebSocket"""

    def __init__(self, obs_client=None):
        """Initialize OBS action handler"""
        self.obs_client = obs_client

    def execute(self, params: Dict[str, Any]):
        """Execute OBS action"""
        if not self.obs_client:
            logger.error("OBS client not connected")
            return

        action = params.get('action', 'toggle_scene')

        try:
            if action == 'toggle_scene':
                self._toggle_scene(params)
            elif action == 'set_scene':
                self._set_scene(params)
            elif action == 'toggle_source':
                self._toggle_source(params)
            elif action == 'toggle_recording':
                self._toggle_recording(params)
            elif action == 'toggle_streaming':
                self._toggle_streaming(params)
            else:
                logger.error(f"Unknown OBS action: {action}")
        except Exception as e:
            logger.error(f"OBS action failed: {e}")

    def _toggle_scene(self, params: Dict[str, Any]):
        """Toggle between two scenes"""
        scene1 = params.get('scene1')
        scene2 = params.get('scene2')

        if not scene1 or not scene2:
            logger.error("toggle_scene requires 'scene1' and 'scene2' parameters")
            return

        try:
            current_scene = self.obs_client.get_current_program_scene()
            current_name = current_scene.current_program_scene_name

            target_scene = scene2 if current_name == scene1 else scene1
            self.obs_client.set_current_program_scene(target_scene)
            logger.info(f"Switched to scene: {target_scene}")
        except Exception as e:
            logger.error(f"Failed to toggle scene: {e}")

    def _set_scene(self, params: Dict[str, Any]):
        """Set active scene"""
        scene = params.get('scene')
        if not scene:
            logger.error("set_scene requires 'scene' parameter")
            return

        try:
            self.obs_client.set_current_program_scene(scene)
            logger.info(f"Set scene to: {scene}")
        except Exception as e:
            logger.error(f"Failed to set scene: {e}")

    def _toggle_source(self, params: Dict[str, Any]):
        """Toggle source visibility"""
        scene = params.get('scene')
        source = params.get('source')

        if not scene or not source:
            logger.error("toggle_source requires 'scene' and 'source' parameters")
            return

        try:
            # Get current visibility state
            item = self.obs_client.get_scene_item_id(scene, source)
            item_id = item.scene_item_id

            state = self.obs_client.get_scene_item_enabled(scene, item_id)
            enabled = state.scene_item_enabled

            # Toggle visibility
            self.obs_client.set_scene_item_enabled(scene, item_id, not enabled)
            logger.info(f"Toggled source '{source}' in scene '{scene}'")
        except Exception as e:
            logger.error(f"Failed to toggle source: {e}")

    def _toggle_recording(self, params: Dict[str, Any]):
        """Toggle recording"""
        try:
            status = self.obs_client.get_record_status()
            is_recording = status.output_active

            if is_recording:
                self.obs_client.stop_record()
                logger.info("Stopped recording")
            else:
                self.obs_client.start_record()
                logger.info("Started recording")
        except Exception as e:
            logger.error(f"Failed to toggle recording: {e}")

    def _toggle_streaming(self, params: Dict[str, Any]):
        """Toggle streaming"""
        try:
            status = self.obs_client.get_stream_status()
            is_streaming = status.output_active

            if is_streaming:
                self.obs_client.stop_stream()
                logger.info("Stopped streaming")
            else:
                self.obs_client.start_stream()
                logger.info("Started streaming")
        except Exception as e:
            logger.error(f"Failed to toggle streaming: {e}")


class ActionExecutor:
    """Execute button actions"""

    def __init__(self, obs_client=None):
        """Initialize action executor"""
        self.handlers = {
            'command': CommandAction(),
            'app': AppAction(),
            'key': KeyAction(),
            'obs': OBSAction(obs_client),
        }

    def execute(self, action_type: str, params: Dict[str, Any]):
        """Execute action by type"""
        handler = self.handlers.get(action_type)
        if not handler:
            logger.error(f"Unknown action type: {action_type}")
            return

        try:
            handler.execute(params)
        except Exception as e:
            logger.error(f"Action execution failed: {e}")
