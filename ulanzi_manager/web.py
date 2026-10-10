"""Local web interface for configuring an Ulanzi D200."""

import argparse
import base64
import binascii
import configparser
import gettext
import json
import hashlib
import io
import logging
import os
import re
import shutil
import socket
import subprocess
import tempfile
import unicodedata
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import unquote, urlparse

import yaml
from PIL import Image, ImageOps, ImageSequence, UnidentifiedImageError

from ulanzi_manager.config import (
    ConfigParser, parse_metrics_style, parse_content_margin, METRICS_FONT_FILES,
)
from ulanzi_manager.application_icons import import_application_icon

logger = logging.getLogger(__name__)

BUTTON_COUNT = 14
WIDE_DISPLAY_INDEX = 13
MAX_IMAGE_BYTES = 8 * 1024 * 1024
# Base64 expands image data by 4/3; reserve bounded space for JSON metadata.
MAX_JSON_BYTES = 4 * ((MAX_IMAGE_BYTES + 2) // 3) + 64 * 1024
MAX_IMAGE_DIMENSION = 4096
MAX_STATIC_IMAGE_PIXELS = 40_000_000
MAX_GIF_FRAMES = 300
ALLOWED_ACTIONS = {"command", "app", "key", "obs"}
ALLOWED_OBS_ACTIONS = {
    "toggle_scene",
    "set_scene",
    "toggle_source",
    "toggle_recording",
    "toggle_streaming",
}
ICON_NAME_RE = re.compile(r"[^a-zA-Z0-9_.-]+")
GENERATED_ICON_RE = re.compile(r"--scale-\d+\.png$")
MOSAIC_TILE_RE = re.compile(r"^mosaic-[0-9a-f]{10}-(?:\d{2}|wide)\.png$")
MOSAIC_SOURCE_RE = re.compile(r"^mosaic-source-([0-9a-f]{64})\.(?:png|jpeg|webp)$")
COMPOSITE_ICON_RE = re.compile(r"--background-[0-9a-f]{10}\.png$")
LAYOUT_ID_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_LAYOUT_NAME_LENGTH = 60
STATIC_DIR = Path(__file__).with_name("static")
APPLICATION_LOCALE_DIRS = ("/usr/share/locale", "/usr/share/locale-langpack")


def _application_dirs() -> list[Path]:
    """Desktop entry roots in override order, without resolving export symlinks."""
    data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    if not data_home.is_absolute():
        data_home = Path.home() / ".local/share"
    data_dirs = [
        Path(value)
        for value in (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")
        if value and Path(value).is_absolute()
    ]
    directories = [
        data_home / "applications",
        data_home / "flatpak/exports/share/applications",
        *(directory / "applications" for directory in data_dirs),
        Path("/var/lib/flatpak/exports/share/applications"),
        Path("/var/lib/snapd/desktop/applications"),
    ]
    return list(dict.fromkeys(directories))


class ValidationError(ValueError):
    """User-facing configuration validation error."""


class WebApp:
    def __init__(self, config_path: Path):
        self.config_path = config_path.expanduser().resolve()
        ConfigParser.ensure_default(str(self.config_path))
        self.config_dir = self.config_path.parent
        self.icons_dir = self.config_dir / "icons"
        self.layouts_dir = self.config_dir / "layouts"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.icons_dir.mkdir(parents=True, exist_ok=True)
        self.layouts_dir.mkdir(parents=True, exist_ok=True)

    def get_config(self) -> Dict[str, Any]:
        with self.config_path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
        return self._present_config(raw)

    def _present_config(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        raw_buttons = raw.get("buttons") or []
        buttons = []
        for index in range(BUTTON_COUNT):
            item = raw_buttons[index] if index < len(raw_buttons) else None
            if not item:
                buttons.append({
                    "index": index,
                    "enabled": False,
                    "label": "",
                    "image": "",
                    "icon_source": "",
                    "icon_scale": 100,
                    "content_margin": 0,
                    "background_tile": "",
                    "action": "command",
                    "params": {"cmd": ""},
                    "action_enabled": index != WIDE_DISPLAY_INDEX,
                    "display_mode": (
                        "stats" if index == WIDE_DISPLAY_INDEX else "buttons"
                    ),
                    "metrics_style": parse_metrics_style(),
                })
                continue

            image = item.get("image") or ""
            icon_source = item.get("icon_source") or image
            try:
                icon_scale = max(25, min(100, int(item.get("icon_scale", 100))))
            except (TypeError, ValueError):
                icon_scale = 100
            default_display_mode = "stats"
            if index == WIDE_DISPLAY_INDEX and image:
                default_display_mode = (
                    "gif" if Path(image).suffix.lower() == ".gif" else "background"
                )
            buttons.append({
                "index": index,
                "enabled": True,
                "label": str(item.get("label") or ""),
                "image": Path(image).name if image else "",
                "icon_source": Path(icon_source).name if icon_source else "",
                "icon_scale": icon_scale,
                "content_margin": parse_content_margin(item.get("content_margin", 0)),
                "background_tile": Path(
                    item.get("background_tile") or ""
                ).name,
                "action": str(item.get("action") or "command"),
                "params": item.get("params") or {},
                "action_enabled": bool(
                    item.get("action_enabled", index != WIDE_DISPLAY_INDEX)
                ),
                "display_mode": str(item.get(
                    "display_mode",
                    default_display_mode,
                )),
                "metrics_style": parse_metrics_style(item.get("metrics_style")),
            })

        label_style = raw.get("label_style") or {}
        obs = raw.get("obs") or {}
        return {
            "brightness": int(raw.get("brightness", 100)),
            "label_style": {
                "Align": label_style.get("Align", "bottom"),
                "Color": label_style.get("Color", 0xFFFFFF),
                "FontName": label_style.get("FontName", "Roboto"),
                "ShowTitle": bool(label_style.get("ShowTitle", True)),
                "Size": int(label_style.get("Size", 10)),
                "Weight": int(label_style.get("Weight", 80)),
            },
            "obs": {
                "host": str(obs.get("host", "localhost")),
                "port": int(obs.get("port", 4444)),
                "password": obs.get("password"),
            },
            "buttons": buttons,
            "background": (
                self._background_settings(raw["background"])
                if raw.get("background") is not None else self._recover_mosaic_source(buttons)
            ),
            "icons": self.list_icons(),
        }

    def _available_icons(self) -> List[str]:
        return [
            path.name
            for pattern in ("*.png", "*.gif")
            for path in self.icons_dir.glob(pattern)
            if path.is_file()
        ]

    def list_icons(self) -> List[str]:
        return sorted(
            name
            for name in self._available_icons()
            if not GENERATED_ICON_RE.search(name)
            and not MOSAIC_TILE_RE.fullmatch(name)
            and not MOSAIC_SOURCE_RE.fullmatch(name)
            and not COMPOSITE_ICON_RE.search(name)
        )

    def list_applications(self) -> List[Dict[str, str]]:
        """Read visible desktop applications without changing user configuration."""
        locale = next(
            (os.environ[key] for key in ("LC_ALL", "LC_MESSAGES", "LANG") if os.environ.get(key)),
            "",
        )
        locale_base, _, modifier = locale.partition("@")
        locale_base = locale_base.split(".", 1)[0]
        language, _, territory = locale_base.partition("_")
        locales = []
        if locale_base and locale_base not in {"C", "POSIX"}:
            if territory and modifier:
                locales.append(f"{language}_{territory}@{modifier}")
            if territory:
                locales.append(f"{language}_{territory}")
            if modifier:
                locales.append(f"{language}@{modifier}")
            locales.append(language)
        desktops = {
            desktop for desktop in os.environ.get("XDG_CURRENT_DESKTOP", "").split(":")
            if desktop
        }
        applications = []
        seen = set()
        for directory in _application_dirs():
            try:
                paths = sorted(directory.rglob("*.desktop"))
            except OSError as exc:
                logger.warning("Ignoring application directory %s: %s", directory, exc)
                continue
            for path in paths:
                desktop_id = path.relative_to(directory).as_posix().replace("/", "-")
                if desktop_id in seen:
                    continue
                entry_file = configparser.ConfigParser(
                    interpolation=None, delimiters=("=",), comment_prefixes=("#",),
                    inline_comment_prefixes=None, strict=True,
                )
                entry_file.optionxform = str
                try:
                    with path.open("r", encoding="utf-8") as handle:
                        entry_file.read_file(handle)
                    if not entry_file.has_section("Desktop Entry"):
                        continue
                    entry = entry_file["Desktop Entry"]
                    # Overrides apply even when the higher-priority entry hides the app.
                    seen.add(desktop_id)
                    if entry.getboolean("Hidden", fallback=False) or entry.getboolean("NoDisplay", fallback=False):
                        continue
                    if entry.get("Type") != "Application":
                        continue
                    if not entry.get("Exec", "").strip() and not entry.getboolean("DBusActivatable", fallback=False):
                        continue
                    try_exec = entry.get("TryExec", "").strip()
                    if try_exec and shutil.which(try_exec) is None:
                        continue
                    if desktops:
                        only_show = {value for value in entry.get("OnlyShowIn", "").split(";") if value}
                        not_show = {value for value in entry.get("NotShowIn", "").split(";") if value}
                        if only_show and not desktops.intersection(only_show):
                            continue
                        if desktops.intersection(not_show):
                            continue
                    name = next(
                        (entry[f"Name[{value}]"] for value in locales if entry.get(f"Name[{value}]", "").strip()),
                        None,
                    )
                    if name is None:
                        name = entry.get("Name", "")
                        domain = (
                            entry.get("X-Ubuntu-Gettext-Domain")
                            or entry.get("X-GNOME-Gettext-Domain")
                        )
                        if name and domain and locales:
                            for locale_dir in APPLICATION_LOCALE_DIRS:
                                translated = gettext.translation(
                                    domain, localedir=locale_dir,
                                    languages=locales, fallback=True,
                                ).gettext(name)
                                if translated != name:
                                    name = translated
                                    break
                    # Desktop strings use these escapes, rather than Python/JSON escapes.
                    escapes = {"s": " ", "n": "\n", "t": "\t", "r": "\r", "\\": "\\"}
                    name = re.sub(r"\\([sntr\\])", lambda match: escapes[match.group(1)], name).strip()
                    if not name:
                        continue
                    applications.append({
                        "id": desktop_id,
                        "name": name,
                        "desktop_file": str(path.absolute()),
                    })
                except (OSError, UnicodeError, configparser.Error, ValueError) as exc:
                    logger.warning("Ignoring invalid application entry %s: %s", path, exc)
        return sorted(applications, key=lambda app: (app["name"].casefold(), app["id"]))

    def prepare_application_icon(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        application_id = payload.get("id")
        application = next(
            (entry for entry in self.list_applications() if entry["id"] == application_id),
            None,
        )
        if application is None:
            raise ValidationError("Aplicativo não encontrado na lista de aplicativos instalados")
        return {
            "filename": import_application_icon(application["desktop_file"], self.icons_dir),
        }

    @staticmethod
    def _layout_name(payload: Dict[str, Any]) -> str:
        name = unicodedata.normalize(
            "NFC",
            str(payload.get("name") or "").strip()
        )
        if not name:
            raise ValidationError("Informe um nome para o layout")
        if len(name) > MAX_LAYOUT_NAME_LENGTH:
            raise ValidationError(
                f"O nome do layout deve ter no máximo {MAX_LAYOUT_NAME_LENGTH} caracteres"
            )
        if any(ord(character) < 32 for character in name):
            raise ValidationError("O nome do layout contém caracteres inválidos")
        return name

    @staticmethod
    def _layout_id(name: str) -> str:
        return hashlib.sha256(name.casefold().encode("utf-8")).hexdigest()

    def _layout_path(self, layout_id: str) -> Path:
        if not LAYOUT_ID_RE.fullmatch(layout_id):
            raise ValidationError("Identificador de layout inválido")
        return self.layouts_dir / f"{layout_id}.yaml"

    def _read_layout(self, layout_id: str) -> Dict[str, Any]:
        path = self._layout_path(layout_id)
        if not path.is_file():
            raise ValidationError("Layout não encontrado")
        try:
            with path.open("r", encoding="utf-8") as handle:
                saved = yaml.safe_load(handle)
        except (OSError, yaml.YAMLError) as exc:
            raise ValidationError("Não foi possível ler o layout") from exc
        if (
            not isinstance(saved, dict)
            or not isinstance(saved.get("name"), str)
            or not isinstance(saved.get("config"), dict)
        ):
            raise ValidationError("Layout salvo está corrompido")
        return saved

    def list_layouts(self) -> List[Dict[str, str]]:
        layouts = []
        for path in self.layouts_dir.glob("*.yaml"):
            if not LAYOUT_ID_RE.fullmatch(path.stem):
                continue
            try:
                saved = self._read_layout(path.stem)
            except ValidationError as exc:
                logger.warning("Ignoring invalid saved layout %s: %s", path, exc)
                continue
            layouts.append({"id": path.stem, "name": saved["name"]})
        return sorted(layouts, key=lambda layout: layout["name"].casefold())

    def save_layout(self, payload: Dict[str, Any]) -> Dict[str, str]:
        name = self._layout_name(payload)
        config = payload.get("config")
        if not isinstance(config, dict):
            raise ValidationError("Configuração do layout inválida")
        document = self._build_document(config)
        layout_id = self._layout_id(name)
        destination = self._layout_path(layout_id)
        candidate = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.layouts_dir,
                prefix=".layout-",
                suffix=".yaml",
                delete=False,
            ) as handle:
                yaml.safe_dump(
                    {"name": name, "config": document},
                    handle,
                    sort_keys=False,
                    allow_unicode=True,
                )
                candidate = Path(handle.name)
            os.replace(candidate, destination)
            candidate = None
        finally:
            if candidate and candidate.exists():
                candidate.unlink()
        logger.info("Layout saved to %s", destination)
        return {"id": layout_id, "name": name}

    def load_layout(self, layout_id: str) -> Dict[str, Any]:
        saved = self._read_layout(layout_id)
        return {
            "layout": {"id": layout_id, "name": saved["name"]},
            "config": self._present_config(saved["config"]),
        }

    def delete_layout(self, layout_id: str) -> Dict[str, bool]:
        path = self._layout_path(layout_id)
        if not path.is_file():
            raise ValidationError("Layout não encontrado")
        path.unlink()
        logger.info("Layout deleted: %s", path)
        return {"deleted": True}

    def render_scaled_icon(self, source_name: str, scale: int, content_margin: int = 0) -> str:
        if scale == 100 and content_margin == 0:
            return source_name

        source = self.icons_dir / source_name
        filename = "{}--scale-{}.png".format(source.stem, scale)
        if content_margin:
            filename = "{}--scale-{}-margin-{}.png".format(source.stem, scale, content_margin)
        destination = self.icons_dir / filename
        with Image.open(source) as image:
            target = max(1, round((196 - 2 * content_margin) * scale / 100))
            logo = ImageOps.contain(
                image.convert("RGBA"),
                (target, target),
                Image.Resampling.LANCZOS,
            )
            rendered = Image.new("RGBA", (196, 196), (0, 0, 0, 0))
            position = ((196 - logo.width) // 2, (196 - logo.height) // 2)
            rendered.alpha_composite(logo, position)
            with tempfile.NamedTemporaryFile(
                "wb", dir=self.icons_dir, suffix=".png", delete=False
            ) as output:
                output_path = Path(output.name)
            try:
                rendered.save(output_path, format="PNG", optimize=True)
                os.replace(output_path, destination)
            finally:
                if output_path.exists():
                    output_path.unlink()
        return filename

    def render_composite_icon(
        self,
        background_name: str,
        source_name: str,
        scale: int,
        content_margin: int = 0,
    ) -> str:
        background_bytes = (self.icons_dir / background_name).read_bytes()
        source_bytes = (self.icons_dir / source_name).read_bytes()
        signature = (
            hashlib.sha256(background_bytes).digest()
            + hashlib.sha256(source_bytes).digest()
            + str(scale).encode("ascii")
        )
        if content_margin:
            signature += f":margin:{content_margin}".encode("ascii")
        digest = hashlib.sha256(signature).hexdigest()[:10]
        filename = f"{Path(source_name).stem}--background-{digest}.png"
        destination = self.icons_dir / filename
        if destination.is_file():
            return filename

        with (
            Image.open(io.BytesIO(background_bytes)) as background_image,
            Image.open(io.BytesIO(source_bytes)) as source_image,
        ):
            background = ImageOps.fit(
                background_image.convert("RGBA"),
                (196, 196),
                Image.Resampling.LANCZOS,
            )
            target = max(1, round((196 - 2 * content_margin) * scale / 100))
            logo = ImageOps.contain(
                source_image.convert("RGBA"),
                (target, target),
                Image.Resampling.LANCZOS,
            )
            position = (
                (196 - logo.width) // 2,
                (196 - logo.height) // 2,
            )
            background.alpha_composite(logo, position)
            with tempfile.NamedTemporaryFile(
                "wb", dir=self.icons_dir, suffix=".png", delete=False
            ) as output:
                output_path = Path(output.name)
            try:
                background.save(output_path, format="PNG", optimize=True)
                os.replace(output_path, destination)
            finally:
                if output_path.exists():
                    output_path.unlink()
        return filename

    def save_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        document = self._build_document(payload)
        candidate = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.config_dir,
                prefix=".config-",
                suffix=".yaml",
                delete=False,
            ) as handle:
                yaml.safe_dump(document, handle, sort_keys=False, allow_unicode=True)
                candidate = Path(handle.name)

            parsed = ConfigParser.load(str(candidate))
            errors = ConfigParser.validate(parsed)
            if errors:
                raise ValidationError("; ".join(errors))

            if self.config_path.exists():
                shutil.copy2(self.config_path, self.config_path.with_suffix(".yaml.backup"))
            os.replace(candidate, self.config_path)
            candidate = None
            logger.info("Configuration saved to %s", self.config_path)
            return self.get_config()
        finally:
            if candidate and candidate.exists():
                candidate.unlink()

    def _build_document(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        background = payload.get("background")
        if background is not None:
            background = self._background_settings(background)
            self._mosaic_source_bytes(background["source"])
        try:
            brightness = int(payload.get("brightness", 100))
        except (TypeError, ValueError) as exc:
            raise ValidationError("Brilho inválido") from exc
        if not 0 <= brightness <= 100:
            raise ValidationError("O brilho deve estar entre 0 e 100")

        label_input = payload.get("label_style") or {}
        try:
            font_size = int(label_input.get("Size", 10))
            font_weight = int(label_input.get("Weight", 80))
            color = int(label_input.get("Color", 0xFFFFFF))
        except (TypeError, ValueError) as exc:
            raise ValidationError("Estilo dos rótulos inválido") from exc

        obs_input = payload.get("obs") or {}
        try:
            obs_port = int(obs_input.get("port", 4444))
        except (TypeError, ValueError) as exc:
            raise ValidationError("Porta do OBS inválida") from exc
        if not 1 <= obs_port <= 65535:
            raise ValidationError("A porta do OBS deve estar entre 1 e 65535")

        input_buttons = payload.get("buttons")
        if not isinstance(input_buttons, list) or len(input_buttons) != BUTTON_COUNT:
            raise ValidationError("A configuração deve conter exatamente 14 botões")

        buttons = []
        available_icons = set(self._available_icons())
        for index, button in enumerate(input_buttons):
            if not isinstance(button, dict) or not button.get("enabled"):
                buttons.append(None)
                continue

            try:
                content_margin = parse_content_margin(button.get("content_margin", 0))
            except ValueError as exc:
                raise ValidationError("Botão {}: {}".format(index + 1, exc)) from exc

            source_name = Path(
                str(button.get("icon_source") or button.get("image") or "")
            ).name
            display_mode = "buttons"
            if index == WIDE_DISPLAY_INDEX:
                display_mode = str(button.get("display_mode") or "gif")
                if display_mode not in {"gif", "stats", "background"}:
                    raise ValidationError("Botão 14: modo de exibição inválido")
                if not source_name or source_name not in available_icons:
                    if display_mode == "gif":
                        raise ValidationError("Botão 14: selecione um GIF animado")
                    if display_mode == "background":
                        raise ValidationError("Botão 14: selecione uma imagem de fundo")
                if source_name and source_name not in available_icons:
                    raise ValidationError("Botão 14: imagem inválida")
                suffix = Path(source_name).suffix.lower() if source_name else ""
                if display_mode == "gif" and suffix != ".gif":
                    raise ValidationError("Botão 14: selecione um GIF animado")
                if display_mode == "background" and suffix != ".png":
                    raise ValidationError("Botão 14: selecione uma imagem PNG")
                if display_mode == "stats" and suffix not in {"", ".gif", ".png"}:
                    raise ValidationError("Botão 14: imagem inválida")
                icon_scale = 100
                image_name = source_name
            else:
                if not source_name or source_name not in available_icons:
                    raise ValidationError(
                        "Botão {}: selecione um ícone válido".format(index + 1)
                    )
                if Path(source_name).suffix.lower() != ".png":
                    raise ValidationError(
                        "Botão {}: selecione uma imagem PNG".format(index + 1)
                    )
                try:
                    icon_scale = int(button.get("icon_scale", 100))
                except (TypeError, ValueError) as exc:
                    raise ValidationError(
                        "Botão {}: tamanho do logo inválido".format(index + 1)
                    ) from exc
                if not 25 <= icon_scale <= 100:
                    raise ValidationError(
                        "Botão {}: o tamanho do logo deve estar entre 25% e 100%".format(index + 1)
                    )
                background_name = Path(
                    str(button.get("background_tile") or "")
                ).name
                if background_name:
                    if (
                        background_name not in available_icons
                        or Path(background_name).suffix.lower() != ".png"
                    ):
                        raise ValidationError(
                            "Botão {}: fundo do mosaico inválido".format(index + 1)
                        )
                    image_name = self.render_composite_icon(
                        background_name,
                        source_name,
                        icon_scale,
                        content_margin,
                    )
                else:
                    image_name = self.render_scaled_icon(source_name, icon_scale, content_margin)

            action_enabled = bool(
                button.get("action_enabled", index != WIDE_DISPLAY_INDEX)
            )
            if index == WIDE_DISPLAY_INDEX and not action_enabled:
                action = "command"
                params = {"cmd": ""}
                label = ""
            else:
                action = str(button.get("action") or "")
                if action not in ALLOWED_ACTIONS:
                    raise ValidationError("Botão {}: ação inválida".format(index + 1))
                params = self._validate_params(index, action, button.get("params") or {})
                label = str(button.get("label") or "").strip()
            saved_button = {
                "image": (
                    "./icons/{}".format(image_name) if image_name else ""
                ),
                "icon_source": (
                    "./icons/{}".format(source_name) if source_name else ""
                ),
                "icon_scale": icon_scale,
                "content_margin": content_margin,
                "label": label,
                "action": action,
                "params": params,
            }
            if index != WIDE_DISPLAY_INDEX and background_name:
                saved_button["background_tile"] = (
                    "./icons/{}".format(background_name)
                )
            if index == WIDE_DISPLAY_INDEX:
                saved_button["action_enabled"] = action_enabled
                saved_button["display_mode"] = display_mode
                try:
                    saved_button["metrics_style"] = parse_metrics_style(button.get("metrics_style"))
                    saved_button["metrics_style"]["content_margin"] = content_margin
                except ValueError as exc:
                    raise ValidationError("Botão 14: {}".format(exc)) from exc
                wide_background = Path(str(button.get("background_tile") or "")).name
                if wide_background:
                    if wide_background not in available_icons or not wide_background.lower().endswith(".png"):
                        raise ValidationError("Botão 14: fundo do mosaico inválido")
                    saved_button["background_tile"] = "./icons/{}".format(wide_background)
            buttons.append(saved_button)

        return {
            "brightness": brightness,
            "label_style": {
                "Align": str(label_input.get("Align", "bottom")),
                "Color": color,
                "FontName": str(label_input.get("FontName", "Roboto")),
                "ShowTitle": bool(label_input.get("ShowTitle", True)),
                "Size": font_size,
                "Weight": font_weight,
            },
            "obs": {
                "host": str(obs_input.get("host") or "localhost").strip(),
                "port": obs_port,
                "password": obs_input.get("password") or None,
            },
            "buttons": buttons,
            "background": background,
        }

    @staticmethod
    def _required(params: Dict[str, Any], key: str, index: int) -> str:
        value = str(params.get(key) or "").strip()
        if not value:
            raise ValidationError("Botão {}: preencha {}".format(index + 1, key))
        return value

    def _validate_params(self, index: int, action: str, raw: Dict[str, Any]) -> Dict[str, str]:
        if not isinstance(raw, dict):
            raise ValidationError("Botão {}: parâmetros inválidos".format(index + 1))
        if action == "command":
            return {"cmd": self._required(raw, "cmd", index)}
        if action == "app":
            return {"name": self._required(raw, "name", index)}
        if action == "key":
            return {"keys": self._required(raw, "keys", index)}

        obs_action = str(raw.get("action") or "")
        if obs_action not in ALLOWED_OBS_ACTIONS:
            raise ValidationError("Botão {}: ação OBS inválida".format(index + 1))
        params = {"action": obs_action}
        if obs_action == "toggle_scene":
            params["scene1"] = self._required(raw, "scene1", index)
            params["scene2"] = self._required(raw, "scene2", index)
        elif obs_action == "set_scene":
            params["scene"] = self._required(raw, "scene", index)
        elif obs_action == "toggle_source":
            params["scene"] = self._required(raw, "scene", index)
            params["source"] = self._required(raw, "source", index)
        return params

    def upload_icon(self, payload: Dict[str, Any]) -> str:
        encoded = str(payload.get("data") or "")
        if "," in encoded:
            encoded = encoded.split(",", 1)[1]
        try:
            image_bytes = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValidationError("Arquivo de imagem inválido") from exc
        if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
            raise ValidationError("A imagem deve ter no máximo 8 MB")

        requested_path = Path(str(payload.get("name") or "icone.png"))
        requested = requested_path.stem
        safe_stem = ICON_NAME_RE.sub("-", requested).strip(".-") or "icone"
        wide = bool(payload.get("wide"))
        if wide:
            digest = hashlib.sha256(image_bytes).hexdigest()[:10]
            filename = "{}-{}.gif".format(safe_stem[:69], digest)
        else:
            filename = "{}.png".format(safe_stem[:80])
        destination = self.icons_dir / filename

        try:
            with tempfile.NamedTemporaryFile("wb", dir=self.icons_dir, delete=False) as source:
                source.write(image_bytes)
                source_path = Path(source.name)
            with Image.open(source_path) as image:
                if wide and max(image.size) > MAX_IMAGE_DIMENSION:
                    raise ValidationError("O GIF não pode ultrapassar 4096 px")
                if not wide and image.width * image.height > MAX_STATIC_IMAGE_PIXELS:
                    raise ValidationError("A imagem não pode ultrapassar 40 megapixels")
                if wide:
                    if image.format != "GIF" or not getattr(image, "is_animated", False):
                        raise ValidationError("O botão 14 requer um GIF animado")
                    if image.n_frames > MAX_GIF_FRAMES:
                        raise ValidationError(
                            f"O GIF pode ter no máximo {MAX_GIF_FRAMES} quadros"
                        )
                    frames = [
                        ImageOps.fit(
                            frame.convert("RGBA"),
                            (458, 196),
                            Image.Resampling.LANCZOS,
                        )
                        for frame in ImageSequence.Iterator(image)
                    ]
                    durations = [
                        max(20, int(frame.info.get("duration", 100)))
                        for frame in ImageSequence.Iterator(image)
                    ]
                    with tempfile.NamedTemporaryFile(
                        "wb", dir=self.icons_dir, suffix=".gif", delete=False
                    ) as output:
                        output_path = Path(output.name)
                    frames[0].save(
                        output_path,
                        format="GIF",
                        save_all=True,
                        append_images=frames[1:],
                        duration=durations,
                        loop=int(image.info.get("loop", 0)),
                        disposal=2,
                        optimize=True,
                    )
                else:
                    rendered = ImageOps.fit(
                        image.convert("RGBA"),
                        (196, 196),
                        Image.Resampling.LANCZOS,
                    )
                    with tempfile.NamedTemporaryFile(
                        "wb", dir=self.icons_dir, suffix=".png", delete=False
                    ) as output:
                        output_path = Path(output.name)
                    rendered.save(output_path, format="PNG", optimize=True)
            if output_path.stat().st_size > MAX_IMAGE_BYTES:
                raise ValidationError("A imagem preparada deve ter no máximo 8 MB")
            os.replace(output_path, destination)
        except (UnidentifiedImageError, OSError) as exc:
            raise ValidationError("Formato de imagem não suportado") from exc
        finally:
            if "source_path" in locals() and source_path.exists():
                source_path.unlink()
            if "output_path" in locals() and output_path.exists():
                output_path.unlink()

        logger.info("Icon saved to %s", destination)
        return filename

    def _recover_mosaic_source(self, buttons: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Recover legacy background pixels without baking overlaid icons into the source."""
        canvas = Image.new("RGBA", (980, 588), (0, 0, 0, 255))
        recovered = False
        include_wide = False
        for index, button in enumerate(buttons):
            name = button.get("background_tile") or ""
            if index == WIDE_DISPLAY_INDEX:
                if button["display_mode"] not in {"background", "stats"}:
                    continue
                if not name and button["display_mode"] == "background":
                    name = button.get("image") or ""
            if not name:
                continue
            path = self.icons_dir / name
            if path.is_symlink() or path.resolve().parent != self.icons_dir.resolve():
                raise ValidationError("Origem da imagem de fundo inválida")
            try:
                with Image.open(path) as tile:
                    if max(tile.size) > MAX_IMAGE_DIMENSION or getattr(tile, "is_animated", False):
                        continue
                    if index == WIDE_DISPLAY_INDEX:
                        face = tile.convert("RGBA").resize((392, 196), Image.Resampling.LANCZOS)
                        position = (588, 392)
                        include_wide = True
                    else:
                        face = ImageOps.fit(tile.convert("RGBA"), (196, 196), Image.Resampling.LANCZOS)
                        row, column = divmod(index, 5)
                        position = (column * 196, row * 196)
                    canvas.alpha_composite(face, position)
                    recovered = True
            except (UnidentifiedImageError, OSError):
                # A legacy configuration with a missing tile remains readable.
                continue
        if not recovered:
            return None
        encoded = io.BytesIO()
        canvas.save(encoded, format="PNG", optimize=True)
        image_bytes = encoded.getvalue()
        name = f"mosaic-source-{hashlib.sha256(image_bytes).hexdigest()}.png"
        self._store_mosaic_source(name, image_bytes)
        return {
            "source": name, "scale": 100, "darkness": 0, "include_wide": include_wide,
        }

    @staticmethod
    def _background_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValidationError("Ajustes da imagem de fundo inválidos")
        source = payload.get("source")
        if not isinstance(source, str) or not MOSAIC_SOURCE_RE.fullmatch(source):
            raise ValidationError("Origem da imagem de fundo inválida")
        try:
            scale = int(payload.get("scale", 100))
            darkness = int(payload.get("darkness", 0))
        except (TypeError, ValueError) as exc:
            raise ValidationError("Ajustes da imagem de fundo inválidos") from exc
        if not 25 <= scale <= 200:
            raise ValidationError("O tamanho do fundo deve estar entre 25% e 200%")
        if not 0 <= darkness <= 80:
            raise ValidationError("O escurecimento deve estar entre 0% e 80%")
        include_wide = payload.get("include_wide", False)
        if not isinstance(include_wide, bool):
            raise ValidationError("A opção de incluir a tela larga deve ser verdadeira ou falsa")
        return {
            "source": source,
            "scale": scale,
            "darkness": darkness,
            "include_wide": include_wide,
        }

    def _mosaic_source_bytes(self, name: str) -> bytes:
        match = MOSAIC_SOURCE_RE.fullmatch(name)
        if not match:
            raise ValidationError("Origem da imagem de fundo inválida")
        path = self.icons_dir / name
        if path.is_symlink() or path.resolve().parent != self.icons_dir.resolve():
            raise ValidationError("Origem da imagem de fundo inválida")
        try:
            with path.open("rb") as handle:
                image_bytes = handle.read(MAX_IMAGE_BYTES + 1)
        except OSError as exc:
            raise ValidationError("A imagem original do fundo não está disponível; envie outra imagem") from exc
        if (
            not image_bytes
            or len(image_bytes) > MAX_IMAGE_BYTES
            or hashlib.sha256(image_bytes).hexdigest() != match[1]
        ):
            raise ValidationError("Origem da imagem de fundo inválida")
        return image_bytes

    def _store_mosaic_source(self, name: str, image_bytes: bytes) -> None:
        destination = self.icons_dir / name
        if destination.exists() or destination.is_symlink():
            if self._mosaic_source_bytes(name) != image_bytes:
                raise ValidationError("Origem da imagem de fundo inválida")
            return
        with tempfile.NamedTemporaryFile(
            "wb", dir=self.icons_dir, prefix=".mosaic-source-", delete=False
        ) as output:
            output_path = Path(output.name)
        try:
            output_path.write_bytes(image_bytes)
            os.replace(output_path, destination)
        finally:
            if output_path.exists():
                output_path.unlink()

    def upload_mosaic(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Render every edit from its immutable original, never from generated tiles."""
        if payload.get("source"):
            if payload.get("data"):
                raise ValidationError("Escolha uma imagem original ou um novo arquivo, não ambos")
            settings = self._background_settings(payload)
            image_bytes = self._mosaic_source_bytes(settings["source"])
        else:
            encoded = str(payload.get("data") or "")
            if "," in encoded:
                encoded = encoded.split(",", 1)[1]
            try:
                image_bytes = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise ValidationError("Arquivo de imagem inválido") from exc
            if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
                raise ValidationError("A imagem deve ter no máximo 8 MB")
            settings = None

        canvas_size = (5 * 196, 3 * 196)
        try:
            with Image.open(io.BytesIO(image_bytes)) as image:
                if image.width * image.height > MAX_STATIC_IMAGE_PIXELS:
                    raise ValidationError("A imagem não pode ultrapassar 40 megapixels")
                if getattr(image, "is_animated", False):
                    raise ValidationError("O mosaico requer uma imagem estática")
                if image.format not in {"PNG", "JPEG", "WEBP"}:
                    raise ValidationError("Use uma imagem PNG, JPG ou WebP")
                if settings is None:
                    source_name = (
                        f"mosaic-source-{hashlib.sha256(image_bytes).hexdigest()}."
                        f"{image.format.lower()}"
                    )
                    settings = self._background_settings({**payload, "source": source_name})
                scale = settings["scale"]
                darkness = settings["darkness"]
                source = ImageOps.exif_transpose(image).convert("RGBA")
                self._store_mosaic_source(settings["source"], image_bytes)
                fitted = ImageOps.fit(source, canvas_size, Image.Resampling.LANCZOS)
                if scale != 100:
                    scaled_size = tuple(round(dimension * scale / 100) for dimension in canvas_size)
                    fitted = fitted.resize(scaled_size, Image.Resampling.LANCZOS)
                if scale > 100:
                    left = (fitted.width - canvas_size[0]) // 2
                    top = (fitted.height - canvas_size[1]) // 2
                    fitted = fitted.crop((
                        left, top, left + canvas_size[0], top + canvas_size[1],
                    ))
                canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 255))
                canvas.alpha_composite(fitted, (
                    (canvas_size[0] - fitted.width) // 2,
                    (canvas_size[1] - fitted.height) // 2,
                ))
                if darkness:
                    shade = Image.new(
                        "RGBA", canvas_size, (0, 0, 0, round(255 * darkness / 100))
                    )
                    canvas = Image.alpha_composite(canvas, shade)
        except (UnidentifiedImageError, OSError) as exc:
            raise ValidationError("Formato de imagem não suportado") from exc

        digest = hashlib.sha256(
            image_bytes + f"\0{scale}\0{darkness}".encode("ascii")
        ).hexdigest()[:10]
        tiles = []
        for index in range(13):
            row, column = divmod(index, 5)
            tiles.append((f"{index + 1:02d}", canvas.crop((
                column * 196, row * 196, (column + 1) * 196, (row + 1) * 196,
            ))))
        if settings["include_wide"]:
            wide = canvas.crop((3 * 196, 2 * 196, 5 * 196, 3 * 196))
            tiles.append(("wide", wide.resize((458, 196), Image.Resampling.LANCZOS)))
        filenames = []
        for suffix, tile in tiles:
            filename = f"mosaic-{digest}-{suffix}.png"
            destination = self.icons_dir / filename
            with tempfile.NamedTemporaryFile(
                "wb", dir=self.icons_dir, suffix=".png", delete=False
            ) as output:
                output_path = Path(output.name)
            try:
                tile.save(output_path, format="PNG", optimize=True)
                os.replace(output_path, destination)
            finally:
                if output_path.exists():
                    output_path.unlink()
            filenames.append(filename)
        logger.info("Mosaic saved from %s", settings["source"])
        return {"filenames": filenames, "background": settings}

    @staticmethod
    def apply() -> Dict[str, Any]:
        result = subprocess.run(
            ["systemctl", "--user", "restart", "ulanzi-daemon.service"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "Falha ao reiniciar o daemon"
            raise RuntimeError(message)
        return {"applied": True}

    @staticmethod
    def status() -> Dict[str, Any]:
        service = subprocess.run(
            ["systemctl", "--user", "is-active", "ulanzi-daemon.service"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        device_connected = False
        for vendor_file in Path("/sys/bus/usb/devices").glob("*/idVendor"):
            try:
                product_file = vendor_file.with_name("idProduct")
                if vendor_file.read_text().strip() == "2207" and product_file.read_text().strip() == "0019":
                    device_connected = True
                    break
            except OSError:
                continue
        return {"service": service or "unknown", "device_connected": device_connected}


class RequestHandler(BaseHTTPRequestHandler):
    server_version = "UlanziWeb/1.0"

    @property
    def app(self) -> WebApp:
        return self.server.app  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: Any) -> None:
        logger.info("%s - %s", self.address_string(), fmt % args)

    def _host_allowed(self) -> bool:
        authorities = self.headers.get_all("Host", [])
        if len(authorities) != 1:
            return False
        authority = authorities[0]
        if not authority or any(character.isspace() for character in authority):
            return False
        try:
            parsed = urlparse(f"//{authority}")
            hostname = parsed.hostname
            port = parsed.port
        except ValueError:
            return False
        if (
            hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.netloc != authority
            or parsed.path
            or parsed.params
            or parsed.query
            or parsed.fragment
        ):
            return False
        host = f"[{hostname}]" if hostname == "::1" else hostname
        normalized = authority.lower()
        if normalized == host:
            return True
        if not normalized.startswith(f"{host}:") or port is None:
            return False
        port_text = normalized[len(host) + 1:]
        return port_text.isascii() and port_text.isdigit()

    def _json(self, payload: Dict[str, Any], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Dict[str, Any]:
        if self.headers.get_content_type() != "application/json":
            raise ValidationError("Content-Type deve ser application/json")
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValidationError("Content-Length inválido") from exc
        if size <= 0 or size > MAX_JSON_BYTES:
            raise ValidationError("Corpo da requisição vazio ou muito grande")
        try:
            payload = json.loads(self.rfile.read(size))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValidationError("JSON inválido") from exc
        if not isinstance(payload, dict):
            raise ValidationError("O corpo JSON deve ser um objeto")
        return payload

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _handle_error(self, exc: Exception) -> None:
        if isinstance(exc, ValidationError):
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        else:
            logger.exception("Request failed")
            self._json({"error": str(exc) or "Erro interno"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_GET(self) -> None:
        if not self._host_allowed():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        path = urlparse(self.path).path
        try:
            if path == "/api/config":
                self._json(self.app.get_config())
            elif path == "/api/status":
                self._json(self.app.status())
            elif path == "/api/applications":
                self._json({"applications": self.app.list_applications()})
            elif path == "/api/layouts":
                self._json({"layouts": self.app.list_layouts()})
            elif path.startswith("/api/layouts/"):
                layout_id = unquote(path[len("/api/layouts/"):])
                self._json(self.app.load_layout(layout_id))
            elif path.startswith("/api/icons/"):
                name = Path(unquote(path[len("/api/icons/"):])).name
                content_type = "image/gif" if Path(name).suffix.lower() == ".gif" else "image/png"
                self._send_file(self.app.icons_dir / name, content_type)
            elif path in {"/", "/index.html"}:
                self._send_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            elif path == "/app.js":
                self._send_file(STATIC_DIR / "app.js", "text/javascript; charset=utf-8")
            elif path == "/style.css":
                self._send_file(STATIC_DIR / "style.css", "text/css; charset=utf-8")
            elif path.startswith("/fonts/"):
                name = unquote(path[len("/fonts/"):])
                allowed = {filename for family in METRICS_FONT_FILES.values() for filename in family.values()}
                if name not in allowed:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                self._send_file(STATIC_DIR / "fonts" / name, "font/ttf")
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._handle_error(exc)

    def do_PUT(self) -> None:
        if not self._host_allowed():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        try:
            if urlparse(self.path).path != "/api/config":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self._json(self.app.save_config(self._read_json()))
        except Exception as exc:
            self._handle_error(exc)

    def do_POST(self) -> None:
        if not self._host_allowed():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        path = urlparse(self.path).path
        try:
            if path == "/api/apply":
                self._read_json()
                self._json(self.app.apply())
            elif path == "/api/applications/icon":
                self._json(
                    self.app.prepare_application_icon(self._read_json()),
                    HTTPStatus.CREATED,
                )
            elif path == "/api/icons":
                filename = self.app.upload_icon(self._read_json())
                self._json({"filename": filename}, HTTPStatus.CREATED)
            elif path == "/api/mosaic":
                self._json(self.app.upload_mosaic(self._read_json()), HTTPStatus.CREATED)
            elif path == "/api/layouts":
                self._json(
                    self.app.save_layout(self._read_json()),
                    HTTPStatus.CREATED
                )
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._handle_error(exc)

    def do_DELETE(self) -> None:
        if not self._host_allowed():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        path = urlparse(self.path).path
        try:
            if not path.startswith("/api/layouts/"):
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            layout_id = unquote(path[len("/api/layouts/"):])
            self._json(self.app.delete_layout(layout_id))
        except Exception as exc:
            self._handle_error(exc)


class IPv6HTTPServer(ThreadingHTTPServer):
    address_family = socket.AF_INET6


def main() -> None:
    parser = argparse.ArgumentParser(description="Interface web local do Ulanzi D200")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--config", default="~/.config/ulanzi/config.yaml")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    server_type = IPv6HTTPServer if ":" in args.host else ThreadingHTTPServer
    server = server_type((args.host, args.port), RequestHandler)
    server.app = WebApp(Path(args.config))  # type: ignore[attr-defined]
    url_host = f"[{args.host}]" if ":" in args.host else args.host
    logger.info("Ulanzi UI available at http://%s:%s", url_host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
