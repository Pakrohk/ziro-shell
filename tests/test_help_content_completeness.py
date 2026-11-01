"""Tests for help content completeness (Spec 008 R7, Phase 6b).

Verifies that every command and subcommand has complete, non-empty,
and well-formed help documentation in HELP_REGISTRY.
"""

from __future__ import annotations

import unittest

from core.help_cli import HELP_REGISTRY, get_entry, render_entry

import pytest
pytestmark = pytest.mark.unit

TOP_LEVEL_COMMANDS = [
    "install",
    "plugin",
    "tag",
    "suggest",
    "theme",
    "prompt",
    "config",
    "doctor",
    "bench",
    "completion",
    "help",
]

NAMESPACES = [
    "plugin",
    "tag",
    "suggest",
    "theme",
    "prompt",
    "config",
]


class TestHelpContentCompleteness(unittest.TestCase):
    def test_all_top_level_commands_registered(self) -> None:
        for cmd in TOP_LEVEL_COMMANDS:
            self.assertIn(cmd, HELP_REGISTRY, f"Missing top-level command in HELP_REGISTRY: {cmd}")
            entry = HELP_REGISTRY[cmd]
            self.assertEqual(entry.name, cmd)

    def test_all_namespaces_list_subcommands(self) -> None:
        for ns in NAMESPACES:
            entry = HELP_REGISTRY[ns]
            self.assertTrue(bool(entry.subcommands), f"Namespace '{ns}' has no subcommands listed")
            for sub, desc in entry.subcommands.items():
                self.assertTrue(bool(desc), f"Subcommand '{sub}' in namespace '{ns}' has empty description")

    def test_all_subcommands_have_dedicated_entries(self) -> None:
        for ns in NAMESPACES:
            entry = HELP_REGISTRY[ns]
            for sub in entry.subcommands:
                full_name = f"{ns} {sub}"
                sub_entry = get_entry(full_name)
                self.assertIsNotNone(sub_entry, f"Missing dedicated entry for subcommand: {full_name}")
                assert sub_entry is not None
                self.assertTrue(bool(sub_entry.summary), f"Subcommand {full_name} has empty summary")
                self.assertTrue(bool(sub_entry.usage), f"Subcommand {full_name} has empty usage")
                self.assertTrue(len(sub_entry.examples) >= 1, f"Subcommand {full_name} has no examples")

    def test_no_entry_has_empty_summary_or_usage(self) -> None:
        for name, entry in HELP_REGISTRY.items():
            self.assertTrue(bool(entry.summary.strip()), f"Entry '{name}' has empty summary")
            self.assertTrue(bool(entry.usage.strip()), f"Entry '{name}' has empty usage")
            self.assertTrue(entry.usage.startswith("ziro "), f"Entry '{name}' usage does not start with 'ziro ': {entry.usage}")

    def test_all_entries_have_at_least_one_example(self) -> None:
        for name, entry in HELP_REGISTRY.items():
            self.assertGreaterEqual(len(entry.examples), 1, f"Entry '{name}' has no examples")
            for ex in entry.examples:
                self.assertTrue(ex.startswith("ziro "), f"Entry '{name}' example does not start with 'ziro ': {ex}")

    def test_rendered_output_structure_consistency(self) -> None:
        # Check a command with flags, subcommands, examples, related
        entry = HELP_REGISTRY["tag define"]
        rendered = render_entry(entry)
        self.assertIn("ziro tag define — ", rendered)
        self.assertIn("Usage:\n  ziro tag define", rendered)
        self.assertIn("Flags:", rendered)
        self.assertIn("--strategy", rendered)
        self.assertIn("--priority", rendered)
        self.assertIn("Examples:\n  ziro tag define", rendered)
        self.assertIn("Related:", rendered)


if __name__ == "__main__":
    unittest.main()
