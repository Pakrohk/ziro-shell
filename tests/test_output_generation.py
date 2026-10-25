"""Tests for Defer v2 output generation (Spec 001/002/005)."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from core.generator import generate
from core.models import AnalysisResult, DetectedSignals, Recommendation, Strategy
from core.resolver import ResolvedConfig, resolve
from core.ziro_load import LoadSpec, emit, emit_deferred


class TestOutputGeneration(unittest.TestCase):
    def test_default_stage_slot(self):
        """No stage/slot passed → default --stage=5 --slot=b."""
        spec = LoadSpec("myplugin", "lazy")
        out = emit_deferred(spec)
        self.assertIn("--stage=5", out)
        self.assertIn("--slot=b", out)

    def test_explicit_stage_slot(self):
        """Explicit stage=2, slot=a reflected in output."""
        spec = LoadSpec("comp", "lazy", stage=2, slot="a")
        out = emit_deferred(spec)
        self.assertIn("--stage=2", out)
        self.assertIn("--slot=a", out)

    def test_name_present(self):
        """Explicit name='foo' produces --name=foo."""
        spec = LoadSpec("foo_plugin", "lazy", name="foo")
        out = emit_deferred(spec)
        self.assertIn("--name=foo", out)

    def test_depends_chain(self):
        """depends=('a', 'b') produces --depends="a b"."""
        spec = LoadSpec("bar", "lazy", depends=("a", "b"))
        out = emit_deferred(spec)
        self.assertIn('--depends="a b"', out)

    def test_condition_if_cmd(self):
        """condition='if-cmd=git' produces --if-cmd=git."""
        spec = LoadSpec("git_tool", "lazy", condition="if-cmd=git")
        out = emit_deferred(spec)
        self.assertIn("--if-cmd=git", out)

    def test_on_key_uses_bind_widget(self):
        """on_key='^R' produces ziro-defer-bind-widget '^R'."""
        spec = LoadSpec("widget", "lazy", on_key="^R")
        out = emit_deferred(spec)
        self.assertIn("ziro-defer-bind-widget '^R'", out)

    def test_no_wait_in_output(self):
        """Output must never contain --wait."""
        spec = LoadSpec("test", "lazy")
        out = emit_deferred(spec)
        self.assertNotIn("--wait", out)

    def test_no_lazy_by_command(self):
        """Output must never contain --lazy-by-command."""
        spec = LoadSpec("test", "lazy")
        out = emit_deferred(spec)
        self.assertNotIn("--lazy-by-command", out)

    def test_timeout_present(self):
        """timeout_ms=5000 produces --timeout=5000."""
        spec = LoadSpec("test", "lazy", timeout_ms=5000)
        out = emit_deferred(spec)
        self.assertIn("--timeout=5000", out)

    def test_full_pipeline_integration(self):
        """End-to-end: analyzer recommendation → resolver → generator → zsh -n."""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            cfg_dir = p / "config"
            cfg_dir.mkdir(parents=True)

            rec = Recommendation(
                strategy=Strategy.AFTER_PROMPT,
                stage=5,
                slot="b",
                name="test_plugin",
                depends=("dep1",),
                condition="if-cmd=git",
                timeout_ms=5000,
            )
            analysis = AnalysisResult(
                plugin="test-plugin",
                source=str(p),
                detected=DetectedSignals(),
                recommended=rec,
                confidence=1.0,
            )

            resolved = resolve(analysis, cfg_dir)
            out_file = p / "plugins.gen.zsh"
            generate([resolved], out_file)
            content = out_file.read_text(encoding="utf-8")

            self.assertIn("ziro-defer --stage=5 --slot=b --name=test_plugin", content)
            self.assertIn('--depends="dep1"', content)
            self.assertIn("--if-cmd=git", content)
            self.assertIn("--timeout=5000", content)

            # Check valid zsh syntax
            proc = subprocess.run(
                ["zsh", "-n", str(out_file)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, f"zsh -n failed: {proc.stderr}")


if __name__ == "__main__":
    unittest.main()
