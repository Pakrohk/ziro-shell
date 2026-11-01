"""Tests for core.theme."""
import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path.home() / ".ziro"))
from core.theme import (
    ThemeSelection, read_theme_conf, write_theme_conf,
    list_themes, theme_path, COMPONENTS,
)

import pytest
pytestmark = pytest.mark.unit


class TestThemeConf(unittest.TestCase):
    def test_missing_returns_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            sel = read_theme_conf(Path(tmp))
            self.assertEqual(sel.prompt, "powerline")
            self.assertEqual(sel.auto_suggest_component, "ziro-ghost")

    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp)
            sel = ThemeSelection(prompt="minimal", prompt_component="starship")
            write_theme_conf(cfg, sel)
            loaded = read_theme_conf(cfg)
            self.assertEqual(loaded.prompt, "minimal")
            self.assertEqual(loaded.prompt_component, "starship")

    def test_default_component(self):
        sel = ThemeSelection()
        self.assertIn("prompt", COMPONENTS)
        self.assertEqual(sel.auto_suggest_component, "ziro-ghost")


class TestListThemes(unittest.TestCase):
    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(list_themes(Path(tmp), "prompt"), [])

    def test_lists_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp) / "prompt"
            t.mkdir()
            (t / "powerline.toml").write_text("# t")
            (t / "minimal.toml").write_text("# t")
            names = list_themes(Path(tmp), "prompt")
            self.assertEqual(set(names), {"powerline", "minimal"})


if __name__ == "__main__":
    unittest.main()
