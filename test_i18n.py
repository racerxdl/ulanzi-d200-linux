"""Every Portuguese UI string must have an English translation in static/i18n.js."""

import ast
import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

PACKAGE = Path(__file__).parent / "ulanzi_manager"
STATIC = PACKAGE / "static"

# Text in index.html that is the same in every language.
LANGUAGE_NEUTRAL = {
    "Ulanzi D200", "LAYOUT", "CPU", "RAM", "GPU", "OBS Studio", "Normal", "Ubuntu", "Ubuntu Mono",
    "Noto Sans", "Noto Serif", "Liberation Sans", "Liberation Serif", "Idioma / Language",
    # Replaced on load by app.js with a translated "Botão {number}".
    "Botão 1",
}
TRANSLATED_ATTRIBUTES = {"placeholder", "aria-label", "title", "alt"}
PORTUGUESE = re.compile(r"[ãõçáéíóúâêôà]|\b(inválid[oa]s?|deve|selecione|preencha|informe|use uma|erro)\b", re.I)
PLACEHOLDER = re.compile(r"\{(\w*)\}")


def english_translations():
    """Read the en table: one '"pt": "en",' entry per line."""
    source = (STATIC / "i18n.js").read_text(encoding="utf-8")
    entry = re.compile(r'^\s*("(?:[^"\\]|\\.)*")\s*:\s*("(?:[^"\\]|\\.)*"),\s*$')
    table = {}
    for line in source.splitlines():
        match = entry.match(line)
        if match:
            table[json.loads(match[1])] = json.loads(match[2])
    return table


class _StaticText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.found = []  # (key, description)
        self.stack = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self.stack.append(attributes.get("data-i18n-context"))
        for name, value in attrs:
            if name in TRANSLATED_ATTRIBUTES and value:
                self.found.append((value, f"<{tag} {name}>"))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.stack.pop()

    def handle_endtag(self, tag):
        if self.stack:
            self.stack.pop()

    def handle_data(self, data):
        text = data.strip()
        if text:
            context = self.stack[-1] if self.stack else None
            self.found.append((f"{context}|{text}" if context else text, "text"))


def _app_keys():
    """Collect every string app.js passes through t(), tc() or the helpers that call t()."""
    source = (STATIC / "app.js").read_text(encoding="utf-8")
    literal = r'"((?:[^"\\]|\\.)*)"'
    keys = set()
    for pattern in (
        rf"\b(?:t|setSaveState|setMosaicStatus)\(\s*{literal}",
        rf"\bsetStatus\([^,]+,[^,]+,\s*{literal},\s*{literal}\)",
        rf"\bt\([^\"()]*?\?\s*{literal}\s*:\s*{literal}\s*\)",
        rf'\["(?:toggle_scene|set_scene|toggle_source|toggle_recording|toggle_streaming)",\s*{literal}\]',
        rf"saveState:\s*\[{literal}\]",
    ):
        for match in re.finditer(pattern, source, re.S):
            keys.update(json.loads(f'"{group}"') for group in match.groups() if group)
    for match in re.finditer(rf"\btc\(\s*{literal},\s*{literal}", source):
        keys.add(f"{match[1]}|{match[2]}")
    return source, keys


def _server_messages():
    """Portuguese error messages raised by the server and shown in the UI."""
    messages = set()
    for path in (PACKAGE / "web.py", PACKAGE / "config.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        # The literal pieces of an f-string are checked as part of the whole f-string.
        fragments = {id(part) for node in ast.walk(tree) if isinstance(node, ast.JoinedStr) for part in node.values}
        for node in ast.walk(tree):
            if id(node) in fragments:
                continue
            if isinstance(node, ast.JoinedStr):
                text = "".join(
                    part.value if isinstance(part, ast.Constant) else "{}" for part in node.values
                )
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = node.value
            else:
                continue
            if PORTUGUESE.search(text) and "\n" not in text and not text.startswith(("Name[", "%")):
                messages.add(text)
    return messages


def _normalise(text):
    return PLACEHOLDER.sub("{}", text)


class TranslationCoverageTests(unittest.TestCase):
    def setUp(self):
        self.english = english_translations()

    def test_table_was_parsed(self):
        self.assertGreater(len(self.english), 150)

    def test_static_page_text_is_translated(self):
        parser = _StaticText()
        parser.feed((STATIC / "index.html").read_text(encoding="utf-8"))
        missing = sorted({
            f"{key!r} ({where})" for key, where in parser.found
            if key not in self.english and key not in LANGUAGE_NEUTRAL
            and not re.fullmatch(r"[\d\s%.,×+–-]*(px)?", key)
        })
        self.assertEqual([], missing, "index.html text without an English translation")

    def test_script_text_is_translated(self):
        source, keys = _app_keys()
        self.assertGreater(len(keys), 60)
        self.assertEqual([], sorted(keys - set(self.english)), "app.js text without an English translation")
        # Catch Portuguese literals added without going through t().
        literals = {json.loads(f'"{text}"') for text in re.findall(r'"((?:[^"\\]|\\.)*)"', source)}
        untranslated = sorted(text for text in literals if PORTUGUESE.search(text) and text not in self.english)
        self.assertEqual([], untranslated, "Portuguese text in app.js that is not translated")

    def test_server_messages_are_translated(self):
        known = {_normalise(key) for key in self.english}
        missing = []
        for message in _server_messages():
            # i18n.message() translates the "Botão N: " prefix and the rest separately.
            rest = re.sub(r"^Botão (\{\}|\d+): ", "", message)
            if rest != "{}" and _normalise(rest) not in known:
                missing.append(message)
        self.assertEqual([], sorted(missing), "server messages without an English translation")

    def test_placeholders_match(self):
        mismatched = sorted(
            key for key, value in self.english.items()
            if sorted(PLACEHOLDER.findall(key)) != sorted(PLACEHOLDER.findall(value))
        )
        self.assertEqual([], mismatched)


if __name__ == "__main__":
    unittest.main()
