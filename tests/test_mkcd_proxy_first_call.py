"""Tests for on-demand proxy first-call behavior: ziro-helpers (mkcd, take, extract, clipcopy, clippaste).

Validates Candidate A fix for Zsh FUNCTION_ARGZERO recursion bug (FUNCNEST).
Uses pytest tmp_path to avoid repo/install path pollution.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def _run_zsh(cmd: str) -> subprocess.CompletedProcess[str]:
    """Execute zsh with ~/.zshrc sourced in an isolated subshell.

    Explicitly sets ZIRO_HOME/ZIRO_CONFIG to real values to avoid
    env pollution from other pytest tests that override these vars.
    """
    import os
    env = dict(os.environ)
    env["ZIRO_HOME"] = os.path.expanduser("~/.ziro")
    env["ZIRO_CONFIG"] = os.path.expanduser("~/.config/ziro")
    env.pop("ZIRO_DATA", None)
    env.pop("ZIRO_CACHE", None)
    full_cmd = f"source ~/.zshrc 2>/dev/null; {cmd}"
    return subprocess.run(
        ["zsh", "-f", "-c", full_cmd],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )


def test_mkcd_first_call_creates_dir(tmp_path: Path):
    target = tmp_path / "test_mkcd_dir"
    res = _run_zsh(f"mkcd {target} && pwd")
    assert res.returncode == 0
    assert "maximum nested" not in res.stderr
    assert "FUNCNEST" not in res.stderr
    assert target.is_dir()
    assert str(target) in res.stdout


def test_take_first_call_creates_dir(tmp_path: Path):
    target = tmp_path / "test_take_dir"
    res = _run_zsh(f"take {target} && pwd")
    assert res.returncode == 0
    assert "maximum nested" not in res.stderr
    assert "FUNCNEST" not in res.stderr
    assert target.is_dir()
    assert str(target) in res.stdout


def test_extract_first_call(tmp_path: Path):
    sample_file = tmp_path / "sample.txt"
    sample_file.write_text("ziro extract test")
    archive = tmp_path / "archive.tar.gz"

    # Create archive
    subprocess.run(
        ["tar", "czf", str(archive), "-C", str(tmp_path), "sample.txt"],
        check=True,
    )
    sample_file.unlink()
    assert not sample_file.exists()

    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    res = _run_zsh(f"cd {dest_dir} && extract {archive}")
    assert res.returncode == 0
    assert "maximum nested" not in res.stderr
    assert "FUNCNEST" not in res.stderr
    assert (dest_dir / "sample.txt").is_file()


def test_clipcopy_and_clippaste_first_call():
    # Note: wl-copy forks to serve clipboard data; redirecting stdout/stderr avoids
    # holding python's capture pipe open.
    res = _run_zsh("echo 'ziro_clip_test' | clipcopy >/dev/null 2>&1; echo DONE")
    assert res.returncode == 0
    assert "DONE" in res.stdout
    assert "maximum nested" not in res.stderr
    assert "FUNCNEST" not in res.stderr

    res_paste = _run_zsh("clippaste")
    assert res_paste.returncode == 0
    assert "maximum nested" not in res_paste.stderr


def test_second_call_bypasses_proxy(tmp_path: Path):
    t1 = tmp_path / "first"
    t2 = tmp_path / "second"
    res = _run_zsh(f"mkcd {t1} && mkcd {t2} && pwd")
    assert res.returncode == 0
    assert "maximum nested" not in res.stderr
    assert str(t2) in res.stdout
