"""Tests for async analyzer (Phase 2b)."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".ziro"))

from core.analyzer import analyze_many, analyze_with_cache

import pytest
pytestmark = pytest.mark.unit


class TestAnalyzeMany(unittest.TestCase):
    def test_parallel_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugins = []
            for i in range(5):
                d = Path(tmp) / f"plugin{i}"
                d.mkdir()
                (d / f"plugin{i}.plugin.zsh").write_text(f"# plugin {i}\n")
                plugins.append((d, f"plugin{i}"))

            results = analyze_many(plugins)
            self.assertEqual(len(results), 5)
            for i, r in enumerate(results):
                self.assertEqual(r.plugin, f"plugin{i}")

    def test_analyze_with_cache_populates_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "cachetest"
            d.mkdir()
            (d / "cachetest.plugin.zsh").write_text("compdef _ct ct")

            r1 = analyze_with_cache(d, "cachetest")
            r2 = analyze_with_cache(d, "cachetest")

            self.assertEqual(r1.plugin, r2.plugin)
            self.assertTrue(r1.detected.compdef)


if __name__ == "__main__":
    unittest.main()
