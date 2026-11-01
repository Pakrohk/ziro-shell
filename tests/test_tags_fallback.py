"""Tests for builtin tag in-memory fallback mechanism (Spec 003, Phase 6f).

Ensures that an empty or uninitialized config directory safely falls back
to the 7 standard builtin tags without crashing.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.tags import BUILTIN_TAGS_DEFAULT, load_all_tags, load_builtin_tags

import pytest
pytestmark = pytest.mark.unit


class TestTagsFallback(unittest.TestCase):
    def test_empty_config_dir_returns_7_builtin_tags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp)
            tags = load_all_tags(cfg)
            self.assertEqual(len(tags), 7)
            self.assertIn("@eager", tags)
            self.assertIn("@compdef", tags)
            self.assertIn("@no-compile", tags)
            self.assertIn("@eval-cache", tags)
            self.assertIn("@lazy", tags)
            self.assertIn("@after-prompt", tags)
            self.assertIn("@raw", tags)

    def test_missing_builtin_toml_fallback_no_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp)
            tags = load_builtin_tags(cfg)
            self.assertEqual(len(tags), len(BUILTIN_TAGS_DEFAULT))
            self.assertEqual(tags["@eager"].priority, 10)
            self.assertEqual(tags["@compdef"].priority, 15)

    def test_corrupt_builtin_toml_fallback_used(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp)
            tags_dir = cfg / "tags"
            tags_dir.mkdir(parents=True, exist_ok=True)
            (tags_dir / "builtin.toml").write_text("THIS IS NOT VALID TOML [[[[[")

            tags = load_builtin_tags(cfg)
            self.assertEqual(len(tags), 7)
            self.assertIn("@eager", tags)

    def test_present_builtin_toml_reads_from_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp)
            tags_dir = cfg / "tags"
            tags_dir.mkdir(parents=True, exist_ok=True)
            (tags_dir / "builtin.toml").write_text(
                '[[tags]]\nname = "@custom-file"\nstrategy = "eager"\npriority = 42\n'
            )

            tags = load_builtin_tags(cfg)
            self.assertIn("@custom-file", tags)
            self.assertEqual(tags["@custom-file"].priority, 42)
            self.assertNotIn("@eager", tags)


if __name__ == "__main__":
    unittest.main()
