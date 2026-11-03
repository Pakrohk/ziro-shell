"""Tests for Ghost v2.0.1 integration in Ziro Shell.

Layer: 4 (Tests)
Spec: 024 (Phase 1, 2, 3, 10)
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from core.doctor_cli import run_checks
from core.ghost_fetch import get_platform_target, fetch_ghost_vendor, fetch_ghost_binary


def test_ghost_platform_target():
    target = get_platform_target()
    assert target is not None
    assert target in ("linux-x86_64", "linux-aarch64", "darwin-x86_64", "darwin-arm64")


def test_ghost_binary_presence():
    paths = [
        Path.home() / ".local" / "share" / "ziro" / "vendor" / "Pakrohk" / "ziro-ghost" / "bin" / "ghost-popup",
        Path.home() / ".local" / "bin" / "ghost-popup",
    ]
    binary_found = any(p.is_file() and os.access(p, os.X_OK) for p in paths)
    assert binary_found is True

    # Check version
    for p in paths:
        if p.is_file():
            res = subprocess.run([str(p), "--version"], capture_output=True, text=True, timeout=5)
            assert res.returncode == 0
            assert "ghost-popup 2.0.1" in res.stdout
            break


def test_ghost_vendor_version():
    vendor_git = Path.home() / ".local" / "share" / "ziro" / "vendor" / "Pakrohk" / "ziro-ghost"
    if vendor_git.is_dir() and (vendor_git / ".git").is_dir():
        res = subprocess.run(["git", "-C", str(vendor_git), "describe", "--tags"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            assert "v2.0.1" in res.stdout


def test_doctor_observes_ghost():
    checks = run_checks()
    assert "external tools" in checks
    status, msg, advice = checks["external tools"]
    assert "ghost" in msg


def test_tools_factory_ghost_entries():
    factory_path = Path(__file__).parent.parent / "core" / "tools_factory.toml"
    content = factory_path.read_text(encoding="utf-8")
    assert "ghost-v2-line" in content
    assert "ghost-v2-focus" in content

def test_ghost_preview_deprecation():
    proc = subprocess.run(["zsh", "-f", "-c", "source commands/ghost.zsh; _ziro_cmd_ghost preview"], capture_output=True, text=True, cwd=str(Path(__file__).parent.parent))
    assert "deprecated in v1.3.0" in proc.stderr
    assert proc.returncode == 0

def test_ghost_health_protocol_json():
    # Verify reading ghost health succeeds
    from core.external_tools import read_health
    h = read_health("ghost")
    assert h is not None
    assert "status" in h


def test_ghost_metrics_recording():
    from core.external_tools import read_metrics, aggregate
    m = read_metrics("ghost")
    agg = aggregate(m)
    assert "total" in agg
    assert "error_count" in agg

def test_ghost_mcp_suggest_tool():
    from core.mcp_tools.ghost import tool_ghost_suggest
    res = tool_ghost_suggest({"query": "git"})
    assert isinstance(res, dict)


def test_ghost_mcp_health_tool():
    from core.mcp_tools.ghost import tool_ghost_health
    res = tool_ghost_health({})
    assert isinstance(res, dict)
    assert res.get("status") in ("ok", "warn", "error") or "error" in res or "raw" in res
