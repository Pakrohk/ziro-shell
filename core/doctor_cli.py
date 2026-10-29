"""ziro-shell — doctor command (health check).

Layer: 3 (Python core, cold-path only)
Spec: 006 SC-1 / Section 4 closeout / 4-E Comprehensive Rebuild
"""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

from core.paths import get_paths


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
    except Exception as e:
        return "error", f"error inspecting boot chain timestamps: {e}", "run `ziro sync`"

    return "ok", "boot chain complete and fresh (boot.zsh → ziro-boot.zwc)", None


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


# Compatibility aliases for prior interfaces
_check_python = _check_python_version
_check_ziro_defer = _check_defer_loaded
_check_paths = _check_tool_paths


def run_checks() -> dict[str, tuple[str, str, str | None]]:
    """Execute all doctor checks and return ordered dict of results."""
    return {
        "Python 3.11+": _check_python_version(),
        "Zsh 5.8+": _check_zsh_version(),
        "boot chain": _check_boot_chain(),
        "compiled (.zwc)": _check_compiled_artifacts(),
        "tool paths": _check_tool_paths(),
        "tool reasons": _check_tool_reasons(),
        "load.toml schema": _check_loadtoml_schema(),
        "ziro-defer": _check_defer_loaded(),
        "defer modules": _check_defer_modules(),
        "external overrides": _check_external_overrides(),
        "legacy config": _check_legacy_config(),
    }


def cmd_doctor(argv: list[str]) -> int:
    from core.help_cli import handle_help_if_requested
    ret = handle_help_if_requested(argv, "doctor")
    if ret is not None:
        return ret

    verbose = "--verbose" in argv or "-v" in argv
    print("ziro doctor")
    print("=" * 50)

    results = run_checks()

    emoji_map = {
        "ok": "✅",
        "warn": "⚠️",
        "error": "❌",
        "info": "ℹ️",
    }

    errors = 0
    warnings = 0
    passed = 0

    for name, result in results.items():
        severity = result[0]
        msg = result[1]
        action = result[2] if len(result) > 2 else None

        icon = emoji_map.get(severity, "•")
        if severity == "error":
            errors += 1
        elif severity == "warn":
            warnings += 1
        elif severity == "ok":
            passed += 1

        if verbose or severity in ("warn", "error"):
            print(f" {icon} {name:25s} {msg}")
        else:
            print(f" {icon} {name:25s}")

        if action and (severity in ("warn", "error") or verbose):
            print(f"    → {action}")

    print()
    if errors > 0:
        print(f"❌ unhealthy: {errors} error(s), {warnings} warning(s)")
        return 1
    elif warnings > 0:
        print(f"⚠️  healthy with {warnings} warning(s) ({passed} checks passed)")
        return 0
    else:
        print(f"✅ healthy ({passed} checks passed)")
        return 0


def main(argv: list[str] | None = None) -> int:
    return cmd_doctor(sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
