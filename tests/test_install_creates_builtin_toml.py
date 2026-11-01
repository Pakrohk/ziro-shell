"""Tests that install_cli ensures builtin.toml is created (Spec 003, Phase 6f).

Verifies Zero-Config compliance on fresh installations.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import install_cli
from core.tags import load_builtin_tags

import pytest


class TestInstallCreatesBuiltinToml(unittest.TestCase):
    @pytest.mark.integration
    def test_install_default_creates_builtin_toml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp)
            # Run install in isolated config
            with mock.patch.dict("os.environ", {"ZIRO_CONFIG": str(cfg)}):
                rc = install_cli.main(["--default"])
            self.assertEqual(rc, 0)

            builtin_file = cfg / "tags" / "builtin.toml"
            self.assertTrue(builtin_file.is_file())

            tags = load_builtin_tags(cfg)
            self.assertEqual(len(tags), 7)
            self.assertIn("@eager", tags)
            self.assertIn("@compdef", tags)

    @pytest.mark.integration
    def test_install_idempotent_does_not_overwrite_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp)
            tags_dir = cfg / "tags"
            tags_dir.mkdir(parents=True, exist_ok=True)
            custom_content = '[[tags]]\nname = "@modified"\nstrategy = "eager"\npriority = 99\n'
            (tags_dir / "builtin.toml").write_text(custom_content)

            with mock.patch.dict("os.environ", {"ZIRO_CONFIG": str(cfg)}):
                rc = install_cli.main(["--default"])
            self.assertEqual(rc, 0)

            # File should be unchanged
            self.assertEqual((tags_dir / "builtin.toml").read_text(), custom_content)

    @pytest.mark.unit
    def test_installed_builtin_content_matches_spec_003(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp)
            with mock.patch.dict("os.environ", {"ZIRO_CONFIG": str(cfg)}):
                install_cli.main(["--default"])

            tags = load_builtin_tags(cfg)
            expected_tags = {
                "@compdef": 15,
                "@eager": 10,
                "@no-compile": 8,
                "@eval-cache": 6,
                "@lazy": 5,
                "@after-prompt": 4,
                "@raw": 0,
            }
            for tag_name, priority in expected_tags.items():
                self.assertIn(tag_name, tags)
                self.assertEqual(tags[tag_name].priority, priority)


if __name__ == "__main__":
    unittest.main()
