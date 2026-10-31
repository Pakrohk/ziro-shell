"""Tests for Spec 018: Universal Secure Permissions (C3).

Validates:
- _ensure_secure_perms helper in core/paths.py (0700 dir, 0600 file, idempotency, non-fatal)
- core/install_cli.py directory & file permissions
- core/plugin_pipeline.py vendor repository permissions
- core/build.py boot artifacts, eval-cache, and directory permissions
- core/doctor_cli.py legacy ghost cache warning and boot chain directory/zwc permission checks
"""

from __future__ import annotations

import os
import stat
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from core.paths import _ensure_secure_perms, get_paths
from core.doctor_cli import _check_boot_chain, _check_legacy_ghost_cache


def test_ensure_secure_perms_dir(tmp_path: Path) -> None:
    """Helper enforces 0700 on directories (R1)."""
    d = tmp_path / "test_dir"
    d.mkdir()
    d.chmod(0o755)
    assert stat.S_IMODE(d.stat().st_mode) == 0o755

    _ensure_secure_perms(d)
    assert stat.S_IMODE(d.stat().st_mode) == 0o700


def test_ensure_secure_perms_file(tmp_path: Path) -> None:
    """Helper enforces 0600 on files (R1)."""
    f = tmp_path / "test_file.txt"
    f.write_text("secret payload\n", encoding="utf-8")
    f.chmod(0o644)
    assert stat.S_IMODE(f.stat().st_mode) == 0o644

    _ensure_secure_perms(f)
    assert stat.S_IMODE(f.stat().st_mode) == 0o600


def test_ensure_secure_perms_idempotent(tmp_path: Path) -> None:
    """Helper is idempotent: safe to call repeatedly (R1)."""
    d = tmp_path / "idem_dir"
    d.mkdir()
    f = tmp_path / "idem_file.txt"
    f.write_text("data\n", encoding="utf-8")

    _ensure_secure_perms(d)
    _ensure_secure_perms(d)
    assert stat.S_IMODE(d.stat().st_mode) == 0o700

    _ensure_secure_perms(f)
    _ensure_secure_perms(f)
    assert stat.S_IMODE(f.stat().st_mode) == 0o600


def test_ensure_secure_perms_missing_path(tmp_path: Path) -> None:
    """Helper no-ops gracefully when target does not exist (R1)."""
    missing = tmp_path / "does_not_exist"
    # Should not raise any exception
    _ensure_secure_perms(missing)


def test_install_creates_700_config(tmp_path: Path) -> None:
    """install_cli writes config directory with 0700 and files with 0600 (R4)."""
    from core.install_cli import _write_defaults, _write_tools
    cfg = tmp_path / "config" / "ziro"

    _write_defaults(cfg)
    assert cfg.is_dir()
    assert stat.S_IMODE(cfg.stat().st_mode) == 0o700

    _write_tools(cfg)
    tools = cfg / "tools.toml"
    assert tools.is_file()
    assert stat.S_IMODE(tools.stat().st_mode) == 0o600


