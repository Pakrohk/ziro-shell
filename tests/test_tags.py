"""Tests for core.tags."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".ziro"))

from core.tags import (
    Tag,
    load_builtin_tags,
    load_all_tags,
    load_plugin_tags,
    save_plugin_tags,
)

import pytest
pytestmark = pytest.mark.unit

# Minimal tag set covering the builtins asserted below. Avoids depending on
# $HOME/.config/ziro/tags/builtin.toml (created by install, gitignored, and
# therefore absent on ephemeral CI runners).
_MIN_BUILTIN_TOML = (
    '[[tags]]\nname = "@eager"\nstrategy = "eager"\npriority = 10\n'
    '[[tags]]\nname = "@compdef"\nstrategy = "eager"\npriority = 15\n'
    '[[tags]]\nname = "@lazy"\nstrategy = "defer"\npriority = 5\n'
    '[[tags]]\nname = "@raw"\nstrategy = "eager"\npriority = 0\n'
    '[[tags]]\nname = "@no-compile"\nstrategy = "eager"\ncompile = false\n'
    '[[tags]]\nname = "@defer-shell"\nstrategy = "defer"\n'
    '[[tags]]\nname = "@defer-comp"\nstrategy = "defer"\n'
)


def _seeded_config(tmp: str) -> Path:
    """Temp config dir with a minimal builtin.toml — self-contained."""
    cfg = Path(tmp)
    (cfg / "tags" / "plugins").mkdir(parents=True, exist_ok=True)
    (cfg / "tags" / "builtin.toml").write_text(_MIN_BUILTIN_TOML)
    return cfg


class TestTag(unittest.TestCase):
    def test_is_builtin(self):
        self.assertTrue(Tag("@eager", "eager").is_builtin())
        self.assertFalse(Tag("my-tag", "eager").is_builtin())


class TestBuiltinLoad(unittest.TestCase):
    def test_loads_builtins(self):
        with tempfile.TemporaryDirectory() as tmp:
            tags = load_builtin_tags(_seeded_config(tmp))
            self.assertIn("@eager", tags)
            self.assertIn("@compdef", tags)
            self.assertEqual(tags["@compdef"].priority, 15)
            self.assertEqual(tags["@eager"].priority, 10)


class TestPluginTags(unittest.TestCase):
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _seeded_config(tmp)
            save_plugin_tags(cfg, "myplugin", ["@eager", "@no-compile"])
            loaded = load_plugin_tags(cfg, "myplugin")
            self.assertEqual(set(loaded), {"@eager", "@no-compile"})


class TestAllTags(unittest.TestCase):
    def test_all_contains_builtins(self):
        with tempfile.TemporaryDirectory() as tmp:
            all_tags = load_all_tags(_seeded_config(tmp))
            for name in ("@eager", "@compdef", "@lazy", "@raw"):
                self.assertIn(name, all_tags)


if __name__ == "__main__":
    unittest.main()
