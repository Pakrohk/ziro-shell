"""Tests for core/update_cli.py orchestration, flags, and regressions."""
from __future__ import annotations

import io
import os
import subprocess
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest
from core import update_cli

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Ensure clean test environment pointing to valid repo and config."""
    monkeypatch.setenv("ZIRO_HOME", str(REPO_ROOT))
    real_config = Path.home() / ".config" / "ziro"
    if real_config.exists():
        monkeypatch.setenv("ZIRO_CONFIG", str(real_config))


def test_empty_argv_regression():
    """Verify empty argv does not fall back to sys.argv ('update')."""
    buf_err = io.StringIO()
    with redirect_stderr(buf_err):
        # Even if working tree is dirty, return code must be 0 or 1 (guard hit), NOT 2 ('unrecognized option update')
        rc = update_cli.main([])
    err = buf_err.getvalue()
    assert "unrecognized option" not in err
    assert rc in (0, 1)


def test_update_check_flag(tmp_path: Path, monkeypatch):
    """Test --check flag returns 0 and produces check status."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True)
    monkeypatch.setenv("ZIRO_CACHE", str(cache_dir))

    buf_out = io.StringIO()
    with redirect_stdout(buf_out):
        rc = update_cli.cmd_update(["--check"])
    assert rc == 0
    assert "Ziro Shell" in buf_out.getvalue() or "Update available" in buf_out.getvalue()


def test_update_dry_run_flag(tmp_path: Path, monkeypatch):
    """Test --dry-run returns 0 and displays orchestration plan without changes."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True)
    monkeypatch.setenv("ZIRO_CACHE", str(cache_dir))

    buf_out = io.StringIO()
    with redirect_stdout(buf_out):
        rc = update_cli.cmd_update(["--dry-run"])
    out = buf_out.getvalue()
    assert rc == 0
    assert "ziro update plan (dry-run):" in out
    assert "Dry-run complete" in out


def test_update_force_flag_bypasses_dirty_guard():
    """Test --force bypasses uncommitted changes guard and executes orchestration."""
    buf_out = io.StringIO()
    with redirect_stdout(buf_out):
        rc = update_cli.cmd_update(["--force", "--dry-run"])
    assert rc == 0
    assert "dry-run" in buf_out.getvalue()


def test_update_sync_only_flag():
    """Test --sync-only compiles boot artifacts directly."""
    buf_out = io.StringIO()
    with redirect_stdout(buf_out):
        rc = update_cli.cmd_update(["--sync-only"])
    out = buf_out.getvalue()
    assert rc == 0
    assert "Synced:" in out


def test_update_plugins_only_flag(tmp_path: Path):
    """Test --plugins-only flag ignores ziro repository dirty check."""
    buf_out = io.StringIO()
    with redirect_stdout(buf_out):
        rc = update_cli.cmd_update(["--plugins-only", "-y", "--dry-run"])
    assert rc == 0


def test_update_plugin_filter_flag():
    """Test --plugin flag filters target plugin."""
    buf_out = io.StringIO()
    with redirect_stdout(buf_out):
        rc = update_cli.cmd_update(["--dry-run", "--plugin", "wd"])
    out = buf_out.getvalue()
    assert rc == 0
    assert "wd" in out


def test_update_plugin_missing_arg():
    """Test --plugin missing arg returns 2."""
    buf_err = io.StringIO()
    with redirect_stderr(buf_err):
        rc = update_cli.cmd_update(["--plugin"])
    assert rc == 2
    assert "--plugin requires an argument" in buf_err.getvalue()


def test_update_no_analyze_flag():
    """Test --no-analyze parses cleanly."""
    buf_out = io.StringIO()
    with redirect_stdout(buf_out):
        rc = update_cli.cmd_update(["--dry-run", "--no-analyze"])
    assert rc == 0


def test_update_unrecognized_option():
    """Test invalid option returns 2."""
    buf_err = io.StringIO()
    with redirect_stderr(buf_err):
        rc = update_cli.cmd_update(["--invalid-flag-xyz"])
    assert rc == 2
    assert "unrecognized option '--invalid-flag-xyz'" in buf_err.getvalue()


def test_find_vendor_plugins_discovery():
    """Test find_vendor_plugins returns discovered repos."""
    plugins = update_cli.find_vendor_plugins()
    assert isinstance(plugins, list)
    # Should find at least one installed plugin
    if plugins:
        name, path = plugins[0]
        assert isinstance(name, str)
        assert isinstance(path, Path)


def test_ziro_defer_excluded_from_vendor_plugins():
    """T3: Verify ziro-defer and znap are excluded from vendor plugins."""
    plugins = update_cli.find_vendor_plugins()
    plugin_names = [name for name, _ in plugins]
    assert "ziro-defer" not in plugin_names
    assert "znap" not in plugin_names


def test_update_dev_flag_bypasses_dirty_guard(monkeypatch):
    """T4: Test --dev flag bypasses uncommitted changes guard with warning."""
    buf_err = io.StringIO()
    buf_out = io.StringIO()
    with redirect_stderr(buf_err), redirect_stdout(buf_out):
        rc = update_cli.cmd_update(["--dev", "--dry-run"])
    assert rc == 0
    # Also verify help shows --dev
    from core.help_cli import get_entry, render_entry
    entry = get_entry("update")
    assert entry is not None
    help_text = render_entry(entry)
    assert "--dev" in help_text


def test_sync_missing_core_tools(tmp_path: Path):
    """Verify _sync_missing_core_tools appends essential core tools to older load.toml."""
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir(parents=True)
    load_toml = cfg_dir / "load.toml"
    load_toml.write_text(
        """[meta]
