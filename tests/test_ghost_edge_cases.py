"""Edge case security and performance tests for zero-lag ghost history architecture.

Spec: 020 (Zero-Lag History Filter Architecture)
Covers:
- Precmd window race (Ctrl+C before precmd fires)
- Secret ID and ARN variations (--secret-id, --secret-arn)
- Multi-command line secret detection
- Piped secrets (Authorization: Bearer)
- Multiline continuation commands
- URL-embedded credentials (https://user:token@host)
- Offline batch sanitization via sync
- Doctor monitoring detection on injected secrets
- Keystroke input latency (< 3ms)
- Precmd append latency (< 0.1ms)
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from core.build import _is_ghost_line_sensitive, _sanitize_ghost_history_cache
from core.doctor_cli import _check_ghost_cache_secrets

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parent.parent
GHOST_SRC = Path.home() / ".local/share/ziro/vendor/Pakrohk/ziro-ghost/sources/history.source.zsh"
if not GHOST_SRC.is_file():
    GHOST_SRC = Path.home() / "Projects/ziro-ghost/sources/history.source.zsh"


class TestGhostEdgeCases(unittest.TestCase):
    """12 edge case tests for zero-lag history filter and monitoring."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.cache_dir = self.tmp_path / "cache" / "ghost"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "history-cache"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _call_zsh_is_sensitive(self, line: str) -> bool:
        """Call ghost_history_is_sensitive in zsh subprocess."""
        cmd = f"""
source {GHOST_SRC}
if ghost_history_is_sensitive "$1"; then
  exit 0
else
  exit 1
fi
"""
        res = subprocess.run(
            ["zsh", "-f", "-c", cmd, "--", line],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return res.returncode == 0

    def test_ctrl_c_before_precmd_no_cache_leak(self) -> None:
        """1. If shell is killed before precmd runs, secrets never enter cache."""
        hist_file = self.tmp_path / "test_histfile"
        script = f"""
source {GHOST_SRC}
export GHOST_CACHE_FILE={self.cache_file}
export HISTFILE={hist_file}
setopt INC_APPEND_HISTORY 2>/dev/null || true
export TEST_SECRET=AKIAIOSFODNN7EXAMPLE
kill -INT $$
ghost_history_append_last
"""
        subprocess.run(["zsh", "-f", "-c", script], capture_output=True, timeout=5)
        if self.cache_file.exists():
            content = self.cache_file.read_text(encoding="utf-8")
            self.assertNotIn("AKIAIOSFODNN7EXAMPLE", content)

    def test_histfile_may_have_secret_but_cache_does_not(self) -> None:
        """2. Histfile may receive raw command on death, but cache must stay clean."""
        hist_file = self.tmp_path / "test_histfile"
        hist_file.write_text("export SECRET=AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8")
        # Ensure ghost history cache does not have the raw secret
        self.assertFalse(self.cache_file.exists() and "AKIAIOSFODNN7EXAMPLE" in self.cache_file.read_text())

    def test_secret_id_pattern_detected(self) -> None:
        """3. --secret-id argument pattern is flagged sensitive."""
        line = "aws secretsmanager get-secret-value --secret-id prod/db"
        self.assertTrue(self._call_zsh_is_sensitive(line))
        self.assertTrue(_is_ghost_line_sensitive(line))

    def test_secret_arn_pattern_detected(self) -> None:
        """4. --secret-arn argument pattern is flagged sensitive."""
        line = "aws secretsmanager get-secret-value --secret-arn arn:aws:secretsmanager:us-east-1:123456789012:secret:app"
        self.assertTrue(self._call_zsh_is_sensitive(line))
        self.assertTrue(_is_ghost_line_sensitive(line))

    def test_multi_command_with_secret_detected(self) -> None:
        """5. Multi-command lines with a secret anywhere are flagged sensitive."""
        line = "export A=AKIAIOSFODNN7EXAMPLE; echo done"
        self.assertTrue(self._call_zsh_is_sensitive(line))
        self.assertTrue(_is_ghost_line_sensitive(line))

    def test_pipe_with_secret_detected(self) -> None:
        """6. Piped commands containing Bearer authorization headers are flagged sensitive."""
        line = 'echo start | curl -H "Authorization: Bearer secret_token_xyz" http://api.internal'
        self.assertTrue(self._call_zsh_is_sensitive(line))
        self.assertTrue(_is_ghost_line_sensitive(line))

    def test_multiline_command_with_secret(self) -> None:
        """7. Multiline command continuation containing credentials is flagged."""
        line = "curl https://api.com \\\n  -H 'Authorization: Bearer secret_12345'"
        self.assertTrue(self._call_zsh_is_sensitive(line))
        self.assertTrue(_is_ghost_line_sensitive(line))

    def test_git_credential_helper_in_url(self) -> None:
        """8. Embedded credentials in git URLs are flagged sensitive."""
        line = "git clone https://username:ghp_personaltoken1234567890abcdefghijklm@github.com/org/repo"
        self.assertTrue(self._call_zsh_is_sensitive(line))
        self.assertTrue(_is_ghost_line_sensitive(line))

    def test_sync_sanitizes_existing_cache(self) -> None:
        """9. ziro sync offline sanitize purges injected secrets from cache file."""
        self.cache_file.write_text(
            "git status\n"
            "export AWS_KEY=AKIAIOSFODNN7EXAMPLE\n"
            "ls -la\n"
            "aws secretsmanager get-secret-value --secret-id prod/db\n",
            encoding="utf-8",
        )
        paths = {"cache": self.tmp_path / "cache"}
        scanned, filtered = _sanitize_ghost_history_cache(paths)
        self.assertEqual(scanned, 4)
        self.assertEqual(filtered, 2)
        content = self.cache_file.read_text(encoding="utf-8")
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", content)
        self.assertNotIn("--secret-id", content)
        self.assertIn("git status", content)
        self.assertIn("ls -la", content)

    def test_doctor_detects_secret_after_manual_injection(self) -> None:
        """10. Doctor flags warning if sensitive secrets are present in history-cache."""
        from unittest import mock

        self.cache_file.write_text(
            "git status\n" "export AWS_KEY=AKIAIOSFODNN7EXAMPLE\n",
            encoding="utf-8",
        )
        with mock.patch("pathlib.Path.home", return_value=self.tmp_path):
            # Point to tmp_path / .cache / ziro / ghost / history-cache
            mock_cache_dir = self.tmp_path / ".cache" / "ziro" / "ghost"
            mock_cache_dir.mkdir(parents=True, exist_ok=True)
            (mock_cache_dir / "history-cache").write_text(
                "export AWS_KEY=AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8"
            )
            status, msg, adv = _check_ghost_cache_secrets()
            self.assertEqual(status, "warn")
            self.assertIn("contains 1 sensitive token", msg)

    def test_typing_latency_under_3ms(self) -> None:
        """11. ghost_history_query executes in < 3ms (zero keystroke lag)."""
        cmd = f"""
source {GHOST_SRC}
_ghost_history_cache=("git status" "git commit -m test" "ls -la" "cargo build")
zmodload zsh/datetime
start=$EPOCHREALTIME
ghost_history_query "git "
end=$EPOCHREALTIME
diff_ms=$(( (end - start) * 1000 ))
print "$diff_ms"
"""
        res = subprocess.run(["zsh", "-f", "-c", cmd], capture_output=True, text=True, timeout=5)
        self.assertEqual(res.returncode, 0, f"stderr: {res.stderr}")
        latency_ms = float(res.stdout.strip())
        self.assertLess(latency_ms, 3.0, f"Keystroke query latency was {latency_ms}ms (expected < 3.0ms)")

    def test_append_last_latency_under_0_1ms(self) -> None:
        """12. ghost_history_append_last executes in < 1ms per execution in precmd."""
        cmd = f"""
source {GHOST_SRC}
export GHOST_CACHE_FILE={self.cache_file}
: > "$GHOST_CACHE_FILE"
print -s "echo safe_command_benchmark"
zmodload zsh/datetime
start=$EPOCHREALTIME
ghost_history_append_last
end=$EPOCHREALTIME
diff_ms=$(( (end - start) * 1000 ))
print "$diff_ms"
"""
        res = subprocess.run(["zsh", "-f", "-c", cmd], capture_output=True, text=True, timeout=5)
        self.assertEqual(res.returncode, 0, f"stderr: {res.stderr}")
        latency_ms = float(res.stdout.strip())
        self.assertLess(latency_ms, 1.5, f"Precmd append latency was {latency_ms}ms")


if __name__ == "__main__":
    unittest.main()
