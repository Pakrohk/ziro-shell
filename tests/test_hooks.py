"""Tests for core.hooks."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".ziro"))

from core.hooks import (
    emit_re_registration,
    needs_re_registration,
    list_known_hooks,
)

import pytest
pytestmark = pytest.mark.unit


class TestKnownHooks(unittest.TestCase):
    def test_wd_needs_reregistration(self):
        self.assertTrue(needs_re_registration("wd"))

    def test_alias_tips_needs_reregistration(self):
        self.assertTrue(needs_re_registration("alias-tips"))

    def test_colored_man_pages_no_hooks(self):
        self.assertFalse(needs_re_registration("ohmyzsh-colored-man-pages"))

    def test_z_no_hooks(self):
        self.assertFalse(needs_re_registration("rupa/z"))

    def test_unknown_plugin_no_reregistration(self):
        self.assertFalse(needs_re_registration("random-plugin"))


class TestEmitReRegistration(unittest.TestCase):
    def test_emits_chpwd_for_wd(self):
        code = emit_re_registration("wd")
        self.assertIn("add-zsh-hook chpwd", code)
        self.assertIn("_wd_chpwd", code)

    def test_emits_preexec_for_alias_tips(self):
        code = emit_re_registration("alias-tips")
        self.assertIn("add-zsh-hook preexec", code)

    def test_empty_for_unknown(self):
        code = emit_re_registration("unknown")
        self.assertEqual(code, "")


if __name__ == "__main__":
    unittest.main()
