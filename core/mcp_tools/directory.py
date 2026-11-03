"""Directory awareness and safety heuristics for AI agents.

Spec: 024 (R11)
"""

from __future__ import annotations

import os
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


def _is_protected_system_path(p: Path) -> bool:
    """Return True if path is a sensitive root system path outside user space."""
    resolved = p.resolve()
    protected_roots = [
        Path("/"),
        Path("/etc"),
        Path("/usr"),
        Path("/bin"),
        Path("/sbin"),
        Path("/lib"),
        Path("/lib64"),
        Path("/var"),
        Path("/boot"),
        Path("/root"),
        Path("/sys"),
        Path("/proc"),
        Path("/dev"),
    ]
    return resolved in protected_roots


def tool_dir_inspect(args: dict[str, Any]) -> dict[str, Any]:
    """Inspect directory semantics: git status, files, manifests, languages, permissions."""
    raw_path = args.get("path", ".")
    target = Path(raw_path).expanduser().resolve()

    if not target.exists():
        return {"error": f"Path '{target}' does not exist", "exists": False}

    if not target.is_dir():
        return {"error": f"Path '{target}' is a file, not a directory", "is_dir": False}

    if _is_protected_system_path(target):
        return {"error": f"Path '{target}' is a protected system directory", "protected": True}

    # Permissions
    readable = os.access(target, os.R_OK)
    writable = os.access(target, os.W_OK)
    executable = os.access(target, os.X_OK)

    # Manifests detection
    manifest_map = {
        "pyproject.toml": "python",
        "requirements.txt": "python",
        "package.json": "javascript/typescript",
        "Cargo.toml": "rust",
        "go.mod": "go",
        "Gemfile": "ruby",
        "composer.json": "php",
        "Makefile": "make",
        "Dockerfile": "docker",
    }
    found_manifests = [m for m in manifest_map if (target / m).is_file()]

    # Git repository detection
    is_git = False
    git_branch = None
    git_clean = True
    git_status_preview: list[str] = []

    try:
        git_check = subprocess.run(
            ["git", "-C", str(target), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if git_check.returncode == 0 and git_check.stdout.strip() == "true":
            is_git = True
            branch_proc = subprocess.run(
                ["git", "-C", str(target), "branch", "--show-current"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            git_branch = branch_proc.stdout.strip() or "HEAD"

            stat_proc = subprocess.run(
                ["git", "-C", str(target), "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            stat_lines = stat_proc.stdout.splitlines()
            if stat_lines:
                git_clean = False
                git_status_preview = [l[:80] for l in stat_lines[:10]]
    except Exception:
        pass

    # File counts and extension distribution
    file_count = 0
    dir_count = 0
    ext_counter: Counter[str] = Counter()

    try:
        for entry in os.scandir(target):
            if entry.is_file(follow_symlinks=False):
                file_count += 1
                suffix = Path(entry.name).suffix.lower()
                if suffix:
                    ext_counter[suffix] += 1
            elif entry.is_dir(follow_symlinks=False):
                dir_count += 1
    except PermissionError:
        pass

    top_extensions = [{"ext": ext, "count": count} for ext, count in ext_counter.most_common(5)]

    return {
        "path": str(target),
        "permissions": {"read": readable, "write": writable, "execute": executable},
        "is_git_repository": is_git,
        "git": {
            "branch": git_branch,
            "clean": git_clean,
            "uncommitted_files_sample": git_status_preview,
        }
        if is_git
        else None,
        "manifests": found_manifests,
        "immediate_entries": {"files": file_count, "directories": dir_count},
        "top_extensions": top_extensions,
    }


def tool_dir_types(args: dict[str, Any]) -> dict[str, Any]:
    """Classify directory semantics: project_root, build_dir, cache_dir, config_dir, temp_dir."""
    raw_path = args.get("path", ".")
    target = Path(raw_path).expanduser().resolve()

    if not target.exists():
        return {"error": "path does not exist"}

    name = target.name.lower()
    path_str = str(target)

    types = []
    if (target / ".git").exists():
        types.append("project_root")

    if any((target / m).is_file() for m in ("package.json", "pyproject.toml", "Cargo.toml", "go.mod")):
        if "project_root" not in types:
            types.append("project_root")

    if name in ("node_modules", "target", "build", "dist", ".tox", "__pycache__", ".pytest_cache", ".venv", "venv"):
        types.append("build_dir")

    if ".config" in path_str or name in ("config", "etc"):
        types.append("config_dir")

    if ".cache" in path_str or "cache" in name:
        types.append("cache_dir")

    if path_str.startswith("/tmp") or path_str.startswith("/var/tmp") or "temp" in name:
        types.append("temp_dir")

    if _is_protected_system_path(target):
        types.append("system_root")

    if not types:
        types.append("regular_directory")

    return {
        "path": str(target),
        "primary_type": types[0],
        "all_types": types,
    }


def tool_dir_safe_to_delete(args: dict[str, Any]) -> dict[str, Any]:
    """Assess whether a directory is safe for AI cleanup heuristics."""
    raw_path = args.get("path")
    if not raw_path:
        return {"error": "path parameter required"}

    target = Path(raw_path).expanduser().resolve()
    if not target.exists():
        return {"safe": True, "risk": "low", "reasons": ["path does not exist"]}

    reasons: list[str] = []
    risk = "low"
    safe = True

    path_str = str(target)
    home_str = str(Path.home())

    # System protection
    if _is_protected_system_path(target) or path_str in (home_str, "/"):
        return {
            "safe": False,
            "risk": "critical",
            "reasons": ["Protected root or user home directory; deletion blocked."],
        }

    # Secrets detection
    secret_patterns = (".env", "id_rsa", "id_ed25519", "*.key", "credentials")
    try:
        for p in secret_patterns:
            if list(target.glob(p)):
                safe = False
                risk = "critical"
                reasons.append(f"Directory contains secret credential files matching '{p}'")
                break
    except Exception:
        pass

    # Git uncommitted check
    if (target / ".git").is_dir():
        safe = False
        risk = "high"
        reasons.append("Directory is root of a git repository")
    else:
        try:
            r = subprocess.run(
                ["git", "-C", str(target), "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if r.returncode == 0 and r.stdout.strip():
                safe = False
                risk = "high"
                reasons.append("Directory contains uncommitted git modifications")
        except Exception:
            pass

    # Cache / Temp safe zones
    if path_str.startswith("/tmp") or path_str.startswith("/var/tmp"):
        reasons.append("Path is inside system temporary directory")
    elif ".cache" in path_str:
        reasons.append("Path is inside user cache directory")
    elif target.name in ("node_modules", "target", "__pycache__", ".pytest_cache"):
        reasons.append("Standard volatile build artifact directory")
    else:
        if safe:
            risk = "medium"
            reasons.append("Not inside a recognized volatile directory; verify contents before deletion")

    return {
        "path": str(target),
        "safe": safe,
        "risk": risk,
        "reasons": reasons,
    }