def test_install_creates_700_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cache directory creation ensures 0700 (R4, R5)."""
    from core.cache import cache_dir
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    c_dir = cache_dir()
    assert c_dir.is_dir()
    assert stat.S_IMODE(c_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(c_dir.parent.stat().st_mode) == 0o700


def test_install_creates_700_data(tmp_path: Path) -> None:
    """install_cli writes completion directory with 0700 and file with 0600 (R4)."""
    from core.install_cli import _write_completion
    data_dir = tmp_path / "data" / "ziro"

    comp_file = _write_completion(data_dir)
    assert comp_file.is_file()
    assert stat.S_IMODE(comp_file.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(comp_file.stat().st_mode) == 0o600


def test_plugin_add_creates_700_vendor(tmp_path: Path) -> None:
    """Plugin installation ensures vendor target directory is 0700 (R2)."""
    from core.plugin_pipeline import add_plugin

    ziro_home = tmp_path / "ziro_home"
    ziro_home.mkdir()
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Create dummy local plugin source
    src_plugin = tmp_path / "my_plugin"
    src_plugin.mkdir()
    (src_plugin / "my_plugin.plugin.zsh").write_text("# plugin code\n", encoding="utf-8")

    res = add_plugin(
        source=str(src_plugin),
        ziro_home=ziro_home,
        config_dir=config_dir,
        is_local=True,
    )
    assert res.plugin_dir.is_dir()
    assert stat.S_IMODE(res.plugin_dir.stat().st_mode) == 0o700


def test_build_creates_700_eval_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """build pipeline enforces 0700 on eval-cache directory (R3, R8)."""
    monkeypatch.setattr("core.build._validate_ziro_home", lambda p: None)
    home = tmp_path / "home"
    home.mkdir()
    (home / "ziro.zsh").write_text("# ziro main\n", encoding="utf-8")
    lib = home / "lib"
    lib.mkdir()
    (lib / "aliases.zsh").write_text("# aliases\n", encoding="utf-8")

    cfg = tmp_path / "config"
    cache = tmp_path / "cache"
    data = tmp_path / "data"

    monkeypatch.setenv("ZIRO_HOME", str(home))
    monkeypatch.setenv("ZIRO_CONFIG", str(cfg))
    monkeypatch.setenv("ZIRO_CACHE", str(cache))
    monkeypatch.setenv("ZIRO_DATA", str(data))

    from core.build import build
    ok, msg, _ = build()
    assert ok, f"build failed: {msg}"

    eval_cache = cache / "eval-cache"
    assert eval_cache.is_dir()
    assert stat.S_IMODE(eval_cache.stat().st_mode) == 0o700


def test_build_creates_600_zwc_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """build pipeline enforces 0600 on all .zwc files in eval-cache (R8, AC7)."""
    monkeypatch.setattr("core.build._validate_ziro_home", lambda p: None)
    home = tmp_path / "home"
    home.mkdir()
    (home / "ziro.zsh").write_text("# ziro main\n", encoding="utf-8")
    lib = home / "lib"
    lib.mkdir()
    (lib / "aliases.zsh").write_text("# aliases\n", encoding="utf-8")

    cfg = tmp_path / "config"
    cache = tmp_path / "cache"
    data = tmp_path / "data"

    monkeypatch.setenv("ZIRO_HOME", str(home))
    monkeypatch.setenv("ZIRO_CONFIG", str(cfg))
    monkeypatch.setenv("ZIRO_CACHE", str(cache))
    monkeypatch.setenv("ZIRO_DATA", str(data))

    eval_cache = cache / "eval-cache"
    eval_cache.mkdir(parents=True)
    # Simulate a generated .zwc artifact
    fake_zwc = eval_cache / "custom.zsh.zwc"
    fake_zwc.write_text("bytecode\n", encoding="utf-8")
    fake_zwc.chmod(0o644)

    from core.build import build
    ok, msg, _ = build()
    assert ok, f"build failed: {msg}"
    assert stat.S_IMODE(fake_zwc.stat().st_mode) == 0o600


def test_build_creates_600_boot_zwc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """build pipeline enforces 0600 on primary boot zwc artifact (R8, AC6)."""
    monkeypatch.setattr("core.build._validate_ziro_home", lambda p: None)
    home = tmp_path / "home"
    home.mkdir()
    (home / "ziro.zsh").write_text("# ziro main\n", encoding="utf-8")
    lib = home / "lib"
    lib.mkdir()
    (lib / "aliases.zsh").write_text("# aliases\n", encoding="utf-8")

    cfg = tmp_path / "config"
    cache = tmp_path / "cache"
    data = tmp_path / "data"

    monkeypatch.setenv("ZIRO_HOME", str(home))
    monkeypatch.setenv("ZIRO_CONFIG", str(cfg))
    monkeypatch.setenv("ZIRO_CACHE", str(cache))
    monkeypatch.setenv("ZIRO_DATA", str(data))

    from core.build import build
    ok, msg, _ = build()
    assert ok, f"build failed: {msg}"

    boot_zwc = cache / "ziro-boot.zsh.zwc"
    assert boot_zwc.is_file()
    assert stat.S_IMODE(boot_zwc.stat().st_mode) == 0o600


def test_build_creates_700_boot_parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """build pipeline enforces 0700 on cache directory holding boot artifacts (R8)."""
    monkeypatch.setattr("core.build._validate_ziro_home", lambda p: None)
    home = tmp_path / "home"
    home.mkdir()
    (home / "ziro.zsh").write_text("# ziro main\n", encoding="utf-8")
    lib = home / "lib"
    lib.mkdir()
    (lib / "aliases.zsh").write_text("# aliases\n", encoding="utf-8")

    cfg = tmp_path / "config"
    cache = tmp_path / "cache"
    data = tmp_path / "data"

    monkeypatch.setenv("ZIRO_HOME", str(home))
    monkeypatch.setenv("ZIRO_CONFIG", str(cfg))
    monkeypatch.setenv("ZIRO_CACHE", str(cache))
    monkeypatch.setenv("ZIRO_DATA", str(data))

    from core.build import build
    ok, msg, _ = build()
    assert ok, f"build failed: {msg}"

    assert stat.S_IMODE(cache.stat().st_mode) == 0o700


def test_doctor_detects_755_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Doctor check flags error if any core ziro directory is 0755 (R11, AC9)."""
    home = tmp_path / "home"
    home.mkdir()
    cfg = tmp_path / "config"
    cfg.mkdir()
    cache = tmp_path / "cache"
    cache.mkdir()
    data = tmp_path / "data"
    data.mkdir()

    monkeypatch.setenv("ZIRO_HOME", str(home))
    monkeypatch.setenv("ZIRO_CONFIG", str(cfg))
    monkeypatch.setenv("ZIRO_CACHE", str(cache))
    monkeypatch.setenv("ZIRO_DATA", str(data))

    # Create valid boot files
    (cfg / "load.toml").write_text("", encoding="utf-8")
    (cfg / "boot.zsh").write_text("", encoding="utf-8")
    boot_script = cache / "ziro-boot.zsh"
    boot_script.write_text("", encoding="utf-8")
    boot_zwc = cache / "ziro-boot.zsh.zwc"
    boot_zwc.write_text("", encoding="utf-8")
    boot_zwc.chmod(0o600)

    # Set all 700 except cfg which is 755
    home.chmod(0o700)
    cache.chmod(0o700)
    data.chmod(0o700)
    cfg.chmod(0o755)

    status, msg, advice = _check_boot_chain()
    assert status == "error"
    assert "core directory not 0700" in msg
    assert "config" in msg


