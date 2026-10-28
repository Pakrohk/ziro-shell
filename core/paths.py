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


__all__ = ["get_paths"]
