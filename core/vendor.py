"""ziro-shell — vendor tools bootstrapper.

Layer: 3 (Python core)
Spec: 008, 009
Ensures all tools with external sources declared in load.toml are cloned to $ZIRO_DATA/vendor.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from core.paths import get_paths


def get_vendor_repos(manifest: dict[str, Any]) -> dict[str, str]:
    """Extract map of {source_slug: git_url} from manifest tools."""
    repos: dict[str, str] = {}
    for tool in manifest.get("tool", []):
        src = tool.get("source")
        if src and "/" in src and not src.startswith("$") and not src.startswith("~") and not src.startswith("/"):
            url = f"https://github.com/{src}.git"
            repos[src] = url
    return repos


def _clone_single_vendor(source: str, url: str, dest: Path) -> tuple[str, bool, str]:
    """Clone a single vendor repo using shallow git clone."""
    if dest.is_dir() and ((dest / ".git").is_dir() or any(dest.iterdir())):
        return source, True, "already present"

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_dest = dest.parent / f".tmp_{dest.name}_{os.getpid()}"
    try:
        if tmp_dest.is_dir():
            shutil.rmtree(tmp_dest, ignore_errors=True)
        r = subprocess.run(
            ["git", "clone", "--depth", "1", url, str(tmp_dest)],
            capture_output=True,
            text=True,
            timeout=90,
        )
        if r.returncode == 0:
            if dest.is_dir():
                shutil.rmtree(dest, ignore_errors=True)
            tmp_dest.rename(dest)
            return source, True, "cloned"
        else:
            return source, False, r.stderr.strip() or "git clone failed"
    except Exception as e:
        return source, False, str(e)
    finally:
        if tmp_dest.is_dir():
            shutil.rmtree(tmp_dest, ignore_errors=True)


def ensure_vendor_tools(
    manifest: dict[str, Any],
    paths: dict[str, Path] | None = None,
    quiet: bool = False,
) -> list[str]:
    """Ensure all vendor repositories defined in manifest exist in ZIRO_DATA/vendor."""
    if os.environ.get("ZIRO_SKIP_VENDOR_CLONE") == "1":
        return []

    if paths is None:
        paths = get_paths()

    vendor_root = paths["data"] / "vendor"
    repos = get_vendor_repos(manifest)
    if not repos:
        return []

    # Filter repos that need cloning
    to_clone: dict[str, tuple[str, Path]] = {}
    for src, url in repos.items():
        dest = vendor_root / src
        if not (dest.is_dir() and ((dest / ".git").is_dir() or any(dest.iterdir()))):
            to_clone[src] = (url, dest)

    if not to_clone:
        return []

    if not quiet:
        print(f"[*] Bootstrapping {len(to_clone)} vendor tool(s)...")

    cloned: list[str] = []
    # Use concurrent cloning for speed
    with ThreadPoolExecutor(max_workers=min(4, len(to_clone))) as executor:
        futures = {
            executor.submit(_clone_single_vendor, src, url, dest): src
            for src, (url, dest) in to_clone.items()
        }
        for future in as_completed(futures):
            src = futures[future]
            try:
                name, ok, msg = future.result()
                if ok:
                    cloned.append(name)
                    if not quiet:
                        print(f"  ✔ {name}")
                else:
                    if not quiet:
                        print(f"  ⚠️  {name}: {msg}")
            except Exception as e:
                if not quiet:
                    print(f"  ⚠️  {src}: {e}")

    return cloned


__all__ = ["ensure_vendor_tools", "get_vendor_repos"]
