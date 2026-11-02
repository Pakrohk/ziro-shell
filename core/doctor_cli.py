"""ziro-shell — doctor command (health check).

Layer: 3 (Python core, cold-path only)
Spec: 006 SC-1 / Section 4 closeout / 4-E Comprehensive Rebuild
"""

from __future__ import annotations

import os
import platform
import shutil
import stat
import subprocess
import sys
import tomllib
from pathlib import Path

from core.paths import get_paths

OSC52_ENABLE_GUIDE = {
    "iTerm.app": 'Settings → General → Selection → enable "Applications in terminal may access clipboard"',
    "tmux": "Add to ~/.tmux.conf: set -g set-clipboard on, then: tmux source ~/.tmux.conf",
    "Apple_Terminal": "Terminal.app does not support OSC 52. Ziro uses pbcopy/pbpaste fallback automatically.",
    "gnome-terminal": "Supported in GNOME Terminal 3.44+. If not working, upgrade terminal.",
    "mintty": 'Check Options → Terminal → "Allow OSC52" (usually enabled by default)',
    "Windows Terminal": "Supported by default in Windows Terminal 1.15+. If not working, upgrade Windows Terminal.",
}


def _config_dir() -> Path:
    return get_paths()["config"]


def _ziro_home() -> Path:
    return get_paths()["home"]


def _expand_path(p: str) -> Path:
    """Expand ~, $VARS, ${VARS} with fallbacks for standard ZIRO_* directories."""
    if not p:
        return Path()
    paths = get_paths()
    env = {
        "ZIRO_DATA": str(paths["data"]),
        "ZIRO_CACHE": str(paths["cache"]),
        "ZIRO_CONFIG": str(paths["config"]),
        "ZIRO_HOME": str(paths["home"]),
    }
    # Expand ZIRO_* defaults without polluting global os.environ
    expanded_str = p
    for k, v in env.items():
        if k not in os.environ:
            expanded_str = expanded_str.replace(f"${{{k}}}", v).replace(f"${k}", v)
    expanded = os.path.expandvars(os.path.expanduser(expanded_str))
    return Path(expanded)


def _detect_pkg_manager() -> str | None:
    """Detect available system package manager."""
    for pm in ("pacman", "apt-get", "dnf", "brew", "apk"):
        if shutil.which(pm):
            return pm
    return None


def _check_python_version() -> tuple[str, str, str | None]:
    """Verify Python runtime meets minimum requirement (3.11+)."""
    ok = sys.version_info >= (3, 11)
    v_str = f"python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if ok:
        return "ok", v_str, None
    return "error", f"{v_str} (< 3.11 required)", "install Python 3.11 or newer"


