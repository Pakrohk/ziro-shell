"""Tests for core.cache."""

import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".ziro"))

from core.cache import compute_source_hash, load_cached, store_cached, clear_cache
from core.models import AnalysisResult, DetectedSignals, Recommendation, Strategy

import pytest
pytestmark = pytest.mark.unit


class TestComputeHash(unittest.TestCase):
    def test_same_content_same_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "a.plugin.zsh").write_text("echo hi")
            h1 = compute_source_hash(p)
            h2 = compute_source_hash(p)
            self.assertEqual(h1, h2)

    def test_modified_content_different_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            f = p / "a.plugin.zsh"
            f.write_text("echo hi")
            h1 = compute_source_hash(p)
            time.sleep(1.1)  # ensure mtime differs
            f.write_text("echo bye")
            h2 = compute_source_hash(p)
            self.assertNotEqual(h1, h2)

    def test_empty_dir_has_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = compute_source_hash(Path(tmp))
            self.assertEqual(len(h), 64)  # sha256 hex


class TestCacheRoundtrip(unittest.TestCase):
    def test_store_and_load(self):
        result = AnalysisResult(
            plugin="test-plugin",
            source="/tmp/test",
            detected=DetectedSignals(compdef=True),
            recommended=Recommendation(strategy=Strategy.EAGER),
            confidence=0.5,
        )
        store_cached("test-plugin", "fakehash", result)
        loaded = load_cached("test-plugin", "fakehash")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.plugin, "test-plugin")
        self.assertTrue(loaded.detected.compdef)
        clear_cache("test-plugin")

    def test_hash_mismatch_returns_none(self):
        result = AnalysisResult.empty("test2", "/tmp")
        store_cached("test2", "hash1", result)
        self.assertIsNone(load_cached("test2", "hash2"))
        clear_cache("test2")


if __name__ == "__main__":
    unittest.main()
