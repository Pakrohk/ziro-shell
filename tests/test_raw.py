"""Tests for core.raw."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".ziro"))

from core.raw import RawSpec, validate_raw, emit_raw

import pytest
pytestmark = pytest.mark.unit


class TestValidate(unittest.TestCase):
 def test_valid_raw(self):
  ok, _ = validate_raw(RawSpec("p", "znap source p --deep"))
  self.assertTrue(ok)

 def test_empty_rejected(self):
  ok, reason = validate_raw(RawSpec("p", ""))
  self.assertFalse(ok)
  self.assertIn("empty", reason)

 def test_forbidden_curl(self):
  ok, reason = validate_raw(RawSpec("p", "curl http://evil"))
  self.assertFalse(ok)

 def test_forbidden_rm(self):
  ok, reason = validate_raw(RawSpec("p", "rm -rf / --no-preserve-root"))
  self.assertFalse(ok)


class TestEmit(unittest.TestCase):
 def test_emits_valid(self):
  out = emit_raw(RawSpec("p", "znap source p"))
  self.assertEqual(out, "znap source p")

 def test_emits_rejection_comment(self):
  out = emit_raw(RawSpec("p", "curl x"))
  self.assertIn("rejected", out)

 def test_emits_with_comment(self):
  out = emit_raw(RawSpec("p", "znap source p", comment="custom"))
  self.assertIn("# raw: custom", out)


if __name__ == "__main__":
 unittest.main()