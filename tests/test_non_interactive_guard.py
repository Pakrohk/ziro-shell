"""Tests for Spec 015 non-interactive guard (C1).

Validates that non-interactive shells (scripts, ssh, cron) do not initialize
prompt engines, themes, background workers, or interactive hooks, while
keeping the ziro CLI fully functional.
"""

from __future__ import annotations

import os
import subprocess
import unittest


class TestNonInteractiveGuard(unittest.TestCase):
    """Test suite for non-interactive execution gating (AC1-AC7)."""

    def test_ziro_version_works_in_non_interactive(self) -> None:
        """AC1: ziro --version executes cleanly in zsh -c."""
        res = subprocess.run(
            ["zsh", "-c", "source ~/.zshrc 2>/dev/null; ziro --version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(res.returncode, 0, f"stderr: {res.stderr}")
        self.assertIn("ziro-shell", res.stdout)

    def test_ziro_doctor_works_in_non_interactive(self) -> None:
        """AC2: ziro doctor executes cleanly and returns healthy in zsh -c."""
        res = subprocess.run(
            ["zsh", "-c", "source ~/.zshrc 2>/dev/null; ziro doctor"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(res.returncode, 0, f"stdout: {res.stdout}\nstderr: {res.stderr}")
        self.assertIn("HEALTHY", res.stdout)

    def test_non_interactive_startup_silent(self) -> None:
        """AC3: Sourcing ~/.zshrc in non-interactive produces zero output."""
        res = subprocess.run(
            ["zsh", "-c", "source ~/.zshrc"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(res.stdout, "")
        self.assertEqual(res.stderr, "")

    def test_starship_unset_in_non_interactive(self) -> None:
        """AC4: STARSHIP_SHELL is unset in non-interactive zsh."""
        env = os.environ.copy()
        env.pop("STARSHIP_SHELL", None)
        res = subprocess.run(
            ["zsh", "-c", 'source ~/.zshrc 2>/dev/null; echo "STARSHIP_SHELL=${STARSHIP_SHELL:-unset}"'],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("STARSHIP_SHELL=unset", res.stdout)

    def test_precmd_functions_empty_in_non_interactive(self) -> None:
        """AC5: precmd_functions is unset or has no prompt/defer hooks in non-interactive."""
        env = os.environ.copy()
        env.pop("STARSHIP_SHELL", None)
        res = subprocess.run(
            ["zsh", "-c", "source ~/.zshrc 2>/dev/null; typeset -p precmd_functions 2>&1 || true"],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        # Either no such variable or empty array without prompt/defer hooks
        output = res.stdout + res.stderr
        self.assertNotIn("prompt_starship_precmd", output)
        self.assertNotIn("_ziro_defer_core_dispatch_precmd", output)
        self.assertNotIn("_ziro_ghost_history_append", output)

    def test_starship_set_in_interactive(self) -> None:
        """AC6: STARSHIP_SHELL is set in interactive shell (zsh -ic)."""
        res = subprocess.run(
            ["zsh", "-ic", 'source ~/.zshrc 2>/dev/null; echo "STARSHIP_SHELL=$STARSHIP_SHELL"'],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("STARSHIP_SHELL=zsh", res.stdout)

    def test_precmd_functions_populated_in_interactive(self) -> None:
        """AC7: Interactive shell retains all standard precmd hooks."""
        res = subprocess.run(
            ["zsh", "-ic", "source ~/.zshrc 2>/dev/null; typeset -p precmd_functions"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("_ziro_defer_core_dispatch_precmd", res.stdout)
        self.assertIn("prompt_starship_precmd", res.stdout)


if __name__ == "__main__":
    unittest.main()
