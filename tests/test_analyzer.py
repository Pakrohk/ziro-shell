"""Tests for core.analyzer."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".ziro"))

from core.analyzer import analyze_plugin, _detect_signals, _recommend
from core.models import DetectedSignals, Strategy

import pytest
pytestmark = pytest.mark.unit


class TestDetectSignals(unittest.TestCase):
    def test_empty_content(self):
        signals = _detect_signals("")
        self.assertFalse(signals.has_any())

    def test_compdef_detected(self):
        signals = _detect_signals("compdef _git git")
        self.assertTrue(signals.compdef)

    def test_zle_hook_detected(self):
        signals = _detect_signals("add-zle-hook-widget line-pre-redraw my_widget")
        self.assertTrue(signals.zle_widgets)

    def test_zsh_hook_detected(self):
        signals = _detect_signals("add-zsh-hook precmd my_precmd")
        self.assertIn("precmd", signals.hooks)

    def test_zsh_hook_not_confused_by_autoload(self):
        # 'autoload -Uz add-zsh-hook is-at-least' must NOT yield hook 'is'
        signals = _detect_signals("autoload -Uz add-zsh-hook is-at-least")
        self.assertNotIn("is", signals.hooks)
        self.assertEqual(signals.hooks, ())

    def test_zsh_hook_anchored_at_line_start(self):
        signals = _detect_signals("print -r -- 'zsh-syntax-highlighting: failed loading add-zsh-hook.'")
        self.assertEqual(signals.hooks, ())

    def test_bindkey_detected(self):
        signals = _detect_signals("bindkey '^E' end-of-line")
        self.assertTrue(signals.bindkey)

    def test_path_mod_detected(self):
        signals = _detect_signals('export PATH="$HOME/bin:$PATH"')
        self.assertTrue(signals.modifies_path)


class TestRecommend(unittest.TestCase):
    def test_compdef_is_eager(self):
        signals = DetectedSignals(compdef=True)
        self.assertEqual(_recommend(signals).strategy, Strategy.EAGER)

    def test_zle_is_after_prompt(self):
        signals = DetectedSignals(zle_widgets=True)
        self.assertEqual(_recommend(signals).strategy, Strategy.AFTER_PROMPT)

    def test_no_signals_is_lazy(self):
        signals = DetectedSignals()
        self.assertEqual(_recommend(signals).strategy, Strategy.LAZY)

    def test_path_mod_is_eager(self):
        signals = DetectedSignals(modifies_path=True)
        self.assertEqual(_recommend(signals).strategy, Strategy.EAGER)


class TestAnalyzePlugin(unittest.TestCase):
    def test_nonexistent_dir_returns_empty(self):
        result = analyze_plugin(Path("/nonexistent/path/xyz"), "fake")
        self.assertEqual(result.plugin, "fake")
        self.assertEqual(result.recommended.strategy, Strategy.EAGER)
        self.assertEqual(result.confidence, 0.0)

    def test_real_plugin_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "myplugin.plugin.zsh"
            p.write_text("add-zsh-hook precmd my_hook\ncompdef _my my\n")
            result = analyze_plugin(Path(tmp), "myplugin")
            self.assertTrue(result.detected.compdef)
            self.assertIn("precmd", result.detected.hooks)
            self.assertEqual(result.recommended.pick, "myplugin.plugin.zsh")
            self.assertEqual(result.recommended.strategy, Strategy.EAGER)

    def test_to_dict_is_schema_a(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.plugin.zsh"
            p.write_text("bindkey '^E' end-of-line\n")
            d = analyze_plugin(Path(tmp), "test").to_dict()
            self.assertIn("plugin", d)
            self.assertIn("detected", d)
            self.assertIn("recommended", d)
            self.assertIn("confidence", d)
            self.assertIn("analyzer_version", d)


if __name__ == "__main__":
    unittest.main()