def test_doctor_detects_644_boot_zwc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Doctor check flags error if ziro-boot.zsh.zwc is 0644 (R11, AC9)."""
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    cfg = tmp_path / "config"
    cfg.mkdir(mode=0o700)
    cache = tmp_path / "cache"
    cache.mkdir(mode=0o700)
    data = tmp_path / "data"
    data.mkdir(mode=0o700)

    monkeypatch.setenv("ZIRO_HOME", str(home))
    monkeypatch.setenv("ZIRO_CONFIG", str(cfg))
    monkeypatch.setenv("ZIRO_CACHE", str(cache))
    monkeypatch.setenv("ZIRO_DATA", str(data))

    (cfg / "load.toml").write_text("", encoding="utf-8")
    (cfg / "boot.zsh").write_text("", encoding="utf-8")
    boot_script = cache / "ziro-boot.zsh"
    boot_script.write_text("", encoding="utf-8")
    boot_zwc = cache / "ziro-boot.zsh.zwc"
    boot_zwc.write_text("", encoding="utf-8")
    boot_zwc.chmod(0o644)

    status, msg, advice = _check_boot_chain()
    assert status == "error"
    assert "ziro-boot.zsh.zwc is not 0600" in msg


def test_doctor_legacy_cache_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Doctor check warns if ghost history cache mtime predates v1.2.3 cutoff (R10, AC8)."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    ghost_dir = tmp_path / ".cache" / "ziro" / "ghost"
    ghost_dir.mkdir(parents=True)
    cache_file = ghost_dir / "history-cache"
    cache_file.write_text("old_history\n", encoding="utf-8")

    # Set mtime to 1700000000 (well before 1730246400 cutoff)
    os.utime(cache_file, (1700000000, 1700000000))

    status, msg, advice = _check_legacy_ghost_cache()
    assert status == "warn"
    assert "unfiltered secrets" in msg
    assert "rm ~/.cache/ziro/ghost/history-cache" in advice


def test_doctor_legacy_cache_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Doctor check passes if ghost history cache mtime post-dates v1.2.3 cutoff (R10, AC8)."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    ghost_dir = tmp_path / ".cache" / "ziro" / "ghost"
    ghost_dir.mkdir(parents=True)
    cache_file = ghost_dir / "history-cache"
    cache_file.write_text("new_history\n", encoding="utf-8")

    # Set mtime to current timestamp (> 1730246400)
    current_ts = time.time()
    os.utime(cache_file, (current_ts, current_ts))

    status, msg, advice = _check_legacy_ghost_cache()
    assert status == "ok"
    assert "post-dates v1.2.3 filter" in msg
