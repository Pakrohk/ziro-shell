"""Helper routines to fetch Ghost v2.0.1 vendor source and precompiled binaries.

Layer: 3 (Python core)
Spec: 024 (R1, R2, R5)
"""

from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import sys
import urllib.request
from pathlib import Path

from core.paths import _ensure_secure_perms, get_paths

GHOST_VERSION = "2.0.1"
GHOST_REPO_URL = "https://github.com/Pakrohk/ziro-ghost"
RELEASE_BASE_URL = f"https://github.com/Pakrohk/ziro-ghost/releases/download/v{GHOST_VERSION}"


def get_platform_target() -> str | None:
    """Map system platform and architecture to Ghost release binary target."""
    sys_name = sys.platform.lower()
    arch = platform.machine().lower()
    if sys_name.startswith("linux"):
        if arch in ("x86_64", "amd64"):
            return "linux-x86_64"
        elif arch in ("aarch64", "arm64"):
            return "linux-aarch64"
    elif sys_name == "darwin":
        if arch in ("x86_64", "amd64"):
            return "darwin-x86_64"
        elif arch in ("arm64", "aarch64"):
            return "darwin-arm64"
    return None


def fetch_ghost_vendor(target_dir: Path | None = None) -> bool:
    """Clone or checkout Ghost v2.0.1 into vendor directory."""
    paths = get_paths()
    vendor_root = target_dir or (paths["data"] / "vendor" / "Pakrohk" / "ziro-ghost")
    vendor_root.parent.mkdir(parents=True, exist_ok=True)
    _ensure_secure_perms(vendor_root.parent)

    try:
        if (vendor_root / ".git").is_dir():
            subprocess.run(
                ["git", "-C", str(vendor_root), "fetch", "--tags", "-q", "origin"],
                capture_output=True,
                timeout=30,
            )
            r = subprocess.run(
                ["git", "-C", str(vendor_root), "checkout", "-q", f"v{GHOST_VERSION}"],
                capture_output=True,
                timeout=15,
            )
            return r.returncode == 0
        else:
            r = subprocess.run(
                [
                    "git",
                    "clone",
                    "-q",
                    "--depth=1",
                    "--branch",
                    f"v{GHOST_VERSION}",
                    GHOST_REPO_URL,
                    str(vendor_root),
                ],
                capture_output=True,
                timeout=45,
            )
            return r.returncode == 0
    except Exception:
        return False


def fetch_ghost_binary(dest_dir: Path | None = None) -> bool:
    """Download platform-matched ghost-popup binary, verify SHA256, and install."""
    target = get_platform_target()
    if not target:
        print(
            f"ziro: warning: unsupported platform ({sys.platform}-{platform.machine()}) for prebuilt ghost-popup; source compile fallback required.",
            file=sys.stderr,
        )
        return False

    paths = get_paths()
    vendor_dir = dest_dir or (paths["data"] / "vendor" / "Pakrohk" / "ziro-ghost")
    bin_dir = vendor_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    _ensure_secure_perms(bin_dir)
    target_bin = bin_dir / "ghost-popup"

    binary_name = f"ghost-popup-{target}"
    bin_url = f"{RELEASE_BASE_URL}/{binary_name}"
    sums_url = f"{RELEASE_BASE_URL}/SHA256SUMS"

    try:
        # 1. Fetch SHA256SUMS
        sums_req = urllib.request.Request(sums_url, headers={"User-Agent": "ziro-shell"})
        with urllib.request.urlopen(sums_req, timeout=15) as resp:
            sums_text = resp.read().decode("utf-8")

        expected_hash = None
        for line in sums_text.splitlines():
            parts = line.strip().split()
            if len(parts) == 2 and parts[1].strip() == binary_name:
                expected_hash = parts[0].strip()
                break

        if not expected_hash:
            print(f"ziro: warning: could not find expected hash for {binary_name} in SHA256SUMS", file=sys.stderr)
            return False

        # 2. Download binary to temp file
        tmp_bin = bin_dir / f".tmp-{binary_name}"
        bin_req = urllib.request.Request(bin_url, headers={"User-Agent": "ziro-shell"})
        hasher = hashlib.sha256()
        with urllib.request.urlopen(bin_req, timeout=30) as resp, open(tmp_bin, "wb") as f:
            while chunk := resp.read(65536):
                hasher.update(chunk)
                f.write(chunk)

        computed_hash = hasher.hexdigest()
        if computed_hash != expected_hash:
            tmp_bin.unlink(missing_ok=True)
            print(f"ziro: error: SHA256 mismatch for {binary_name}: got {computed_hash}, expected {expected_hash}", file=sys.stderr)
            return False

        # 3. Rename and chmod +x
        tmp_bin.replace(target_bin)
        target_bin.chmod(0o755)

        # Also place symlink or copy to ~/.local/bin/ghost-popup if ~/.local/bin exists
        user_local_bin = Path.home() / ".local" / "bin"
        if user_local_bin.is_dir():
            link_path = user_local_bin / "ghost-popup"
            try:
                link_path.unlink(missing_ok=True)
                link_path.symlink_to(target_bin)
            except Exception:
                pass

        # 4. Verify binary runs --version
        v_res = subprocess.run([str(target_bin), "--version"], capture_output=True, text=True, timeout=5)
        if v_res.returncode == 0 and f"ghost-popup {GHOST_VERSION}" in v_res.stdout:
            return True
        return False
    except Exception as e:
        print(f"ziro: warning: ghost-popup download failed: {e}", file=sys.stderr)
        return False
