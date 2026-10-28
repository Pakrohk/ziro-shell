"""Tests for boot shim path baking and coherence."""

import unittest
from pathlib import Path

from core.build import render_boot_shim, write_boot_shim
from core.paths import get_paths


class TestBootShimPaths(unittest.TestCase):
    def test_render_boot_shim_bakes_paths(self):
        paths = {
            "home": Path("/custom/ziro/home"),
            "config": Path("/custom/ziro/config"),
            "data": Path("/custom/ziro/data"),
            "cache": Path("/custom/ziro/cache"),
        }
        shim = render_boot_shim(paths)
        self.assertIn('export ZIRO_HOME="/custom/ziro/home"', shim)
        self.assertIn('export ZIRO_CONFIG="/custom/ziro/config"', shim)
        self.assertIn('export ZIRO_DATA="/custom/ziro/data"', shim)
        self.assertIn('export ZIRO_CACHE="/custom/ziro/cache"', shim)
        self.assertIn('if [ ! -f "${ZIRO_CACHE}/ziro-boot.zsh.zwc" ]; then', shim)
        self.assertIn('source "${ZIRO_CACHE}/ziro-boot.zsh"', shim)

    def test_write_boot_shim_writes_expected_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            dest = tmp_path / "boot.zsh"
            custom_paths = {
                "home": tmp_path / "h",
                "config": tmp_path / "c",
                "data": tmp_path / "d",
                "cache": tmp_path / "cache",
            }
            result = write_boot_shim(dest, paths=custom_paths)
            self.assertEqual(result, dest)
            self.assertTrue(dest.is_file())
            content = dest.read_text(encoding="utf-8")
            self.assertIn(f'export ZIRO_HOME="{tmp_path}/h"', content)
            self.assertIn(f'export ZIRO_CACHE="{tmp_path}/cache"', content)


if __name__ == "__main__":
    unittest.main()
