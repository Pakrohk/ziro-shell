"""Unit tests for core/help_cli.py.

Layer: 3 (Python CLI tests)
Spec: 008 R1, R2, R7, R10
"""

from __future__ import annotations

import io
import sys
import unittest

from core.help_cli import (
    HELP_REGISTRY,
    HelpEntry,
    cmd_help,
    get_entry,
    handle_help_if_requested,
    list_all,
    render_entry,
    suggest_similar,
)

import pytest
pytestmark = pytest.mark.unit


class TestHelpCli(unittest.TestCase):
    def test_cmd_help_empty_prints_all(self) -> None:
        buf = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = buf
            rc = cmd_help([])
        finally:
            sys.stdout = old_stdout

        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("ziro — fast, layered Zsh runtime customization", out)
        self.assertIn("install", out)
        self.assertIn("plugin", out)
        self.assertIn("tag", out)

    def test_cmd_help_install(self) -> None:
        buf = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = buf
            rc = cmd_help(["install"])
        finally:
            sys.stdout = old_stdout

        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("ziro install", out)
        self.assertIn("Usage:", out)
        self.assertIn("--default", out)

    def test_cmd_help_plugin_namespace(self) -> None:
        buf = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = buf
            rc = cmd_help(["plugin"])
        finally:
            sys.stdout = old_stdout

        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("ziro plugin", out)
        self.assertIn("Subcommands:", out)
        self.assertIn("add", out)
        self.assertIn("remove", out)

    def test_cmd_help_plugin_subcommand(self) -> None:
        buf = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = buf
            rc = cmd_help(["plugin", "add"])
        finally:
            sys.stdout = old_stdout

        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("ziro plugin add", out)
        self.assertIn("Usage:", out)

    def test_cmd_help_subcommand_fallback(self) -> None:
        buf = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = buf
            rc = cmd_help(["plugin", "customsub"])
        finally:
            sys.stdout = old_stdout

        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("ziro plugin", out)

    def test_cmd_help_nonexistent(self) -> None:
        buf = io.StringIO()
        err_buf = io.StringIO()
        old_stdout, old_stderr = sys.stdout, sys.stderr
        try:
            sys.stdout = buf
            sys.stderr = err_buf
            rc = cmd_help(["nonexistentcommand"])
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        self.assertEqual(rc, 1)
        err = err_buf.getvalue()
        self.assertIn("unknown command or topic 'nonexistentcommand'", err)

    def test_get_entry_existing(self) -> None:
        entry = get_entry("install")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertIsInstance(entry, HelpEntry)
        self.assertEqual(entry.name, "install")

    def test_get_entry_nonexistent(self) -> None:
        entry = get_entry("totally_bogus_xyz")
        self.assertIsNone(entry)

    def test_suggest_similar_typo(self) -> None:
        match = suggest_similar("instal")
        self.assertEqual(match, "install")

        match_doc = suggest_similar("docter")
        self.assertEqual(match_doc, "doctor")

    def test_handle_help_if_requested(self) -> None:
        buf = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = buf
            rc = handle_help_if_requested(["--help"], "install")
        finally:
            sys.stdout = old_stdout

        self.assertEqual(rc, 0)
        self.assertIn("ziro install", buf.getvalue())

        # No help requested
        rc_none = handle_help_if_requested(["--default"], "install")
        self.assertIsNone(rc_none)

    def test_colorization_respects_flag_and_tty(self) -> None:
        entry = get_entry("install")
        assert entry is not None

        plain = render_entry(entry, colorize=False)
        self.assertNotIn("\033[", plain)
        self.assertIn("ziro install", plain)

        colored = render_entry(entry, colorize=True)
        self.assertIn("\033[", colored)
        self.assertIn("ziro install", colored)

        plain_all = list_all(colorize=False)
        self.assertNotIn("\033[", plain_all)

        colored_all = list_all(colorize=True)
        self.assertIn("\033[", colored_all)

    def test_i18n_stub_returns_default(self) -> None:
        from core.help_cli import t
        self.assertEqual(t("some.key", "Default English Text"), "Default English Text")


if __name__ == "__main__":
    unittest.main()
