"""Unit tests for ziro theme submit (Spec 017).

Hermetic tests: mocked gh CLI and git subprocess calls; no network or GitHub API access.
"""

from __future__ import annotations

import io
import os
import shutil
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from core import theme_submit_cli
from core.theme_submit_cli import diff_dicts, validate_theme_name


@pytest.fixture
def mock_starship_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Provide a valid customized starship.toml in an isolated directory."""
    conf = tmp_path / "starship.toml"
    conf.write_text(
        """
format = "$directory$git_branch$character"

[directory]
truncation_length = 4
truncate_to_repo = true

[character]
success_symbol = "[➜](bold green)"
error_symbol = "[✗](bold red)"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("STARSHIP_CONFIG", str(conf))
    return conf


def test_diff_dicts_helper():
    """Verify diff_dicts identifies added, modified, and removed keys."""
    curr = {"a": 1, "b": 2, "c": 3}
    base = {"b": 20, "c": 3, "d": 4}
    res = diff_dicts(curr, base)
    assert res["added"] == ["a"]
    assert res["modified"] == ["b"]
    assert res["removed"] == ["d"]


def test_diff_shows_additions():
    """Verify diff vs empty baseline identifies added sections."""
    curr = {"directory": {"truncation_length": 3}, "git_branch": {"symbol": "git"}}
    res = diff_dicts(curr, {})
    assert res["added"] == ["directory", "git_branch"]
    assert res["modified"] == []
    assert res["removed"] == []


def test_diff_shows_modifications():
    """Verify modifications when baseline contains different values."""
    curr = {"character": {"success_symbol": "ok"}}
    base = {"character": {"success_symbol": "yes"}}
    res = diff_dicts(curr, base)
    assert res["modified"] == ["character"]
    assert res["added"] == []


def test_valid_theme_name_passes():
    """Valid kebab-case names (3-30 chars, [a-z0-9-]) pass validation."""
    for name in ["my-theme", "my-awesome-theme", "abc", "theme-123", "a-1"]:
        ok, msg = validate_theme_name(name)
        assert ok, f"Expected {name} to be valid, got {msg}"
        assert msg == ""


def test_invalid_theme_name_rejected():
    """Invalid names (uppercase, spaces, length < 3 or > 30, symbols) are rejected."""
    cases = [
        ("ab", "at least 3 characters"),
        ("a" * 31, "at most 30 characters"),
        ("My-Theme", "must be kebab-case"),
        ("theme_1", "must be kebab-case"),
        ("theme 1", "must be kebab-case"),
        ("-start", "must not start or end with a hyphen"),
        ("end-", "must not start or end with a hyphen"),
        ("special$theme", "must be kebab-case"),
    ]
    for name, expected_err in cases:
        ok, msg = validate_theme_name(name)
        assert not ok, f"Expected {name} to be invalid"
        assert expected_err in msg


def test_missing_gh_cli_errors(mock_starship_config: Path, monkeypatch: pytest.MonkeyPatch):
    """AC2: Missing gh CLI in PATH returns exit code 1 with download advice."""
    monkeypatch.setattr(shutil, "which", lambda cmd: None if cmd == "gh" else "/bin/sh")

    buf_err = io.StringIO()
    with redirect_stderr(buf_err):
        rc = theme_submit_cli.main([])
    assert rc == 1
    assert "gh CLI not found" in buf_err.getvalue()
    assert "https://cli.github.com/" in buf_err.getvalue()


def test_missing_gh_auth_errors(mock_starship_config: Path, monkeypatch: pytest.MonkeyPatch):
    """AC3: Unauthenticated gh CLI returns exit code 1 with login advice."""
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/gh")

    def mock_run(cmd, *args, **kwargs):
        if cmd[:2] == ["gh", "auth"]:
            return MagicMock(returncode=1, stderr="You are not logged into any GitHub hosts")
        return MagicMock(returncode=0, stdout="")

    monkeypatch.setattr(theme_submit_cli.subprocess, "run", mock_run)

    buf_err = io.StringIO()
    with redirect_stderr(buf_err):
        rc = theme_submit_cli.main([])
    assert rc == 1
    assert "gh not authenticated" in buf_err.getvalue()
    assert "gh auth login" in buf_err.getvalue()