def _check_zsh_version() -> tuple[str, str, str | None]:
    """Verify system Zsh version is 5.8 or higher."""
    try:
        proc = subprocess.run(["zsh", "--version"], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0 and proc.stdout:
            out = proc.stdout.strip()
            parts = out.split()
            if len(parts) >= 2:
                ver_str = parts[1]
                subparts = ver_str.split(".")
                major = int(subparts[0]) if subparts[0].isdigit() else 0
                minor = int(subparts[1]) if len(subparts) > 1 and subparts[1].isdigit() else 0
                if (major, minor) >= (5, 8):
                    return "ok", out, None
                return "error", f"{out} (< 5.8 required)", "upgrade Zsh to 5.8 or newer"
            return "ok", out, None
    except Exception as e:
        return "error", f"zsh check failed: {e}", "install Zsh 5.8+"
    return "error", "zsh binary not found in PATH", "install Zsh 5.8+"


def _check_git_version() -> tuple[str, str, str | None]:
    """Verify Git is installed and available in PATH."""
    p = shutil.which("git")
    if not p:
        local_git = Path.home() / ".local" / "bin" / "git"
        if local_git.is_file() and os.access(local_git, os.X_OK):
            p = str(local_git)
    if not p:
        pm = _detect_pkg_manager()
        advice = "install Git (required for ziro updates and plugin cloning)"
        if pm == "pacman":
            advice = "sudo pacman -S --needed git"
        elif pm == "apt-get":
            advice = "sudo apt install -y git"
        elif pm == "dnf":
            advice = "sudo dnf install -y git"
        elif pm == "brew":
            advice = "brew install git"
        return "error", "git binary not found in PATH", advice
    try:
        proc = subprocess.run([p, "--version"], capture_output=True, text=True, timeout=5)
        out = proc.stdout.strip() if proc.stdout else f"git ({p})"
        return "ok", f"{out} ({p})", None
    except Exception as e:
        return "error", f"git check failed: {e}", "reinstall Git via package manager"


def _check_starship_version() -> tuple[str, str, str | None]:
    """Verify Starship prompt engine is installed."""
    p = shutil.which("starship")
    if not p:
        local_star = Path.home() / ".local" / "bin" / "starship"
        if local_star.is_file() and os.access(local_star, os.X_OK):
            p = str(local_star)
    if not p:
        pm = _detect_pkg_manager()
        if pm == "pacman":
            advice = "sudo pacman -S --needed starship"
        elif pm == "brew":
            advice = "brew install starship"
        elif pm == "dnf":
            advice = "sudo dnf install -y starship"
        else:
            advice = "curl -fsSL https://starship.rs/install.sh | sh"
        return "error", "starship prompt engine not found in PATH", advice
    try:
        proc = subprocess.run([p, "--version"], capture_output=True, text=True, timeout=5)
        ver = proc.stdout.splitlines()[0] if proc.stdout else f"starship ({p})"
        return "ok", f"{ver} ({p})", None
    except Exception as e:
        return "error", f"starship check failed: {e}", "reinstall Starship"


def _check_boot_shim_ziro_home() -> tuple[str, str, str | None]:
    """Verify boot.zsh exists and contains a valid, non-ephemeral ZIRO_HOME path."""
    import re
    import tempfile
    paths = get_paths()
    boot_shim = paths["config"] / "boot.zsh"
    if not boot_shim.is_file():
        return "error", f"boot.zsh missing at {boot_shim}", "run `ziro sync`"

    try:
        content = boot_shim.read_text(encoding="utf-8")
    except Exception as e:
        return "error", f"could not read boot.zsh: {e}", "run `ziro sync`"

    match = re.search(r'export ZIRO_HOME="?([^"\n]+)"?', content)
    if not match:
        return "error", "no ZIRO_HOME found in boot.zsh", "run `ziro sync`"

    ziro_home_str = match.group(1).strip()
    home_path = Path(ziro_home_str)

    if not home_path.is_absolute():
        return "error", f"boot.zsh ZIRO_HOME is not absolute: {ziro_home_str}", "run `ziro sync`"

    if not home_path.is_dir():
        return "error", f"boot.zsh ZIRO_HOME does not exist: {ziro_home_str}", "reinstall ziro or run `ziro sync`"

    try:
        resolved = home_path.resolve()
        temp_roots = [Path("/tmp"), Path("/var/tmp"), Path(tempfile.gettempdir())]
        tmpdir = os.environ.get("TMPDIR")
        if tmpdir:
            temp_roots.append(Path(tmpdir))
        for temp in temp_roots:
            try:
                resolved.relative_to(temp.resolve())
                return "error", f"boot.zsh ZIRO_HOME is in temporary directory: {ziro_home_str}", "run `ziro sync` from a clean shell"
            except ValueError:
                continue
    except Exception as e:
        return "error", f"boot.zsh ZIRO_HOME path resolution error: {e}", "run `ziro sync`"

    if not (home_path / "core" / "__main__.py").is_file():
        return "error", f"boot.zsh ZIRO_HOME missing core/__main__.py: {ziro_home_str}", "reinstall ziro"

    has_git = (home_path / ".git").exists()
    has_marker = (home_path / ".ziro-root").exists()
    has_pyproject = (home_path / "pyproject.toml").is_file()
    if not has_git and not has_marker and not has_pyproject:
        return "error", f"boot.zsh ZIRO_HOME missing .git/ or markers: {ziro_home_str}", "reinstall ziro"

    return "ok", f"boot.zsh ZIRO_HOME verified: {ziro_home_str}", None


def _check_boot_chain() -> tuple[str, str, str | None]:
    """Verify boot chain integrity: load.toml -> boot.zsh -> ziro-boot.zsh -> ziro-boot.zwc."""
    paths = get_paths()
    load_toml = paths["config"] / "load.toml"
    boot_shim = paths["config"] / "boot.zsh"
    boot_script = paths["cache"] / "ziro-boot.zsh"
    boot_zwc = paths["cache"] / "ziro-boot.zsh.zwc"

    missing = []
    if not load_toml.is_file():
        missing.append(str(load_toml))
    if not boot_shim.is_file():
        missing.append(str(boot_shim))
    if not boot_script.is_file():
        missing.append(str(boot_script))
    if not boot_zwc.is_file():
        missing.append(str(boot_zwc))

    if missing:
        return "error", f"missing boot artifact(s): {', '.join(missing)}", "run `ziro sync`"

    try:
        if boot_zwc.stat().st_mtime < boot_script.stat().st_mtime:
            return "error", "ziro-boot.zsh.zwc is older than ziro-boot.zsh", "run `ziro sync`"

        # Spec 018 R8, R11: verify boot zwc is 0600
        zwc_mode = stat.S_IMODE(boot_zwc.stat().st_mode)
        if zwc_mode != 0o600:
            return "error", f"ziro-boot.zsh.zwc is not 0600: {oct(zwc_mode)}", "run `ziro sync`"

        # Spec 018 R11: verify core directories are 0700
        bad_dirs = []
        for name, p in paths.items():
            if p.is_dir():
                mode = stat.S_IMODE(p.stat().st_mode)
                if mode != 0o700:
                    bad_dirs.append(f"{name} ({oct(mode)})")
        if bad_dirs:
            return "error", f"core directory not 0700: {', '.join(bad_dirs)}", "run `ziro sync`"
    except Exception as e:
        return "error", f"error inspecting boot chain: {e}", "run `ziro sync`"

    return "ok", "boot chain complete, fresh, and secure (boot.zsh → ziro-boot.zwc)", None


def _check_compiled_artifacts() -> tuple[str, str, str | None]:
    """Check that every eager tool has a fresh .zwc sibling."""
    load_toml = get_paths()["config"] / "load.toml"
    if not load_toml.is_file():
        return "error", "load.toml not found", "run `ziro sync`"
    try:
        with load_toml.open("rb") as f:
            manifest = tomllib.load(f)
    except Exception as e:
        return "error", f"could not parse load.toml: {e}", "run `ziro analyze --full`"

    missing: list[str] = []
    stale: list[str] = []
    ok: list[str] = []

    for tool in manifest.get("tool", []):
        if tool.get("timing") != "eager" or not tool.get("enabled", True):
            continue
        method = tool.get("method", "")
        if method == "eval-cache":
            target = tool.get("cache_path", "")
        elif method in ("source", "local-source"):
            target = tool.get("path", "")
        else:
            continue
        if not target:
            continue

        tpath = _expand_path(target)
        if not tpath.is_file():
            missing.append(f"{tool.get('name', target)} (source missing)")
            continue

        zwc = Path(str(tpath) + ".zwc")
        if not zwc.is_file():
            missing.append(f"{tool.get('name', target)} (missing .zwc)")
        elif zwc.stat().st_mtime < tpath.stat().st_mtime:
            stale.append(f"{tool.get('name', target)} (stale .zwc)")
        else:
            ok.append(tool.get("name", str(tpath)))

    if missing:
        return "error", f"{len(missing)} eager artifact(s) missing: {missing[:2]}", "run `ziro sync`"
    if stale:
        return "error", f"{len(stale)} eager artifact(s) stale: {stale[:2]}", "run `ziro sync`"
    return "ok", f"{len(ok)} eager artifact(s) compiled and fresh", None


def _check_runtime_commands() -> tuple[str, str, str | None]:
    """Verify runtime command and function loading in an actual Zsh subshell."""
    paths = get_paths()
    boot_shim = paths["config"] / "boot.zsh"
    if not boot_shim.is_file():
        return "warn", "boot.zsh not found (runtime verification skipped)", "run `ziro sync`"

    script = """
source "$1" || exit 2
missing=()
alias ll >/dev/null 2>&1 || missing+=(ll)
alias la >/dev/null 2>&1 || missing+=(la)
alias lt >/dev/null 2>&1 || missing+=(lt)
alias .. >/dev/null 2>&1 || missing+=(..)
(( $+functions[mkcd] )) || missing+=(mkcd)
(( $+functions[extract] )) || missing+=(extract)
(( $+functions[ziro] )) || (( $+commands[ziro] )) || missing+=(ziro)
(( $+commands[man] )) && { man -w ziro >/dev/null 2>&1 || missing+=(man-ziro); }
if (( ${#missing} > 0 )); then
  print "missing: ${(j:, :)missing}"
  exit 1
fi
print "ok"
"""
    try:
        r = subprocess.run(
            ["zsh", "-f", "-c", script, "--", str(boot_shim)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode != 0:
            out = r.stdout.strip() or r.stderr.strip() or f"exit code {r.returncode}"
            return "error", f"runtime load check failed: {out}", "run `ziro sync`"
        return "ok", "runtime commands and functions loaded (ll, la, lt, .., mkcd, extract, ziro, man)", None
    except subprocess.TimeoutExpired:
        return "error", "runtime load check timed out (zsh boot hung)", "run `ziro sync`"
    except Exception as e:
        return "warn", f"runtime command verification skipped: {e}", None


def _check_tool_paths() -> tuple[str, str, str | None]:
    """Verify all enabled tools with paths point to existing files on disk."""
    load_toml = get_paths()["config"] / "load.toml"
    if not load_toml.is_file():
        return "error", "load.toml not found", "run `ziro sync`"
    try:
        with load_toml.open("rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        return "error", f"could not parse load.toml: {e}", "run `ziro analyze --full`"

    missing = []
    valid = 0
    tools = data.get("tool", [])
    for tool in tools:
        if not tool.get("enabled", True):
            continue
        path = tool.get("path", "")
        if not path:
            valid += 1
            continue
        exp = _expand_path(path)
        if exp.exists():
            valid += 1
        else:
            missing.append(tool.get("name", "?"))

    if missing:
        return "warn", f"{len(missing)} tool path(s) missing: {', '.join(missing[:3])}", "run `ziro plugin add <name>` for missing plugins"
    return "ok", f"{valid} tool path(s) valid on disk", None


def _check_tool_reasons() -> tuple[str, str, str | None]:
    """Report per-tool timing decision + reason from load.toml."""
    load_toml = get_paths()["config"] / "load.toml"
    if not load_toml.is_file():
        return "warn", "load.toml not found", "run `ziro analyze`"
    try:
        with load_toml.open("rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        return "warn", f"could not parse load.toml: {e}", "run `ziro analyze --full`"

    tools = data.get("tool", [])
    if not tools:
        return "info", "no tools in load.toml", None
    with_reasons = sum(1 for t in tools if t.get("reason"))
    if with_reasons == len(tools):
        return "ok", f"{with_reasons}/{len(tools)} tools with explicit reason", None
    return "info", f"{with_reasons}/{len(tools)} tools with explicit reason", "run `ziro analyze --full`"


def _check_loadtoml_schema() -> tuple[str, str, str | None]:
    """Validate load.toml syntax, required sections, and [user] table."""
    load_toml = get_paths()["config"] / "load.toml"
    if not load_toml.is_file():
        return "error", "load.toml not found", "run `ziro analyze --full`"
    try:
        with load_toml.open("rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        return "error", f"invalid load.toml syntax: {e}", "run `ziro analyze --full`"

    missing_sections = []
    for sec in ("meta", "boot", "defer"):
        if sec not in data:
            missing_sections.append(sec)
    if "tool" not in data or not isinstance(data["tool"], list):
        missing_sections.append("[[tool]]")

    if missing_sections:
        return "error", f"missing required section(s): {', '.join(missing_sections)}", "run `ziro analyze --full`"

    user_sec = data.get("user")
    if user_sec is not None and not isinstance(user_sec, dict):
        return "error", "[user] section must be a table", "edit ~/.config/ziro/load.toml to fix [user]"

    return "ok", f"schema valid ({len(data.get('tool', []))} tools)", None


def _check_defer_loaded() -> tuple[str, str, str | None]:
    """Verify presence of ziro-defer on disk."""
    paths = get_paths()
    home = paths["home"]
    data = paths["data"]
    candidates = [
        (home / "ziro-defer" / "ziro-defer.plugin.zsh", "ziro-defer (canonical fork)"),
        (data / "vendor" / "ziro-defer" / "ziro-defer.plugin.zsh", "ziro-defer (fork)"),
        (home / "vendor" / "ziro-defer" / "ziro-defer.plugin.zsh", "ziro-defer (fork)"),
        (data / "vendor" / "ziro-defer" / "zsh-defer.plugin.zsh", "zsh-defer (upstream)"),
        (home / "vendor" / "ziro-defer" / "zsh-defer.plugin.zsh", "zsh-defer (upstream)"),
    ]
    for p, label in candidates:
        if p.is_file():
            return "ok", f"{label}: {p}", None
    return "error", "ziro-defer/zsh-defer not found on disk", "check ZIRO_HOME or reinstall ziro"


def _check_defer_modules() -> tuple[str, str, str | None]:
    """Verify all eager_modules declared in load.toml exist on disk."""
    paths = get_paths()
    load_toml = paths["config"] / "load.toml"
    if not load_toml.is_file():
        return "warn", "load.toml not found", "run `ziro sync`"
    try:
        with load_toml.open("rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        return "warn", f"could not parse load.toml: {e}", "run `ziro sync`"

    mods = data.get("defer", {}).get("eager_modules", [])
    if not mods:
        return "ok", "no eager defer modules specified", None

    candidates = [
        paths["home"] / "vendor" / "ziro-defer",
        paths["home"] / "ziro-defer",
        paths["data"] / "vendor" / "ziro-defer",
    ]
    defer_root = None
    for cand in candidates:
        if cand.is_dir() and (cand / "api" / "ziro-defer.zsh").is_file():
            defer_root = cand
            break

    if not defer_root:
        return "warn", "defer root directory not found", "run `ziro sync`"

    missing = []
    for m in mods:
        if not (defer_root / m).is_file():
            missing.append(m)

    if missing:
        return "warn", f"{len(missing)} defer module(s) missing: {missing[:2]}", "run `ziro sync`"
    return "ok", f"{len(mods)}/{len(mods)} eager defer modules present", None


def _check_external_overrides() -> tuple[str, str, str | None]:
    """Inspect optional overrides.toml if configured."""
    override_file = os.environ.get("ZIRO_OVERRIDES_FILE")
    p = Path(override_file).expanduser() if override_file else (get_paths()["config"] / "overrides.toml")
    if not p.is_file():
        return "info", "none configured (optional)", None
    try:
        with p.open("rb") as f:
            data = tomllib.load(f)
        count = len(data.get("override", [])) if "override" in data else len(data)
        return "ok", f"active ({p}, {count} override(s))", None
    except Exception as e:
        return "warn", f"syntax error in {p}: {e}", f"fix TOML syntax in {p} or remove file"


def _check_legacy_config() -> tuple[str, str, str | None]:
    """Check status of legacy config files (informational only)."""
    cfg = _config_dir()
    found = []
    for name in ("defaults.toml", "tools.toml", ".theme.conf"):
        if (cfg / name).is_file():
            found.append(name)
    if found:
        return "info", f"{len(found)} legacy file(s) present ({', '.join(found)})", None
    return "info", "no legacy config files (clean)", None


def _check_ghost_cache_perms() -> tuple[str, str, str | None]:
    """Verify ghost cache file is 600 and dir is 700 (spec 016 R5-R6)."""
    import stat
    cache_file = Path.home() / ".cache" / "ziro" / "ghost" / "history-cache"
    cache_dir = cache_file.parent
    if not cache_dir.exists():
        return "ok", "ghost cache directory not yet created (clean)", None

    dir_mode = stat.S_IMODE(cache_dir.stat().st_mode)
    if dir_mode != 0o700:
        return "error", f"ghost cache dir perms {oct(dir_mode)} (expected 0700)", "run `chmod 700 ~/.cache/ziro/ghost`"

    if not cache_file.exists():
        return "ok", "ghost cache dir 700 (cache file not yet created)", None

    file_mode = stat.S_IMODE(cache_file.stat().st_mode)
    if file_mode != 0o600:
        return "error", f"ghost cache file perms {oct(file_mode)} (expected 0600)", "run `chmod 600 ~/.cache/ziro/ghost/history-cache`"

    return "ok", "ghost cache file 600, directory 700", None


def _check_legacy_ghost_cache() -> tuple[str, str, str | None]:
    """Warn if ghost history cache predates v1.2.3 installation (spec 018 R10)."""
    cache_file = Path.home() / ".cache" / "ziro" / "ghost" / "history-cache"
    if not cache_file.exists():
        return "ok", "no legacy ghost cache (clean)", None

    cache_mtime = cache_file.stat().st_mtime
    # Cutoff: 2026-10-30 00:00:00 UTC (1730246400). v1.2.3 was 2026-10-31.
    v123_install_cutoff = 1730246400
    if cache_mtime < v123_install_cutoff:
        import time
        return (
            "warn",
            f"ghost history cache may contain unfiltered secrets from before v1.2.3 (mtime: {time.ctime(cache_mtime)})",
            "run `rm ~/.cache/ziro/ghost/history-cache` to purge legacy cache",
        )
    return "ok", "ghost history cache post-dates v1.2.3 filter", None


def _check_ghost_cache_secrets() -> tuple[str, str, str | None]:
    """Audit ghost history cache for sensitive tokens or credentials."""
    from core.build import _is_ghost_line_sensitive
    cache_file = Path.home() / ".cache" / "ziro" / "ghost" / "history-cache"
    if not cache_file.is_file():
        return "ok", "no ghost history cache (clean)", None

    try:
        lines = cache_file.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as e:
        return "warn", f"could not read ghost history cache: {e}", None

    flagged = 0
    for line in lines:
        if _is_ghost_line_sensitive(line):
            flagged += 1

    if flagged > 0:
        return (
            "warn",
            f"ghost history cache contains {flagged} sensitive token(s)",
            "run `ziro sync` to sanitize history cache",
        )
    return "ok", f"ghost history cache clean (0 secrets in {len(lines)} lines)", None


def _check_theme_sharing_prereqs() -> tuple[str, str, str | None]:
    """Check prerequisites for ziro theme submit (gh CLI, auth status, starship config)."""
    gh_bin = shutil.which("gh")
    if not gh_bin:
        return (
            "info",
            "gh CLI not found",
            "install from https://cli.github.com/ to enable 'ziro theme submit'",
        )

    star_conf = Path(os.environ.get("STARSHIP_CONFIG", Path.home() / ".config" / "starship.toml"))
    if not star_conf.is_file():
        return (
            "info",
            "starship.toml not found",
            f"generate with 'starship preset <name> -o {star_conf}'",
        )

    try:
        r = subprocess.run([gh_bin, "auth", "status"], capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return (
                "info",
                "gh not authenticated",
                "run 'gh auth login' to enable theme sharing",
            )
    except Exception:
        return ("info", "gh auth check timed out or failed", None)

    return ("ok", "theme sharing ready (gh authenticated, starship.toml found)", None)


def _check_eval_cache_perms() -> tuple[str, str, str | None]:
    """Verify eval-cache .zwc files are 600 and dir is 700 (spec 016 R7)."""
    import stat
    paths = get_paths()
    eval_cache = paths["cache"] / "eval-cache"
    if not eval_cache.exists():
        return "info", "no eval-cache directory yet", None

    dir_mode = stat.S_IMODE(eval_cache.stat().st_mode)
    if dir_mode != 0o700:
        return "error", f"eval-cache dir perms {oct(dir_mode)} (expected 0700)", "run `ziro sync`"

    bad_files = []
    zwc_files = list(eval_cache.glob("*.zwc"))
    for zwc in zwc_files:
        mode = stat.S_IMODE(zwc.stat().st_mode)
        if mode != 0o600:
            bad_files.append(f"{zwc.name} ({oct(mode)})")

    if bad_files:
        return "error", f"{len(bad_files)} .zwc file(s) not 0600: {', '.join(bad_files[:2])}", "run `ziro sync`"

    return "ok", f"eval-cache dir 700, {len(zwc_files)} .zwc file(s) 600", None


def _check_root_profile() -> tuple[str, str, str | None]:
    """Verify root profile hardening (spec 022 R11)."""
    import os
    if os.geteuid() != 0:
        return "ok", "N/A (not root)", None

    paths = get_paths()
    config_path = paths["config"] / "starship-root.toml"
    if not config_path.exists():
        return "error", "starship-root.toml missing", "run `ziro sync`"

    try:
        content = config_path.read_text(encoding="utf-8")
    except Exception as e:
        return "error", f"cannot read starship-root.toml: {e}", "run `ziro sync`"

    if "[custom" in content:
        return (
            "error",
            "starship-root.toml contains [custom] (CVE-2024-41815 risk)",
            "regenerate: rm ~/.config/ziro/starship-root.toml && ziro sync",
        )

    starship_env = os.environ.get("STARSHIP_CONFIG")
    if starship_env and Path(starship_env).resolve() != config_path.resolve():
        return (
            "warn",
            f"STARSHIP_CONFIG not pointing to root config (got: {starship_env})",
            "restart shell or run `source ~/.zshrc`",
        )

    return "ok", f"root profile active ({config_path})", None


class CheckResult(tuple):
    """Result tuple compatible with (status, message, suggestion) and dict-like indexing."""

    def __new__(
        cls,
        status: str,
        message: str,
        suggestion: str | None = None,
        name: str = "headless capabilities",
    ):
        return super().__new__(cls, (status, message, suggestion))

    def __init__(
        self,
        status: str,
        message: str,
        suggestion: str | None = None,
        name: str = "headless capabilities",
    ):
        self.status = status
        self.message = message
        self.suggestion = suggestion
        self.name = name

    def __getitem__(self, item: Any) -> Any:
        if isinstance(item, str):
            if item == "status":
                return self.status
            if item == "message":
                return self.message
            if item == "suggestion":
                return self.suggestion
            if item == "name":
                return self.name
            raise KeyError(item)
        return super().__getitem__(item)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


def _check_headless_capabilities() -> CheckResult:
    """Spec 023 R7: headless clipboard capability detection."""
    # GUI fast path (zero overhead)
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return CheckResult("ok", "GUI session — native clipboard available")

    # Headless path — full detection
    term = os.environ.get("TERM", "unknown")
    term_program = os.environ.get("TERM_PROGRAM", "")

    # Known but needs manual enable or unsupported
    key = term_program or term.split("-")[0]
    if key in ("iTerm.app", "tmux"):
        return CheckResult(
            "warn",
            f"headless — OSC 52 NOT enabled for {key}",
            OSC52_ENABLE_GUIDE.get(key),
        )
    if key == "Apple_Terminal":
        return CheckResult(
            "info",
            "headless — OSC 52 not supported by Apple_Terminal; using pbcopy fallback",
            OSC52_ENABLE_GUIDE.get(key),
        )

    # Env heuristic (fast)
    env_supported = bool(
        os.environ.get("KITTY_WINDOW_ID")
        or os.environ.get("WEZTERM_PANE")
        or os.environ.get("ALACRITTY_WINDOW_ID")
        or os.environ.get("GHOSTTY_RESOURCES_DIR")
        or "kitty" in term
        or "alacritty" in term
        or "wezterm" in term
        or "foot" in term
    )
    if env_supported:
        family = (
            "kitty"
            if "kitty" in term or os.environ.get("KITTY_WINDOW_ID")
            else (
                "wezterm"
                if "wezterm" in term or os.environ.get("WEZTERM_PANE")
                else (
                    "alacritty"
                    if "alacritty" in term or os.environ.get("ALACRITTY_WINDOW_ID")
                    else (
                        "ghostty"
                        if os.environ.get("GHOSTTY_RESOURCES_DIR")
                        else "iTerm2"
                    )
                )
            )
        )
        return CheckResult("ok", f"headless — OSC 52 supported (terminal: {family})")

    if key in OSC52_ENABLE_GUIDE:
        return CheckResult(
            "warn",
            f"headless — OSC 52 NOT enabled for {key}",
            OSC52_ENABLE_GUIDE[key],
        )

    return CheckResult(
        "info",
        f"headless — OSC 52 support unknown (terminal: {term}); file buffer fallback will be used",
    )


def _check_external_tools() -> tuple[str, str, str | None]:
    """Check external tools that emit metrics to ~/.cache/ziro/<tool>/."""
    from core.external_tools import aggregate, discover_tools, read_health, read_metrics

    tools = discover_tools()
    if not tools:
        return "info", "external tools: none configured", None

    summaries = []
    has_error = False
    for tool in tools:
        m = read_metrics(tool)
        agg = aggregate(m)
        h = read_health(tool)
        summary = f"{tool} ({agg['total']} events, {agg['error_count']} errors)"
        if h:
            h_status = h.get("status", "info")
            summary += f", health: {h_status}"
            if h_status == "error":
                has_error = True
        summaries.append(summary)

    status = "warn" if has_error else "ok"
    return status, f"external tools: {' | '.join(summaries)}", None


# Compatibility aliases for prior interfaces
_check_python = _check_python_version
_check_ziro_defer = _check_defer_loaded
_check_paths = _check_tool_paths


def run_checks() -> dict[str, tuple[str, str, str | None]]:
    """Execute all doctor checks and return ordered dict of results."""
    return {
        "Python 3.11+": _check_python_version(),
        "Zsh 5.8+": _check_zsh_version(),
        "Git": _check_git_version(),
        "Starship": _check_starship_version(),
        "boot shim ZIRO_HOME": _check_boot_shim_ziro_home(),
        "boot chain": _check_boot_chain(),
        "compiled (.zwc)": _check_compiled_artifacts(),
        "eval-cache perms": _check_eval_cache_perms(),
        "ghost cache perms": _check_ghost_cache_perms(),
        "runtime commands": _check_runtime_commands(),
        "tool paths": _check_tool_paths(),
        "tool reasons": _check_tool_reasons(),
        "load.toml schema": _check_loadtoml_schema(),
        "ziro-defer": _check_defer_loaded(),
        "defer modules": _check_defer_modules(),
        "external overrides": _check_external_overrides(),
        "legacy config": _check_legacy_config(),
        "theme sharing prerequisites": _check_theme_sharing_prereqs(),
        "legacy ghost cache": _check_legacy_ghost_cache(),
        "ghost cache secrets": _check_ghost_cache_secrets(),
        "root profile": _check_root_profile(),
        "headless capabilities": _check_headless_capabilities(),
        "external tools": _check_external_tools(),
    }


class HealthReport:
    """Neovim checkhealth style modular health reporter."""

    def __init__(self, name: str):
        self.name = name
        self.sections: list[tuple[str, list[dict[str, Any]]]] = []
        self._current_items: list[dict[str, Any]] = []
        self._current_section = ""

    def start_section(self, title: str):
        if self._current_section or self._current_items:
            self.sections.append((self._current_section, self._current_items))
        self._current_section = title
        self._current_items = []

    def ok(self, msg: str):
        self._current_items.append({"status": "ok", "msg": msg})

    def warn(self, msg: str, advice: str | list[str] | None = None):
        adv_list = [advice] if isinstance(advice, str) else (advice or [])
        self._current_items.append({"status": "warn", "msg": msg, "advice": adv_list})

    def error(self, msg: str, advice: str | list[str] | None = None):
        adv_list = [advice] if isinstance(advice, str) else (advice or [])
        self._current_items.append({"status": "error", "msg": msg, "advice": adv_list})

    def info(self, msg: str):
        self._current_items.append({"status": "info", "msg": msg})

    def line(self, msg: str):
        self._current_items.append({"status": "line", "msg": msg})

    def from_tuple(self, res: tuple[str, str, str | None], prefix: str = ""):
        sev, msg, advice = res
        text = f"{prefix}{msg}" if prefix else msg
        if sev == "ok":
            self.ok(text)
        elif sev == "warn":
            self.warn(text, advice)
        elif sev == "error":
            self.error(text, advice)
        else:
            self.info(text)

    def finish(self):
        if self._current_section or self._current_items:
            self.sections.append((self._current_section, self._current_items))
            self._current_section = ""
            self._current_items = []

    def counts(self) -> tuple[int, int, int]:
        errors = sum(1 for _, items in self.sections for i in items if i.get("status") == "error")
        warns = sum(1 for _, items in self.sections for i in items if i.get("status") == "warn")
        oks = sum(1 for _, items in self.sections for i in items if i.get("status") == "ok")
        return errors, warns, oks

    def render(self) -> str:
        self.finish()
        errors, warns, _ = self.counts()
        if errors > 0 and warns > 0:
            badge = f"{errors} ❌, {warns} ⚠️"
        elif errors > 0:
            badge = f"{errors} ❌"
        elif warns > 0:
            badge = f"{warns} ⚠️"
        else:
            badge = "✅"

        sep = "=" * 78
        header_text = f"{self.name}:"
        spaces = max(2, 78 - len(header_text) - len(badge))
        header_line = f"{header_text}{' ' * spaces}{badge}"

        out = [sep, header_line, ""]
        for sec_title, items in self.sections:
            if sec_title:
                out.append(f"{sec_title} ~")
            for item in items:
                st = item.get("status")
                msg = item.get("msg", "")
                advice = item.get("advice", [])
                if st == "ok":
                    out.append(f"- ✅ OK {msg}")
                elif st == "warn":
                    out.append(f"- ⚠️ WARNING {msg}")
                    if advice:
                        out.append("  - ADVICE:")
                        for adv in advice:
                            out.append(f"    - {adv}")
                elif st == "error":
                    out.append(f"- ❌ ERROR {msg}")
                    if advice:
                        out.append("  - ADVICE:")
                        for adv in advice:
                            out.append(f"    - {adv}")
                elif st == "info":
                    out.append(f"- ℹ️ INFO {msg}")
                elif st == "line":
                    out.append(f"- {msg}")
            out.append("")
        return "\n".join(out)


def cmd_doctor(argv: list[str]) -> int:
    from core.help_cli import handle_help_if_requested
    ret = handle_help_if_requested(argv, "doctor")
    if ret is not None:
        return ret

    paths = get_paths()
    reports: list[HealthReport] = []

    # 1. ziro.system
    rep_sys = HealthReport("ziro.system")
    rep_sys.start_section("Core Prerequisites")
    py_res = _check_python_version()
    rep_sys.from_tuple(py_res, prefix=f"Python: {sys.executable} · ")
    zsh_res = _check_zsh_version()
    rep_sys.from_tuple(zsh_res)
    git_res = _check_git_version()
    rep_sys.from_tuple(git_res)
    star_res = _check_starship_version()
    rep_sys.from_tuple(star_res)

    rep_sys.start_section("System Info")
    rep_sys.line(f"Operating system: {platform.system()} {platform.release()} ({platform.machine()})")
    rep_sys.line(f"Shell: {os.environ.get('SHELL', 'unknown')}")
    rep_sys.line(f"$TERM={os.environ.get('TERM', 'unset')!r}")
    if "COLORTERM" in os.environ:
        rep_sys.line(f"$COLORTERM={os.environ.get('COLORTERM')!r}")

    rep_sys.start_section("Paths")
    rep_sys.line(f"$ZIRO_HOME: {paths['home']}")
    rep_sys.line(f"$ZIRO_CONFIG: {paths['config']}")
    rep_sys.line(f"$ZIRO_CACHE: {paths['cache']}")
    rep_sys.line(f"$ZIRO_DATA: {paths['data']}")
    reports.append(rep_sys)

    # 2. ziro.runtime
    rep_run = HealthReport("ziro.runtime")
    rep_run.start_section("Boot Chain")
    rep_run.from_tuple(_check_boot_shim_ziro_home())
    rep_run.from_tuple(_check_boot_chain())

    rep_run.start_section("Runtime Commands & Aliases")
    rep_run.from_tuple(_check_runtime_commands())

    rep_run.start_section("Defer Engine (ziro-defer)")
    rep_run.from_tuple(_check_defer_loaded())
    rep_run.from_tuple(_check_defer_modules())
    reports.append(rep_run)

    # 3. ziro.bytecode
    rep_byte = HealthReport("ziro.bytecode")
    rep_byte.start_section("Compiled Artifacts (.zwc)")
    rep_byte.from_tuple(_check_compiled_artifacts())

    rep_byte.start_section("Eval Caches & Permissions")
    rep_byte.from_tuple(_check_eval_cache_perms())
    rep_byte.from_tuple(_check_ghost_cache_perms())
    rep_byte.from_tuple(_check_ghost_cache_secrets())
    rep_byte.from_tuple(_check_legacy_ghost_cache())
    eval_cache_dir = paths["cache"] / "eval-cache"
    for cache_name in ("starship.zsh", "zcolors.zsh", "zoxide.zsh", "fzf.zsh"):
        cp = eval_cache_dir / cache_name
        zwc = Path(str(cp) + ".zwc")
        if cp.is_file():
            zwc_note = " (compiled .zwc)" if zwc.is_file() else ""
            rep_byte.ok(f"{cache_name}{zwc_note}")
        else:
            rep_byte.info(f"{cache_name} (not present / optional cache)")
    reports.append(rep_byte)

    # 4. ziro.config
    rep_cfg = HealthReport("ziro.config")
    rep_cfg.start_section("Manifest & Schema (load.toml)")
    rep_cfg.from_tuple(_check_loadtoml_schema())
    rep_cfg.from_tuple(_check_tool_reasons())

    rep_cfg.start_section("Tool Paths")
    rep_cfg.from_tuple(_check_tool_paths())

    rep_cfg.start_section("Overrides & Legacy")
    rep_cfg.from_tuple(_check_external_overrides())
    rep_cfg.from_tuple(_check_legacy_config())

    rep_cfg.start_section("Root Profile Hardening")
    rep_cfg.from_tuple(_check_root_profile())
    reports.append(rep_cfg)

    # 5. ziro.tools
    rep_tools = HealthReport("ziro.tools")
    rep_tools.start_section("Manual Page")
    man_path = Path.home() / ".local" / "share" / "man" / "man1" / "ziro.1"
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        man_path = Path(xdg_data) / "man" / "man1" / "ziro.1"
    if man_path.is_file():
        rep_tools.ok(f"ziro(1) manual installed ({man_path})")
    else:
        rep_tools.warn(
            f"ziro(1) manual not installed at {man_path}",
            ["Run: ziro install --rebuild"],
        )

    pm = _detect_pkg_manager()
    rep_tools.start_section("Recommended Companions")
    recommended = [
        ("zoxide", "smart directory jump (`z`)", "curl -sSfL https://raw.githubusercontent.com/ajeetdsouza/zoxide/main/install.sh | sh"),
        ("fzf", "fuzzy finder for history & files", "install via package manager"),
        ("eza", "modern ls/lt replacement with icons", "install via package manager"),
    ]
    for bin_name, desc, default_install in recommended:
        p = shutil.which(bin_name)
        if not p:
            local_bin = Path.home() / ".local" / "bin" / bin_name
            if local_bin.is_file() and os.access(local_bin, os.X_OK):
                p = str(local_bin)
        if p:
            try:
                r = subprocess.run([p, "--version"], capture_output=True, text=True, timeout=5)
                v = r.stdout.splitlines()[0] if r.stdout else p
                rep_tools.ok(f"{v} ({p})")
            except Exception:
                rep_tools.ok(f"{bin_name} ({p})")
        else:
            if pm == "pacman":
                adv = f"sudo pacman -S --needed {bin_name}"
            elif pm == "apt-get":
                adv = f"sudo apt install -y {bin_name}"
            elif pm == "brew":
                adv = f"brew install {bin_name}"
            elif pm == "dnf":
                adv = f"sudo dnf install -y {bin_name}"
            else:
                adv = default_install
            rep_tools.warn(
                f"{bin_name} not found ({desc})",
                [adv],
            )

    rep_tools.start_section("Optional CLI Helpers")
    optional_helpers = [
        ("bat", "modern cat replacement with syntax highlighting"),
        ("rg", "ripgrep fast grep replacement"),
        ("fd", "fast user-friendly find replacement"),
    ]
    for bin_name, desc in optional_helpers:
        p = shutil.which(bin_name)
        if not p:
            local_bin = Path.home() / ".local" / "bin" / bin_name
            if local_bin.is_file() and os.access(local_bin, os.X_OK):
                p = str(local_bin)
        if p:
            try:
                r = subprocess.run([p, "--version"], capture_output=True, text=True, timeout=5)
                v = r.stdout.splitlines()[0] if r.stdout else p
                rep_tools.ok(f"{v} ({p})")
            except Exception:
                rep_tools.ok(f"{bin_name} ({p})")
        else:
            rep_tools.info(f"{bin_name} not found (optional: {desc})")

    clip_tools = ["wl-copy", "xclip", "xsel", "pbcopy", "clip.exe"]
    found_clip = [c for c in clip_tools if shutil.which(c)]
    if found_clip:
        rep_tools.ok(f"clipboard tool found: {found_clip[0]}")
    else:
        rep_tools.info(f"no clipboard tool found ({', '.join(clip_tools)})")
    rep_tools.from_tuple(_check_headless_capabilities(), prefix="headless capabilities: ")

    rep_tools.start_section("Theme Sharing Prerequisites")
    theme_res = _check_theme_sharing_prereqs()
    rep_tools.from_tuple(theme_res)

    rep_tools.start_section("External Tools Observability")
    ext_res = _check_external_tools()
    rep_tools.from_tuple(ext_res)
    reports.append(rep_tools)

    # Header banner matching Neovim checkhealth
    print("==============================================================================")
    print("ziro doctor: checkhealth")
    for rep in reports:
        print(rep.render())

    total_errors = sum(r.counts()[0] for r in reports)
    total_warns = sum(r.counts()[1] for r in reports)
    total_oks = sum(r.counts()[2] for r in reports)

    print("==============================================================================")
    print(f"Summary: {total_oks} passed, {total_warns} warning(s), {total_errors} error(s)")
    if total_errors > 0:
        print("Result:  ❌ UNHEALTHY")
        return 1
    elif total_warns > 0:
        print("Result:  ⚠️  HEALTHY WITH WARNINGS")
        return 0
    else:
        print("Result:  ✅ HEALTHY")
        return 0


def main(argv: list[str] | None = None) -> int:
    return cmd_doctor(sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
