"""Tests for fuzzy command suggestions and unknown command handling (Spec 008 R2, Phase 6e).

Layer: 3 (CLI error handling tests)
Spec: 008 R2, SC-1
"""

from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.help_cli import cmd_help, suggest_similar

import pytest
pytestmark = pytest.mark.unit


class TestFuzzySuggest(unittest.TestCase):
    def test_suggest_instal(self) -> None:
        self.assertEqual(suggest_similar("instal"), "install")

    def test_suggest_docktor(self) -> None:
        self.assertEqual(suggest_similar("docktor"), "doctor")

    def test_suggest_plug(self) -> None:
        self.assertEqual(suggest_similar("plug"), "plugin")

    def test_suggest_theem(self) -> None:
        self.assertEqual(suggest_similar("theem"), "theme")

    def test_suggest_benc(self) -> None:
        self.assertEqual(suggest_similar("benc"), "bench")

    def test_suggest_unrecognized_returns_none(self) -> None:
        self.assertIsNone(suggest_similar("xyz"))
        self.assertIsNone(suggest_similar("qwertyuiop12345"))

    def test_cmd_help_with_typo_suggests_command(self) -> None:
        err_buf = io.StringIO()
        out_buf = io.StringIO()
        old_err = sys.stderr
        try:
            sys.stderr = err_buf
            with redirect_stdout(out_buf):
                rc = cmd_help(["instal"])
        finally:
            sys.stderr = old_err

        self.assertEqual(rc, 1)
        err = err_buf.getvalue()
        self.assertIn("unknown command or topic 'instal'", err)
        self.assertIn("Did you mean: ziro install?", err)
        self.assertIn("Run 'ziro help'", err)

    def test_cmd_help_with_docktor_suggests_doctor(self) -> None:
        err_buf = io.StringIO()
        out_buf = io.StringIO()
        old_err = sys.stderr
        try:
            sys.stderr = err_buf
            with redirect_stdout(out_buf):
                rc = cmd_help(["docktor"])
        finally:
            sys.stderr = old_err

        self.assertEqual(rc, 1)
        err = err_buf.getvalue()
        self.assertIn("unknown command or topic 'docktor'", err)
        self.assertIn("Did you mean: ziro doctor?", err)

    def test_cmd_help_with_xyz_no_suggestion(self) -> None:
        err_buf = io.StringIO()
        out_buf = io.StringIO()
        old_err = sys.stderr
        try:
            sys.stderr = err_buf
            with redirect_stdout(out_buf):
                rc = cmd_help(["xyz"])
        finally:
            sys.stderr = old_err

        self.assertEqual(rc, 1)
        err = err_buf.getvalue()
        self.assertIn("unknown command or topic 'xyz'", err)
        self.assertNotIn("Did you mean", err)
        self.assertIn("Run 'ziro help' to view all available commands.", err)


if __name__ == "__main__":
    unittest.main()
