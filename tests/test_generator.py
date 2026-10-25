"""Tests for core.generator."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".ziro"))

from core.generator import generate, HEADER_LINE, default_output_path, EmitOptions
from core.models import Strategy
from core.resolver import ResolvedConfig


class TestGenerate(unittest.TestCase):
    def test_header_and_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "plugins.gen.zsh"
            configs = [
                ResolvedConfig("p1", Strategy.EAGER),
                ResolvedConfig("p2", Strategy.AFTER_PROMPT, defer_slot="b"),
                ResolvedConfig("p3", Strategy.LAZY, defer_slot="c"),
                ResolvedConfig("p4", Strategy.AFTER_PROMPT, defer_slot="0"),
            ]
            opts = EmitOptions(generated_at="2026-01-01T00:00:00Z")
            generate(configs, out, options=opts)
            content = out.read_text()
            self.assertTrue(content.startswith(HEADER_LINE))
            self.assertIn("znap source p1", content)
            self.assertIn("--stage=5", content)
            self.assertIn("--slot=b", content)
            self.assertIn("znap source p2", content)
            self.assertIn("--slot=c", content)
            self.assertIn("znap source p3", content)
            # Slot '0' must be omitted
            self.assertIn("znap source p4", content)
            self.assertNotIn("--slot=0", content)

    def test_local_clone_source_emission(self):
        with tempfile.TemporaryDirectory() as tmp:
            zh = Path(tmp) / ".ziro"
            pdir = zh / "plugins" / "myplugin"
            pdir.mkdir(parents=True)
            (pdir / "myplugin.plugin.zsh").write_text("# myplugin")

            out = Path(tmp) / "plugins.gen.zsh"
            configs = [
                ResolvedConfig("myplugin", Strategy.EAGER),
            ]
            opts = EmitOptions(generated_at="2026-01-01T00:00:00Z", ziro_home=zh)
            generate(configs, out, options=opts)
            content = out.read_text()
            self.assertIn("ziro local source $ZIRO_HOME/plugins/myplugin/myplugin.plugin.zsh", content)
            self.assertNotIn("znap source myplugin", content)

    def test_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            out1 = Path(tmp) / "a.zsh"
            out2 = Path(tmp) / "b.zsh"
            configs = [ResolvedConfig("p1", Strategy.EAGER)]
            ts = "2026-01-01T00:00:00Z"
            opts = EmitOptions(generated_at=ts)
            generate(configs, out1, options=opts)
            generate(configs, out2, options=opts)
            self.assertEqual(out1.read_text(), out2.read_text())

    def test_default_output_path(self):
        p = default_output_path(Path("/home/x/.config/ziro"))
        self.assertEqual(str(p), "/home/x/.config/ziro/derived/plugins.gen.zsh")


if __name__ == "__main__":
    unittest.main()
