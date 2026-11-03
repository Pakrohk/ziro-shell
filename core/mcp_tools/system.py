"""System inventory tools for AI-safe inspection.

Spec: 024 (R10)
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from core.constants import VERSION


def tool_system_info(args: dict[str, Any]) -> dict[str, Any]:
    """Report operating system, architecture, Python, and Ziro versions."""
    path_entries = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    return {
        "os": sys.platform,
        "kernel": platform.release(),
        "arch": platform.machine(),
        "python": sys.version.split()[0],
        "ziro_version": VERSION,
        "shell": os.environ.get("SHELL", "unknown"),
        "path_summary": {
            "entry_count": len(path_entries),
            "common_paths": [p for p in path_entries if Path(p).is_dir()][:8],
        },
    }


def tool_system_packages(args: dict[str, Any]) -> dict[str, Any]:
    """Enumerate installed packages across discovered package managers (counts + sample)."""
    scan_all = bool(args.get("all", False))
    # Common managers (Q1 answer: common by default, all on flag)
    managers = ["pip", "uv", "npm", "cargo", "brew", "pacman", "apt"]
    if scan_all:
        managers.extend(["gem", "composer", "go", "yarn", "pnpm"])

    results = []

    for mgr in managers:
        bin_path = shutil.which(mgr)
        if not bin_path:
            continue

        sample_packages: list[str] = []
        total_count = 0

        try:
            cmd = []
            if mgr == "pip":
                cmd = [bin_path, "list", "--format=freeze"]
            elif mgr == "uv":
                cmd = [bin_path, "tool", "list"]
            elif mgr == "npm":
                cmd = [bin_path, "list", "-g", "--depth=0"]
            elif mgr == "cargo":
                cmd = [bin_path, "install", "--list"]
            elif mgr == "brew":
                cmd = [bin_path, "list", "--formula"]
            elif mgr == "pacman":
                cmd = [bin_path, "-Q"]
            elif mgr == "apt":
                cmd = [bin_path, "list", "--installed"]
            elif mgr in ("yarn", "pnpm"):
                cmd = [bin_path, "global", "list", "--depth=0"]
            elif mgr == "gem":
                cmd = [bin_path, "list"]

            if cmd:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if proc.returncode == 0:
                    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
                    total_count = len(lines)
                    sample_packages = [ln.split()[0].split("==")[0] for ln in lines[:10]]
        except Exception:
            pass

        results.append({
            "manager": mgr,
            "binary_path": bin_path,
            "estimated_packages": total_count,
            "sample": sample_packages,
        })

    return {"package_managers": results}


def tool_system_binaries(args: dict[str, Any]) -> dict[str, Any]:
    """Inspect resolved paths and versions of requested or standard developer binaries."""
    requested = args.get("commands")
    if not requested or not isinstance(requested, list):
        requested = [
            "python3",
            "uv",
            "node",
            "npm",
            "rustc",
            "cargo",
            "docker",
            "git",
            "gh",
            "ziro",
            "ghost-popup",
            "zsh",
            "curl",
        ]

    binaries = []
    for cmd in requested:
        bin_path = shutil.which(str(cmd))
        if not bin_path:
            # Check local bin fallback
            cand = Path.home() / ".local" / "bin" / str(cmd)
            if cand.is_file() and os.access(cand, os.X_OK):
                bin_path = str(cand)

        v_str = None
        if bin_path:
            try:
                proc = subprocess.run([bin_path, "--version"], capture_output=True, text=True, timeout=2)
                if proc.returncode == 0 and proc.stdout:
                    v_str = proc.stdout.strip().splitlines()[0]
                elif proc.stderr:
                    v_str = proc.stderr.strip().splitlines()[0]
            except Exception:
                pass

        binaries.append({
            "command": cmd,
            "found": bool(bin_path),
            "path": bin_path,
            "version": v_str,
        })

    return {"binaries": binaries}


def tool_system_env(args: dict[str, Any]) -> dict[str, Any]:
    """Return whitelisted non-sensitive environment variables (secrets redacted)."""
    allowed_prefixes = ("ZIRO_", "XDG_", "LC_")
    allowed_exact = {
        "PATH",
        "HOME",
        "USER",
        "SHELL",
        "TERM",
        "EDITOR",
        "VISUAL",
        "PAGER",
        "LANG",
    }
    forbidden_tokens = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASS", "AUTH", "CREDENTIAL", "PRIVATE")

    clean_env: dict[str, str] = {}
    for k, v in os.environ.items():
        k_upper = k.upper()
        if any(f in k_upper for f in forbidden_tokens):
            continue

        if k in allowed_exact or any(k.startswith(p) for p in allowed_prefixes):
            clean_env[k] = v

    return {"environment": clean_env}
