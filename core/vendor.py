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


def _sync_single_vendor(
    source: str,
    url: str,
    dest: Path,
    update_existing: bool = False,
    force: bool = False,
) -> tuple[str, bool, str]:
    """Clone or update a single vendor repo using shallow git operations."""
    is_git_dir = (dest / ".git").is_dir()

    if dest.is_dir() and is_git_dir:
        if not update_existing and not force:
            return source, True, "already present"

        # Update existing repository
        try:
            # 1. Ensure remote origin is set to expected URL
            subprocess.run(
                ["git", "-C", str(dest), "remote", "set-url", "origin", url],
                capture_output=True,
                text=True,
                timeout=10,
            )

            # 2. Fetch origin with refspec to support shallow/tag/detached clones
            r_fetch = subprocess.run(
                ["git", "-C", str(dest), "fetch", "--depth", "1", "-q", "origin", "+refs/heads/*:refs/remotes/origin/*"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if r_fetch.returncode != 0:
                # Fallback to simple fetch
                r_fetch = subprocess.run(
                    ["git", "-C", str(dest), "fetch", "-q", "origin"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

            if r_fetch.returncode == 0:
                # Detect target ref
                target_ref = None
                for cand in ("origin/HEAD", "origin/main", "origin/master"):
                    chk = subprocess.run(
                        ["git", "-C", str(dest), "rev-parse", "--verify", cand],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if chk.returncode == 0:
                        target_ref = cand
                        break

                if target_ref:
                    # Compare local HEAD commit with target ref commit
                    head_res = subprocess.run(
                        ["git", "-C", str(dest), "rev-parse", "HEAD"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    target_res = subprocess.run(
                        ["git", "-C", str(dest), "rev-parse", target_ref],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    is_same_commit = (
                        head_res.returncode == 0
                        and target_res.returncode == 0
                        and head_res.stdout.strip() == target_res.stdout.strip()
                    )

                    # Check working tree cleanliness
                    stat_res = subprocess.run(
                        ["git", "-C", str(dest), "status", "--porcelain", "-uno"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    is_clean = not bool(stat_res.stdout.strip())

                    if is_same_commit and is_clean and not force:
                        return source, True, "up to date"

                    # Discard stale artifacts / local changes and sync to target ref
                    reset_res = subprocess.run(
                        ["git", "-C", str(dest), "reset", "--hard", target_ref],
                        capture_output=True,
                        text=True,
                        timeout=15,
                    )
                    subprocess.run(
                        ["git", "-C", str(dest), "clean", "-fd"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if reset_res.returncode == 0:
                        return source, True, "updated"
        except Exception:
            pass

        # If update in place failed and force is requested, wipe and re-clone
        if force:
            shutil.rmtree(dest, ignore_errors=True)
        else:
            return source, True, "already present (update skipped)"

    elif dest.is_dir():
        # Directory exists but is not a valid git repository (corrupted)
        shutil.rmtree(dest, ignore_errors=True)

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


_clone_single_vendor = _sync_single_vendor


def ensure_vendor_tools(
    manifest: dict[str, Any],
    paths: dict[str, Path] | None = None,
    quiet: bool = False,
    update_existing: bool = False,
    force: bool = False,
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

    # Filter repos that need cloning or updating
    to_sync: dict[str, tuple[str, Path]] = {}
    for src, url in repos.items():
        dest = vendor_root / src
        if update_existing or force or not (dest.is_dir() and ((dest / ".git").is_dir() or any(dest.iterdir()))):
            to_sync[src] = (url, dest)

    if not to_sync:
        return []

    action_label = "Bootstrapping / Updating" if (update_existing or force) else "Bootstrapping"
    if not quiet:
        print(f"[*] {action_label} {len(to_sync)} vendor tool(s)...")

    cloned: list[str] = []
    # Use concurrent cloning/updating for speed
    with ThreadPoolExecutor(max_workers=min(4, len(to_sync))) as executor:
        futures = {
            executor.submit(_sync_single_vendor, src, url, dest, update_existing, force): src
            for src, (url, dest) in to_sync.items()
        }
        for future in as_completed(futures):
            src = futures[future]
            try:
                name, ok, msg = future.result()
                if ok:
                    cloned.append(name)
                    if not quiet:
                        print(f"  ✔ {name} ({msg})")
                else:
                    if not quiet:
                        print(f"  ⚠️  {name}: {msg}")
            except Exception as e:
                if not quiet:
                    print(f"  ⚠️  {src}: {e}")

    return cloned


__all__ = ["ensure_vendor_tools", "get_vendor_repos"]
