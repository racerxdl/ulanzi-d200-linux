"""Extra D200X controls: three knobs and two physical buttons.

The web UI rewrites config.yaml from scratch on every save, so these controls
live in a separate controls.yaml next to it. The file is re-read whenever its
modification time changes, so edits apply without restarting the daemon.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

# Device index -> (section, name), as reported by the D200X firmware.
CONTROL_INDEX = {
    15: ("buttons", "first"),
    16: ("buttons", "second"),
    17: ("knobs", "left"),
    18: ("knobs", "middle"),
    19: ("knobs", "right"),
}
KNOB_EVENTS = ("clockwise", "counterclockwise", "press")
ACTION_TYPES = ("command", "app", "key", "obs")
REQUIRED_PARAM = {"command": "cmd", "app": "name", "key": "keys"}

DEFAULT_CONTROLS = """\
# Controles extras do Ulanzi D200X: 3 knobs e 2 botões físicos (sem tela).
# Este arquivo é separado do config.yaml porque a interface web reescreve
# aquele arquivo ao salvar. Edições aqui valem na hora, sem reiniciar nada.
#
# Cada ação usa os mesmos tipos das teclas:
#   action: command  -> params: {cmd: "comando de shell"}
#   action: app      -> params: {name: "firefox"}
#   action: key      -> params: {keys: "ctrl+alt+t"}   (via ydotool no Wayland)
#   action: obs      -> params: {action: toggle_recording}
# Para desativar um controle, apague a linha ou deixe-a comentada.

knobs:
  # Knob da esquerda: volume do som.
  left:
    clockwise:
      action: command
      params: {cmd: "wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ 5%+"}
    counterclockwise:
      action: command
      params: {cmd: "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"}
    press:
      action: command
      params: {cmd: "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"}

  # Knob do meio: volume do microfone; apertar liga/desliga o mudo.
  middle:
    clockwise:
      action: command
      params: {cmd: "wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SOURCE@ 5%+"}
    counterclockwise:
      action: command
      params: {cmd: "wpctl set-volume @DEFAULT_AUDIO_SOURCE@ 5%-"}
    press:
      action: command
      params: {cmd: "wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"}

  # Knob da direita: livre. Exemplo:
  right:
    # clockwise:
    #   action: command
    #   params: {cmd: "notify-send 'Knob direito' 'girou para a direita'"}
    # counterclockwise: ...
    # press: ...

buttons:
  # 1º e 2º botões físicos (sem tela). Exemplo:
  # first:
  #   action: app
  #   params: {name: gnome-terminal}
  # second:
  #   action: command
  #   params: {cmd: "gnome-screenshot -i"}
"""


def ensure_default(path: Path) -> None:
    """Create the commented default file without replacing user edits."""
    if path.exists() or path.is_symlink():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "x", encoding="utf-8") as handle:
            handle.write(DEFAULT_CONTROLS)
        logger.info("Created default extra controls at %s", path)
    except FileExistsError:
        pass


def _validate_action(where: str, entry: Any) -> Optional[Tuple[str, Dict[str, Any]]]:
    if not isinstance(entry, dict):
        logger.error("%s: expected 'action' and 'params'", where)
        return None
    action = entry.get("action")
    params = entry.get("params") or {}
    if action not in ACTION_TYPES:
        logger.error("%s: invalid action %r", where, action)
        return None
    if not isinstance(params, dict):
        logger.error("%s: 'params' must be a mapping", where)
        return None
    required = REQUIRED_PARAM.get(action)
    if required and not params.get(required):
        logger.error("%s: action %r requires params.%s", where, action, required)
        return None
    return action, params


class ExtraControls:
    """Resolve knob and physical-button events to configured actions."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._mtime: Optional[float] = None
        self._actions: Dict[Tuple[int, str], Tuple[str, Dict[str, Any]]] = {}

    def _reload_if_changed(self) -> None:
        try:
            mtime = self.path.stat().st_mtime
        except FileNotFoundError:
            self._mtime, self._actions = None, {}
            return
        if mtime == self._mtime:
            return
        self._mtime = mtime
        try:
            data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as error:
            logger.error("Could not read %s: %s", self.path, error)
            self._actions = {}
            return
        if not isinstance(data, dict):
            logger.error("%s: top level must be a mapping", self.path)
            self._actions = {}
            return

        actions = {}
        for index, (section, name) in CONTROL_INDEX.items():
            entry = (data.get(section) or {}).get(name)
            if entry is None:
                continue
            if section == "buttons":
                resolved = _validate_action(f"{section}.{name}", entry)
                if resolved:
                    actions[(index, "press")] = resolved
                continue
            if not isinstance(entry, dict):
                logger.error("%s.%s: expected clockwise/counterclockwise/press", section, name)
                continue
            for event in KNOB_EVENTS:
                if entry.get(event) is None:
                    continue
                resolved = _validate_action(f"{section}.{name}.{event}", entry[event])
                if resolved:
                    actions[(index, event)] = resolved
        self._actions = actions
        logger.info("Loaded %d extra control action(s) from %s", len(actions), self.path)

    def resolve(self, index: int, event: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Return (action_type, params) for a control event, if configured."""
        self._reload_if_changed()
        return self._actions.get((index, event))
