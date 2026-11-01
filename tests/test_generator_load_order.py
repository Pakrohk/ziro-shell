"""Tests for load-order enforcement in generator."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".ziro"))

from core.generator import generate, EmitOptions
from core.models import Strategy
from core.resolver import ResolvedConfig

import pytest
pytestmark = pytest.mark.unit


class TestLoadOrder(unittest.TestCase):
    def test_order_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "plugins.gen.zsh"
            configs = [
                ResolvedConfig("zoxide", Strategy.EAGER, eval_cache=True),
                ResolvedConfig("starship", Strategy.EAGER, eval_cache=True),
                ResolvedConfig("zsh-completions", Strategy.EAGER),
                ResolvedConfig("fzf", Strategy.EAGER, eval_cache=True),
            ]
            generate(configs, out, options=EmitOptions(enforce_order=True))
            content = out.read_text()

            idx_completions = content.index("zsh-completions")
            idx_starship = content.index("starship")
            idx_fzf = content.index("fzf")
            idx_zoxide = content.index("zoxide")

            self.assertLess(idx_completions, idx_starship)
            self.assertLess(idx_starship, idx_fzf)
            self.assertLess(idx_fzf, idx_zoxide)

    def test_unknown_plugin_at_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "plugins.gen.zsh"
            configs = [
                ResolvedConfig("unknown-plugin", Strategy.EAGER),
                ResolvedConfig("starship", Strategy.EAGER),
            ]
            generate(configs, out, options=EmitOptions(enforce_order=True))
            content = out.read_text()
            self.assertLess(content.index("starship"), content.index("unknown-plugin"))

    def test_order_disabled_preserves_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "plugins.gen.zsh"
            configs = [
                ResolvedConfig("zoxide", Strategy.EAGER),
                ResolvedConfig("zsh-completions", Strategy.EAGER),
            ]
            generate(configs, out, options=EmitOptions(enforce_order=False))
            content = out.read_text()
            self.assertLess(content.index("zoxide"), content.index("zsh-completions"))


if __name__ == "__main__":
    unittest.main()
