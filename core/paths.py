"""ziro-shell — standard path resolution utilities.

Layer: 3 (Python core, cold-path only)
Spec: 009 Post-Integration Architecture
Permanent constraints: C17.1 (No unnecessary files), C17.2 (POSIX/Zsh standard), C17.3 (Zero redundant abstractions)
"""

from __future__ import annotations

import os
from pathlib import Path


def get_paths() -> dict[str, Path]:
    """Resolve standard Ziro filesystem paths."""
    home = Path(os.environ.get("ZIRO_HOME", Path.home() / ".ziro")).resolve()
    config = Path(
        os.environ.get(
            "ZIRO_CONFIG",
            Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "ziro",
        )
    ).resolve()
    data = Path(
        os.environ.get(
            "ZIRO_DATA",
            Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "ziro",
        )
    ).resolve()
    cache = Path(
        os.environ.get(
            "ZIRO_CACHE",
            Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "ziro",
        )
    ).resolve()
    return {
        "home": home,
        "config": config,
        "data": data,
        "cache": cache,
    }


def _ensure_secure_perms(path: Path) -> None:
    """Apply secure permissions (spec 018 R1).

    Directories get 700 (owner read/write/execute only).
    Files get 600 (owner read/write only).

    Idempotent — safe to call on already-secure paths.
    Silently no-ops on paths that don't exist (caller's responsibility).
    """
    if not path.exists():
        return
    try:
        if path.is_dir():
            path.chmod(0o700)
        elif path.is_file():
            path.chmod(0o600)
    except (PermissionError, OSError):
        # Non-fatal — e.g. on systems/mounts where chmod is restricted
        # The parent directory being 700 already blocks most access
        pass


__all__ = ["get_paths", "_ensure_secure_perms"]
