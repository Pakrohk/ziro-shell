"""ziro-shell — update command.

Layer: 3 (Python core, cold-path only)
Spec: 008 / Phase B Orchestrator
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


def _repo_dir() -> Path:
    env = os.environ.get("ZIRO_HOME")
    if env and (Path(env) / ".git").exists():
        return Path(env)
    default_home = Path.home() / ".ziro"
    if (default_home / ".git").exists():
        return default_home
    # Fallback to repository containing this source file (development / CI mode)
    candidate = Path(__file__).resolve().parent.parent
    if (candidate / ".git").exists():
        return candidate
    if env:
        return Path(env)
    return default_home


def _cache_dir() -> Path:
    env = os.environ.get("ZIRO_CACHE")
    if env:
        return Path(env)
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg) / "ziro"
    return Path.home() / ".cache" / "ziro"


def _config_dir() -> Path:
    env = os.environ.get("ZIRO_CONFIG")
    if env:
        return Path(env)
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "ziro"
    return Path.home() / ".config" / "ziro"


def is_opted_out(config_dir: Path | None = None) -> bool:
    """Return True if user explicitly opted out of update checks in defaults.toml."""
    cfg = config_dir or _config_dir()
    defaults_file = cfg / "defaults.toml"
    if not defaults_file.is_file():
        return False
    try:
        content = defaults_file.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("check_for_updates") or line.startswith("enabled"):
                parts = line.split("=", 1)
                if len(parts) == 2 and parts[1].strip().lower() in ("false", "0", '"false"'):
                    return True
    except OSError:
        return False
    return False


def is_cache_fresh(cache_file: Path, ttl: int = 86400, now: float | None = None) -> bool:
    """Check if cache file exists and was checked within ttl seconds."""
    if not cache_file.is_file():
        return False
    current_time = now if now is not None else time.time()
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        checked_at = data.get("checked_at")
        if checked_at and isinstance(checked_at, (int, float)):
            return (current_time - checked_at) < ttl
        mtime = cache_file.stat().st_mtime
        return (current_time - mtime) < ttl
    except (OSError, json.JSONDecodeError, ValueError):
        return False


def read_cache(cache_file: Path) -> dict | None:
    """Read cached update info if valid JSON."""
    if not cache_file.is_file():
        return None
    try:
        return json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_cache(cache_file: Path, data: dict) -> None:
    """Persist update status to cache file atomically."""
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache_file.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(cache_file)
    except OSError:
        pass


def check_update(
    repo_dir: Path | None = None,
    cache_dir: Path | None = None,
    fetch: bool = True,
) -> dict:
    """Check repository against origin/main for available updates."""
    repo = repo_dir or _repo_dir()
    cache_d = cache_dir or _cache_dir()
    cache_file = cache_d / "update-check.json"

    result = {
        "available": False,
        "local": "",
        "remote": "",
        "behind": 0,
        "checked_at": int(time.time()),
        "error": None,
    }

    git_dir = repo / ".git"
    if not git_dir.exists():
        result["error"] = "not a git repository"
        return result

    try:
        local_hash_res = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        local_hash = local_hash_res.stdout.strip()
        result["local"] = local_hash
    except (subprocess.SubprocessError, OSError) as e:
        result["error"] = f"git rev-parse failed: {e}"
        return result

    if fetch:
        try:
            subprocess.run(
                ["git", "-C", str(repo), "fetch", "-q", "origin", "main"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
        except (subprocess.SubprocessError, OSError):
            # Non-fatal: offline or unable to reach origin
            pass

    remote_hash = ""
    remote_ref = None
    for ref_candidate in ("origin/main", "FETCH_HEAD"):
        p = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", ref_candidate],
            capture_output=True,
            text=True,
        )
        if p.returncode == 0 and p.stdout.strip():
            remote_hash = p.stdout.strip()
            remote_ref = ref_candidate
            break

    result["remote"] = remote_hash
    if remote_hash and local_hash and remote_ref:
        try:
            rev_count = subprocess.run(
                ["git", "-C", str(repo), "rev-list", "--count", f"HEAD..{remote_ref}"],
                capture_output=True,
                text=True,
                check=True,
            )
            behind = int(rev_count.stdout.strip() or "0")
            result["behind"] = behind
            result["available"] = behind > 0
        except (subprocess.SubprocessError, OSError, ValueError):
            pass

    write_cache(cache_file, result)
    return result


def perform_update(
    repo_dir: Path | None = None,
    force: bool = False,
) -> tuple[int, str]:
    """Execute update check with dirty working tree protection."""
    repo = repo_dir or _repo_dir()
    git_dir = repo / ".git"
    if not git_dir.exists():
        return 1, f"ziro: {repo} is not a git repository"

    # Check for uncommitted changes in tracked files
    status_res = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain", "-uno"],
        capture_output=True,
        text=True,
    )
    if status_res.stdout.strip() and not force:
        return 1, "ziro: working directory has uncommitted tracked changes. Stash or commit before updating (or pass --force)."

    short_local = "current"
    try:
        rev_res = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
        )
        if rev_res.returncode == 0:
            short_local = rev_res.stdout.strip()
    except Exception:
        pass

    return 0, f"Ziro Shell repository is up to date ({short_local})."


def find_vendor_plugins(target_plugin: str | None = None) -> list[tuple[str, Path]]:
    """Discover installed git plugin repositories in vendor directories."""
    bases = [
        Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")) / "ziro" / "vendor",
        Path(os.environ.get("ZIRO_HOME", Path.home() / ".ziro")) / "vendor",
    ]
    seen_paths = set()
    seen_names = set()
    plugins: list[tuple[str, Path]] = []

    for base in bases:
        if not base.is_dir():
            continue
        for p in sorted(base.rglob(".git")):
            repo_dir = p.parent
            if repo_dir in seen_paths:
                continue
            seen_paths.add(repo_dir)
            try:
                rel = str(repo_dir.relative_to(base))
            except ValueError:
                rel = repo_dir.name

            # Skip deprecated/removed tools
            if rel in ("znap", "ziro-defer"):
                continue

            # If target_plugin specified, filter by slug or name
            if target_plugin:
                target_norm = target_plugin.strip().lower()
                if target_norm not in rel.lower() and target_norm != repo_dir.name.lower():
                    continue

            if rel in seen_names:
                continue
            seen_names.add(rel)
            plugins.append((rel, repo_dir))

    return plugins


def update_single_plugin(name: str, path: Path, dry_run: bool = False) -> bool:
    """Check / fetch plugin updates. Return True if changes detected / applied."""
    if dry_run:
        return False

    try:
        status_res = subprocess.run(
            ["git", "-C", str(path), "status", "--porcelain", "-uno"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if status_res.stdout.strip():
            # Dirty plugin working tree — skip modifying to avoid data loss
            return False

        # Fetch
        subprocess.run(
            ["git", "-C", str(path), "fetch", "-q", "origin"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Check if behind origin/HEAD or origin/main or origin/master
        rev_res = subprocess.run(
            ["git", "-C", str(path), "rev-list", "--count", "HEAD..origin/HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if rev_res.returncode == 0:
            behind = int(rev_res.stdout.strip() or "0")
            if behind > 0:
                pull_res = subprocess.run(
                    ["git", "-C", str(path), "pull", "--ff-only"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                return pull_res.returncode == 0
    except Exception:
        return False
    return False


def cmd_update(argv: list[str]) -> int:
    from core.help_cli import handle_help_if_requested
    ret = handle_help_if_requested(argv, "update")
    if ret is not None:
        return ret

    check_only = False
    force = False
    dev_mode = False
    dry_run = False
    yes = False
    plugins_only = False
    sync_only = False
    target_plugin: str | None = None
    no_analyze = False
    quiet = False

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--check", "-c"):
            check_only = True
        elif arg in ("--force", "-f"):
            force = True
        elif arg == "--dev":
            dev_mode = True
        elif arg == "--dry-run":
            dry_run = True
        elif arg in ("--yes", "-y"):
            yes = True
        elif arg == "--plugins-only":
            plugins_only = True
        elif arg == "--sync-only":
            sync_only = True
        elif arg == "--no-analyze":
            no_analyze = True
        elif arg == "--plugin":
            if i + 1 < len(argv):
                i += 1
                target_plugin = argv[i]
            else:
                print("ziro update: error: --plugin requires an argument", file=sys.stderr)
                return 2
        elif arg.startswith("--plugin="):
            target_plugin = arg.split("=", 1)[1]
        elif arg in ("--quiet", "-q"):
            quiet = True
        elif arg in ("--help", "-h"):
            from core.help_cli import handle_help_if_requested
            return handle_help_if_requested(["--help"], "update") or 0
        else:
            print(f"ziro update: unrecognized option '{arg}'", file=sys.stderr)
            return 2
        i += 1

    repo = _repo_dir()

    # Mode 1: --sync-only (alias to ziro sync)
    if sync_only:
        from core.build import build
        ok, msg, counts = build()
        if not quiet:
            print(f"✔ {msg}")
        return 0 if ok else 1

    # Mode 2: --check
    if check_only:
        res = check_update(repo, fetch=True)
        if res.get("error"):
            print(f"ziro update check: {res['error']}", file=sys.stderr)
            return 1
        if res.get("available"):
            behind = res.get("behind", 1)
            print(f"Update available: {behind} commit(s) behind origin/main. Run 'ziro update' to apply.")
            return 0
        short_local = (res.get("local") or "current")[:7]
        print(f"Ziro Shell is up to date ({short_local}).")
        return 0

    # Mode 3: git-dirty working tree protection (skipped for dry-run and plugins-only)
    if not dry_run and not plugins_only:
        git_dir = repo / ".git"
        if git_dir.exists():
            status_res = subprocess.run(
                ["git", "-C", str(repo), "status", "--porcelain", "-uno"],
                capture_output=True,
                text=True,
            )
            if status_res.stdout.strip():
                if dev_mode and not force:
                    force = True
                    print("ziro update: warning: dev mode: dirty guard bypassed", file=sys.stderr)
                elif not force:
                    print(
                        "ziro: working directory has uncommitted tracked changes. Stash or commit before updating (or pass --force).",
                        file=sys.stderr,
                    )
                    return 1

    # Mode 4: --dry-run
    if dry_run:
        print("ziro update plan (dry-run):")
        if not plugins_only:
            print("  1. Self repository check:")
            res = check_update(repo, fetch=False)
            if res.get("available"):
                print(f"     Status: update available ({res.get('behind', 1)} commit(s) behind)")
            else:
                short_local = (res.get("local") or "current")[:7]
                print(f"     Status: up to date ({short_local})")
        plugins = find_vendor_plugins(target_plugin=target_plugin)
        print(f"  2. Plugins ({len(plugins)} target(s)):")
        for name, p in plugins:
            print(f"     - {name}")
        if not plugins_only:
            print("  3. Build & synchronize boot artifacts (ziro sync)")
        print()
        print("ℹ️  Dry-run complete. No changes made.")
        return 0

    # Mode 5: Orchestration flow
    # Step 1: Self check
    if not plugins_only:
        res = check_update(repo, fetch=True)
        if res.get("available"):
            behind = res.get("behind", 1)
            print(f"ℹ️  Update available: {behind} commit(s) behind origin/main.")
            print(f"   To update Ziro Shell repository manually (H2 safety): run 'git -C {repo} pull'")
        elif not quiet:
            short_local = (res.get("local") or "current")[:7]
            print(f"Ziro Shell repository is up to date ({short_local}).")

    # Step 2: Plugin updates
    plugins = find_vendor_plugins(target_plugin=target_plugin)
    updated_plugins = []
    if plugins and not quiet:
        print(f"Checking {len(plugins)} plugin(s)...")
    for name, p in plugins:
        upd = update_single_plugin(name, p, dry_run=False)
        if upd:
            updated_plugins.append(name)
            if not quiet:
                print(f"  ✔ Updated plugin: {name}")

    # Step 3: Tool-set drift analysis
    if updated_plugins and not no_analyze:
        should_analyze = yes
        if not should_analyze and sys.stdin.isatty():
            try:
                ans = input("Plugin updates detected. Re-analyze tool configuration? [y/N] ").strip().lower()
                should_analyze = ans in ("y", "yes")
            except (EOFError, KeyboardInterrupt):
                should_analyze = False
        if should_analyze:
            from core.analyze_cli import main as analyze_main
            analyze_main(["--full"])

    # Step 4: Rebuild boot artifacts
    if not plugins_only:
        from core.build import build
        ok, msg, counts = build()
        if not quiet:
            print(f"✔ {msg}")
        if not ok:
            return 1

    if not quiet:
        print("✔ Update orchestration complete.")
    return 0


def main(argv: list[str] | None = None) -> int:
    return cmd_update(argv if argv is not None else sys.argv[1:])
