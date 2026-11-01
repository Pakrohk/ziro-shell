"""Tests for core.theme_resolver."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path.home() / ".ziro"))
from core.theme_resolver import (
    EnvContext, resolve_prompt_theme, resolve_all,
)

import pytest
pytestmark = pytest.mark.unit


class TestResolvePrompt(unittest.TestCase):
    def test_server_gets_minimal(self):
        ctx = EnvContext(env_type="server", has_nerd_font=True, has_truecolor=True)
        self.assertEqual(resolve_prompt_theme(ctx), "minimal")

    def test_no_nerd_font_gets_minimal(self):
        ctx = EnvContext(env_type="desktop", has_nerd_font=False, has_truecolor=True)
        self.assertEqual(resolve_prompt_theme(ctx), "minimal")

    def test_desktop_full_gets_powerline(self):
        ctx = EnvContext(env_type="desktop", has_nerd_font=True, has_truecolor=True)
        self.assertEqual(resolve_prompt_theme(ctx), "powerline")

    def test_256color_fallback(self):
        ctx = EnvContext(env_type="desktop", has_nerd_font=True, has_truecolor=False)
        self.assertEqual(resolve_prompt_theme(ctx), "standard")


class TestResolveAll(unittest.TestCase):
    def test_all_components_present(self):
        ctx = EnvContext()
        result = resolve_all(ctx)
        for key in ("prompt", "auto_suggest", "colors", "syntax_highlighting"):
            self.assertIn(key, result)


if __name__ == "__main__":
    unittest.main()
