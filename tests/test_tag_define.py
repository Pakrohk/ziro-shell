"""Tests for ziro tag define command (Spec 003 R6, Phase 6f).

Verifies creating user-defined tags, validation rules, collision detection,
and persistence in user.toml.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import tag_cli
from core.tags import load_user_tags

import pytest
pytestmark = pytest.mark.unit


class TestTagDefine(unittest.TestCase):
    def test_define_new_custom_tag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp)
            with mock.patch.dict("os.environ", {"ZIRO_CONFIG": str(cfg)}):
                rc = tag_cli.main(["define", "@fast", "--strategy=eager", "--priority=7", "--description=Fast tag"])
            self.assertEqual(rc, 0)

            user_tags = load_user_tags(cfg)
            self.assertIn("@fast", user_tags)
            self.assertEqual(user_tags["@fast"].strategy, "eager")
            self.assertEqual(user_tags["@fast"].priority, 7)
            self.assertEqual(user_tags["@fast"].description, "Fast tag")

    def test_define_duplicate_name_error_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp)
            with mock.patch.dict("os.environ", {"ZIRO_CONFIG": str(cfg)}):
                rc1 = tag_cli.main(["define", "@my-tag", "--strategy=eager"])
                self.assertEqual(rc1, 0)
                # Second define without --force
                rc2 = tag_cli.main(["define", "@my-tag", "--strategy=defer"])
                self.assertEqual(rc2, 1)

    def test_define_colliding_with_builtin_error_unless_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp)
            with mock.patch.dict("os.environ", {"ZIRO_CONFIG": str(cfg)}):
                # Collides with builtin @eager
                rc1 = tag_cli.main(["define", "@eager", "--strategy=defer"])
                self.assertEqual(rc1, 1)

                # With --force
                rc2 = tag_cli.main(["define", "@eager", "--strategy=defer", "--force"])
                self.assertEqual(rc2, 0)
                user_tags = load_user_tags(cfg)
                self.assertIn("@eager", user_tags)
                self.assertEqual(user_tags["@eager"].strategy, "defer")

    def test_define_invalid_strategy_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp)
            with mock.patch.dict("os.environ", {"ZIRO_CONFIG": str(cfg)}):
                rc = tag_cli.main(["define", "@broken", "--strategy=unknown_strat"])
            self.assertEqual(rc, 2)

    def test_define_priority_out_of_range_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp)
            with mock.patch.dict("os.environ", {"ZIRO_CONFIG": str(cfg)}):
                rc1 = tag_cli.main(["define", "@bad-prio", "--priority=999"])
                self.assertEqual(rc1, 2)
                rc2 = tag_cli.main(["define", "@bad-prio", "--priority=-5"])
                self.assertEqual(rc2, 2)

    def test_define_invalid_name_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp)
            with mock.patch.dict("os.environ", {"ZIRO_CONFIG": str(cfg)}):
                rc = tag_cli.main(["define", "@bad name with spaces!"])
            self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