def test_missing_starship_config_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """AC4: Missing starship.toml returns exit code 1 with preset hint."""
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/gh")
    monkeypatch.setattr(
        theme_submit_cli.subprocess,
        "run",
        lambda cmd, *args, **kwargs: MagicMock(returncode=0, stdout=""),
    )
    non_existent = tmp_path / "missing_starship.toml"
    monkeypatch.setenv("STARSHIP_CONFIG", str(non_existent))

    buf_err = io.StringIO()
    with redirect_stderr(buf_err):
        rc = theme_submit_cli.main([])
    assert rc == 1
    assert "No starship config found" in buf_err.getvalue()
    assert "starship preset" in buf_err.getvalue()


def test_empty_config_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """AC5: Empty starship.toml returns exit code 2 indicating no customization."""
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/gh")
    monkeypatch.setattr(
        theme_submit_cli.subprocess,
        "run",
        lambda cmd, *args, **kwargs: MagicMock(returncode=0, stdout=""),
    )
    empty_conf = tmp_path / "empty_starship.toml"
    empty_conf.write_text("# Only comments\n", encoding="utf-8")
    monkeypatch.setenv("STARSHIP_CONFIG", str(empty_conf))

    buf_err = io.StringIO()
    with redirect_stderr(buf_err):
        rc = theme_submit_cli.main([])
    assert rc == 2
    assert "No customization detected" in buf_err.getvalue()


def test_dry_run_no_side_effects(mock_starship_config: Path, monkeypatch: pytest.MonkeyPatch):
    """AC7: --dry-run prints plan without creating branches, cloning, or opening PRs."""
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/gh")
    run_mock = MagicMock(returncode=0, stdout="Pakrohk\n")
    monkeypatch.setattr(
        theme_submit_cli.subprocess,
        "run",
        lambda cmd, *args, **kwargs: run_mock,
    )

    buf_out = io.StringIO()
    with redirect_stdout(buf_out):
        rc = theme_submit_cli.main(["--dry-run", "--name", "cool-theme"])
    out = buf_out.getvalue()

    assert rc == 0
    assert "Dry run: planned theme submission" in out
    assert "Theme name:    cool-theme" in out
    assert "Branch:        submit/Pakrohk/cool-theme" in out
    assert "PR Title:      Theme: cool-theme by @Pakrohk" in out
    assert "directory" in out
    assert "character" in out


def test_invalid_cli_theme_name(mock_starship_config: Path, monkeypatch: pytest.MonkeyPatch):
    """AC9: CLI rejects bad theme names passed via --name."""
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/gh")
    monkeypatch.setattr(
        theme_submit_cli.subprocess,
        "run",
        lambda cmd, *args, **kwargs: MagicMock(returncode=0, stdout="testuser"),
    )

    buf_err = io.StringIO()
    with redirect_stderr(buf_err):
        rc = theme_submit_cli.main(["--name", "INVALID_NAME"])
    assert rc == 2
    assert "must be kebab-case" in buf_err.getvalue()


def test_pr_creation_flow(mock_starship_config: Path, monkeypatch: pytest.MonkeyPatch):
    """AC10, AC11: Full automated PR flow executes git commands and gh pr create."""
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/gh")

    commands_executed: list[list[str]] = []

    def mock_run(cmd, *args, **kwargs):
        commands_executed.append(list(cmd))
        if cmd[:3] == ["gh", "api", "user"]:
            return MagicMock(returncode=0, stdout="alice\n")
        if cmd[:2] == ["gh", "auth"]:
            return MagicMock(returncode=0, stdout="ok")
        if cmd[:3] == ["gh", "repo", "clone"]:
            # Create dummy repo directory
            target_dir = Path(cmd[4])
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / ".git").mkdir(parents=True, exist_ok=True)
            return MagicMock(returncode=0, stdout="")
        if cmd[:3] == ["gh", "pr", "create"]:
            return MagicMock(returncode=0, stdout="https://github.com/Pakrohk/ziro-themes/pull/42\n")
        return MagicMock(returncode=0, stdout="")

    monkeypatch.setattr(theme_submit_cli.subprocess, "run", mock_run)

    buf_out = io.StringIO()
    with redirect_stdout(buf_out):
        rc = theme_submit_cli.main(["--name", "neon-stars"])

    assert rc == 0
    out = buf_out.getvalue()
    assert "Theme submitted successfully!" in out
    assert "https://github.com/Pakrohk/ziro-themes/pull/42" in out

    # Verify command sequence
    clones = [c for c in commands_executed if len(c) >= 3 and c[:3] == ["gh", "repo", "clone"]]
    assert len(clones) == 1
    pushes = [c for c in commands_executed if "push" in c]
    assert len(pushes) == 1
    assert "submit/alice/neon-stars" in pushes[0]
    prs = [c for c in commands_executed if len(c) >= 3 and c[:3] == ["gh", "pr", "create"]]
    assert len(prs) == 1
    assert "--base" in prs[0]
    assert "main" in prs[0]