schema_version = "1.0.0"

[[tool]]
name = "my-custom-plugin"
timing = "eager"
""",
        encoding="utf-8",
    )

    added = update_cli._sync_missing_core_tools(cfg_dir)
    assert "ziro-aliases-core" in added
    assert "ziro-keybindings" in added
    assert "ziro-helpers" in added
    assert "ziro-aliases" in added

    # Verify content
    content = load_toml.read_text(encoding="utf-8")
    assert "ziro-aliases-core" in content
    assert "my-custom-plugin" in content

    # Second run should add nothing
    added_second = update_cli._sync_missing_core_tools(cfg_dir)
    assert added_second == []


def test_update_self_repository_not_git(tmp_path: Path):
    """Verify update_self_repository returns error on non-git directory."""
    non_git = tmp_path / "not_git"
    non_git.mkdir()
    rc, msg, updated = update_cli.update_self_repository(repo_dir=non_git)
    assert rc == 1
    assert "not a git repository" in msg
    assert updated is False


def test_update_self_repository_dirty_guard(tmp_path: Path):
    """Verify update_self_repository respects dirty working tree unless force=True."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@test.com"], check=True)

    f = repo / "tracked.txt"
    f.write_text("initial\n")
    subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"], check=True)

    # Dirty modification
    f.write_text("modified\n")

    rc, msg, updated = update_cli.update_self_repository(repo_dir=repo, force=False)
    assert rc == 1
    assert "uncommitted tracked changes" in msg
    assert updated is False


def test_update_self_repository_pulls_when_behind(tmp_path: Path):
    """Verify update_self_repository actively pulls upstream commits and returns updated=True."""
    origin = tmp_path / "origin.git"
    origin.mkdir()
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)

    # Initial clone to populate origin
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True)
    subprocess.run(["git", "-C", str(work), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(work), "config", "user.email", "test@test.com"], check=True)
    (work / "file.txt").write_text("v1\n")
    subprocess.run(["git", "-C", str(work), "add", "file.txt"], check=True)
    subprocess.run(["git", "-C", str(work), "commit", "-q", "-m", "v1"], check=True)
    subprocess.run(["git", "-C", str(work), "push", "-q", "origin", "main"], check=True)

    # User clone at v1
    client = tmp_path / "client"
    subprocess.run(["git", "clone", "-q", str(origin), str(client)], check=True)
    subprocess.run(["git", "-C", str(client), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(client), "config", "user.email", "test@test.com"], check=True)

    # Add commit to upstream
    (work / "file.txt").write_text("v2\n")
    subprocess.run(["git", "-C", str(work), "commit", "-q", "-a", "-m", "v2"], check=True)
    subprocess.run(["git", "-C", str(work), "push", "-q", "origin", "main"], check=True)

    # Client runs update_self_repository
    rc, msg, updated = update_cli.update_self_repository(repo_dir=client, force=False)
    assert rc == 0
    assert updated is True
    assert "Updated Ziro Shell repository" in msg
    assert (client / "file.txt").read_text() == "v2\n"

    # Running again should report up to date
    rc2, msg2, updated2 = update_cli.update_self_repository(repo_dir=client, force=False)
    assert rc2 == 0
    assert updated2 is False
    assert "up to date" in msg2
