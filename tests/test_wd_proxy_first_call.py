"""Tests for on-demand command-trigger proxies: wd and zoxide.

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


def test_wd_help_first_call():
    res = _run_zsh("wd help")
    assert res.returncode == 0
    assert "maximum nested" not in res.stderr
    assert "FUNCNEST" not in res.stderr
    assert "Usage: wd" in res.stdout


def test_wd_warp_cycle(tmp_path: Path):
    point = "ziro_test_warp"
    res = _run_zsh(f"cd {tmp_path} && wd add {point} && cd /tmp && wd {point} && pwd && wd rm {point}")
    assert res.returncode == 0
    assert "maximum nested" not in res.stderr
    assert "FUNCNEST" not in res.stderr
    assert str(tmp_path) in res.stdout


def test_zoxide_z_first_call(tmp_path: Path):
    res = _run_zsh(f"z {tmp_path} && pwd")
    assert res.returncode == 0
    assert "maximum nested" not in res.stderr
    assert "FUNCNEST" not in res.stderr
    assert str(tmp_path) in res.stdout


def test_wd_second_call_bypasses_proxy():
    res = _run_zsh("wd help >/dev/null && wd list >/dev/null && echo DONE")
    assert res.returncode == 0
    assert "maximum nested" not in res.stderr
    assert "DONE" in res.stdout