def test_no_pr_flag_skips_pr_creation(mock_starship_config: Path, monkeypatch: pytest.MonkeyPatch):
    """AC12: --no-pr creates and pushes branch, but does not open a pull request."""
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/gh")

    commands_executed: list[list[str]] = []

    def mock_run(cmd, *args, **kwargs):
        commands_executed.append(list(cmd))
        if cmd[:3] == ["gh", "api", "user"]:
            return MagicMock(returncode=0, stdout="bob\n")
        if cmd[:3] == ["gh", "repo", "clone"]:
            target_dir = Path(cmd[4])
            target_dir.mkdir(parents=True, exist_ok=True)
            return MagicMock(returncode=0, stdout="")
        return MagicMock(returncode=0, stdout="")

    monkeypatch.setattr(theme_submit_cli.subprocess, "run", mock_run)

    buf_out = io.StringIO()
    with redirect_stdout(buf_out):
        rc = theme_submit_cli.main(["--name", "bob-custom", "--no-pr"])

    assert rc == 0
    assert "PR creation skipped (--no-pr)" in buf_out.getvalue()

    prs = [c for c in commands_executed if len(c) >= 3 and c[:3] == ["gh", "pr", "create"]]
    assert len(prs) == 0


def test_cleanup_on_failure(mock_starship_config: Path, monkeypatch: pytest.MonkeyPatch):
    """AC14: Temporary directory is cleaned up even if git push or clone fails."""
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/gh")

    temp_dirs_created: list[Path] = []

    def mock_run(cmd, *args, **kwargs):
        if cmd[:3] == ["gh", "api", "user"]:
            return MagicMock(returncode=0, stdout="carol\n")
        if cmd[:3] == ["gh", "repo", "clone"]:
            td = Path(cmd[4])
            td.mkdir(parents=True, exist_ok=True)
            temp_dirs_created.append(td)
            return MagicMock(returncode=0, stdout="")
        if "push" in cmd:
            # Simulate network or git push error
            return MagicMock(returncode=1, stderr="fatal: unable to access network")
        return MagicMock(returncode=0, stdout="")

    monkeypatch.setattr(theme_submit_cli.subprocess, "run", mock_run)

    buf_err = io.StringIO()
    with redirect_stderr(buf_err):
        rc = theme_submit_cli.main(["--name", "carol-theme"])

    assert rc == 3
    assert len(temp_dirs_created) == 1
    # Check directory was deleted in finally block
    assert not temp_dirs_created[0].exists()


def test_keep_flag_preserves_temp(mock_starship_config: Path, monkeypatch: pytest.MonkeyPatch):
    """AC13: --keep preserves workspace directory on disk."""
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/gh")

    temp_dirs_created: list[Path] = []

    def mock_run(cmd, *args, **kwargs):
        if cmd[:3] == ["gh", "api", "user"]:
            return MagicMock(returncode=0, stdout="dave\n")
        if cmd[:3] == ["gh", "repo", "clone"]:
            td = Path(cmd[4])
            td.mkdir(parents=True, exist_ok=True)
            temp_dirs_created.append(td)
            return MagicMock(returncode=0, stdout="")
        return MagicMock(returncode=0, stdout="")

    monkeypatch.setattr(theme_submit_cli.subprocess, "run", mock_run)

    buf_out = io.StringIO()
    with redirect_stdout(buf_out):
        rc = theme_submit_cli.main(["--name", "dave-theme", "--no-pr", "--keep"])

    assert rc == 0
    assert len(temp_dirs_created) == 1
    # Check directory was kept
    assert temp_dirs_created[0].exists()
    # Clean up after test
    shutil.rmtree(temp_dirs_created[0], ignore_errors=True)


def test_help_command():
    """AC1: Intercepts --help and displays usage documentation."""
    buf_out = io.StringIO()
    with redirect_stdout(buf_out):
        rc = theme_submit_cli.main(["--help"])
    assert rc == 0
    out = buf_out.getvalue()
    assert "ziro theme submit" in out
    assert "--name" in out
    assert "--dry-run" in out
