"""Tests for core.ziro_load."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".ziro"))

from core.ziro_load import (
    LoadSpec,
    emit,
    emit_deferred,
    emit_eager,
    emit_raw,
    from_resolved,
)


class TestEmitEager(unittest.TestCase):
    def test_plain_eager(self):
        spec = LoadSpec("my-plugin", "eager")
        self.assertEqual(emit(spec), "znap source my-plugin")

    def test_eager_with_eval_cache(self):
        spec = LoadSpec("zoxide", "eager", eval_cache="zoxide init zsh")
        self.assertEqual(emit(spec), "znap eval zoxide 'zoxide init zsh'")

    def test_eager_with_pick(self):
        spec = LoadSpec("multi", "eager", pick="main.plugin.zsh")
        self.assertIn("--pick=main.plugin.zsh", emit(spec))


class TestEmitDeferred(unittest.TestCase):
    def test_plain_deferred(self):
        spec = LoadSpec("heavy", "after-prompt")
        out = emit(spec)
        self.assertIn("--stage=5", out)
        self.assertIn("--slot=b", out)
        self.assertIn("--name=heavy", out)
        self.assertIn("znap source heavy", out)

    def test_deferred_with_slot(self):
        spec = LoadSpec("heavy", "after-prompt", sub_slot="b")
        out = emit(spec)
        self.assertIn("--stage=5", out)
        self.assertIn("--slot=b", out)
        self.assertIn("znap source heavy", out)

    def test_deferred_rejects_numeric_zero_slot(self):
        # Regression test for Bug #5: slot '0' is invalid per Spec 005 (only a|b|c)
        spec = LoadSpec("heavy", "after-prompt", sub_slot="0")
        out = emit(spec)
        self.assertIn("--slot=b", out)
        self.assertNotIn("--slot=0", out)

    def test_local_plugin_emits_source(self):
        # Regression test for Bug #5: local clone in plugins/ must emit ziro local source
        spec = LoadSpec("$ZIRO_HOME/plugins/git/git.plugin.zsh", "eager", is_local=True)
        self.assertEqual(emit(spec), "ziro local source $ZIRO_HOME/plugins/git/git.plugin.zsh")

    def test_local_plugin_deferred_emits_source(self):
        spec = LoadSpec("$ZIRO_HOME/plugins/wd/wd.plugin.zsh", "after-prompt", is_local=True)
        out = emit(spec)
        self.assertIn("--stage=5", out)
        self.assertIn("--slot=b", out)
        self.assertIn("ziro local source", out)


class TestEmitRaw(unittest.TestCase):
    def test_raw_verbatim(self):
        spec = LoadSpec("custom", "raw", raw='znap source custom --deep')
        self.assertEqual(emit(spec), "znap source custom --deep")


class TestFromResolved(unittest.TestCase):
    def test_maps_eager(self):
        spec = from_resolved("p1", "EAGER")
        self.assertEqual(spec.strategy, "eager")

    def test_maps_after_prompt(self):
        spec = from_resolved("p2", "AFTER_PROMPT", defer_slot="b")
        self.assertEqual(spec.strategy, "after-prompt")
        self.assertEqual(spec.sub_slot, "b")

    def test_unknown_strategy_fallback(self):
        spec = from_resolved("p4", "weird-strategy")
        self.assertEqual(spec.strategy, "eager")


if __name__ == "__main__":
    unittest.main()
