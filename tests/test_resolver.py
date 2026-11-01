"""Tests for core.resolver."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".ziro"))

from core.models import (
    AnalysisResult, DetectedSignals, Recommendation, Strategy,
)
from core.resolver import resolve, ConflictError

import pytest
pytestmark = pytest.mark.unit

# Minimal tag set covering the builtins used below. Avoids depending on
# $HOME/.config/ziro/tags/builtin.toml (created by install, gitignored, and
# therefore absent on ephemeral CI runners).
_MIN_BUILTIN_TOML = (
    '[[tags]]\nname = "@eager"\nstrategy = "eager"\npriority = 10\n'
    '[[tags]]\nname = "@lazy"\nstrategy = "defer"\npriority = 5\n'
)


def _analysis(plugin: str, strategy: Strategy = Strategy.LAZY) -> AnalysisResult:
    return AnalysisResult(
        plugin=plugin,
        source="test",
        detected=DetectedSignals(),
        recommended=Recommendation(strategy=strategy),
    )


def _fixture_config(tmp: str) -> Path:
    """Self-contained temp config dir with a minimal builtin.toml."""
    cfg = Path(tmp)
    (cfg / "tags" / "plugins").mkdir(parents=True, exist_ok=True)
    (cfg / "tags" / "builtin.toml").write_text(_MIN_BUILTIN_TOML)
    return cfg


class TestResolve(unittest.TestCase):
    def test_no_tags_keeps_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = resolve(_analysis("no-tags-plugin"), _fixture_config(tmp))
            self.assertEqual(r.strategy, Strategy.LAZY)
            self.assertEqual(r.applied_tags, ())

    def test_eager_tag_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _fixture_config(tmp)
            from core.tags import save_plugin_tags
            save_plugin_tags(cfg, "eager-plugin", ["@eager"])
            r = resolve(_analysis("eager-plugin"), cfg)
            self.assertEqual(r.strategy, Strategy.EAGER)
            self.assertIn("@eager", r.applied_tags)

    def test_conflict_raises_when_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _fixture_config(tmp)
            from core.tags import save_plugin_tags
            save_plugin_tags(cfg, "conflict-plugin", ["@eager", "@lazy"])
            with self.assertRaises(ConflictError):
                resolve(_analysis("conflict-plugin"), cfg, raise_on_conflict=True)


if __name__ == "__main__":
    unittest.main()
