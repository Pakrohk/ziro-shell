"""Tests for Spec 016 Ghost history cache secret filter (C2).

Validates that sensitive tokens, AWS keys, bearer headers, MySQL passwords,
private keys, space-prefixed commands, and long/high-entropy strings are
never written to the ghost history cache on disk.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestGhostFilter(unittest.TestCase):
    """Test suite for ziro-ghost secret filter (spec 016 R1-R4)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self.tmp.name) / "ghost"
        self.cache_file = self.cache_dir / "history-cache"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run_ghost_save(self, lines: list[str]) -> str:
        """Helper to run ghost_history_save in a subprocess with given cache entries."""
        lines_formatted = " ".join(f'"{l}"' for l in lines)
        cmd = f"""
source ~/.local/share/ziro/vendor/Pakrohk/ziro-ghost/sources/history.source.zsh
_ghost_history_cache=({lines_formatted})
ghost_history_save
"""
        env = os.environ.copy()
        env["GHOST_CACHE_FILE"] = str(self.cache_file)
        res = subprocess.run(
            ["zsh", "-f", "-c", cmd],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        self.assertEqual(res.returncode, 0, f"stderr: {res.stderr}")
        if self.cache_file.is_file():
            return self.cache_file.read_text(encoding="utf-8")
        return ""

    def test_aws_key_filtered(self) -> None:
        """AC1: AWS access key pattern AKIA... is filtered."""
        content = self._run_ghost_save(["export AWS_SECRET_ACCESS_KEY='AKIAIOSFODNN7EXAMPLE'"])
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", content)

    def test_github_token_filtered(self) -> None:
        """AC1: GitHub token pattern ghp_... is filtered."""
        content = self._run_ghost_save(["gh auth login --with-token ghp_1234567890abcdefghijklmnopqrstuvwxyz"])
        self.assertNotIn("ghp_1234567890", content)

    def test_bearer_header_filtered(self) -> None:
        """AC1: Authorization: Bearer header is filtered."""
        content = self._run_ghost_save(["curl -H 'Authorization: Bearer secret_bearer_token' http://example.com"])
        self.assertNotIn("secret_bearer_token", content)

    def test_mysql_password_filtered(self) -> None:
        """AC1: -p<pass> MySQL password pattern is filtered."""
        content = self._run_ghost_save(["mysql -u root -pMySecretPassword test"])
        self.assertNotIn("MySecretPassword", content)

    def test_passphrase_filtered(self) -> None:
        """AC1: passout/passin/passphrase pattern is filtered."""
        content = self._run_ghost_save(["openssl genrsa -passout pass:secret123"])
        self.assertNotIn("secret123", content)

    def test_openai_key_filtered(self) -> None:
        """R1: sk-... OpenAI API key pattern is filtered."""
        content = self._run_ghost_save(["curl -H 'Authorization: Bearer sk-ant-api03-1234567890abcdefghijkl'"])
        self.assertNotIn("sk-ant-api03", content)

    def test_private_key_header_filtered(self) -> None:
        """R1: BEGIN PRIVATE KEY block is filtered."""
        content = self._run_ghost_save(["-----BEGIN OPENSSH PRIVATE KEY-----"])
        self.assertNotIn("OPENSSH PRIVATE KEY", content)

    def test_space_prefix_filtered(self) -> None:
        """R2: Command starting with space is skipped (HIST_IGNORE_SPACE)."""
        content = self._run_ghost_save([" git log --all"])
        self.assertNotIn("git log --all", content)

    def test_long_line_filtered(self) -> None:
        """R3: Command line exceeding 500 characters is skipped."""
        long_line = "a" * 505
        content = self._run_ghost_save([long_line])
        self.assertNotIn(long_line, content)

    def test_base64_line_filtered(self) -> None:
        """R4: 40+ consecutive alphanumeric characters without space is skipped."""
        secret_blob = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        content = self._run_ghost_save([f"token={secret_blob}"])
        self.assertNotIn(secret_blob, content)

    def test_normal_command_preserved(self) -> None:
        """AC6: Standard development commands are preserved in history cache."""
        content = self._run_ghost_save(["git status", "ls -la", "cargo build --release"])
        self.assertIn("git status", content)
        self.assertIn("ls -la", content)
        self.assertIn("cargo build --release", content)


if __name__ == "__main__":
    unittest.main()
