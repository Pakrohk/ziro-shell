"""ziro-shell — config command.

Layer: 3 (Python core, cold-path only)
Spec: 006 R4
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from core.paths import _ensure_secure_perms


def _config_dir() -> Path:
    base = os.environ.get("ZIRO_CONFIG")
    if base:
        return Path(base)
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "ziro"


def cmd_show(argv: list[str]) -> int:
    from core.help_cli import handle_help_if_requested
    ret = handle_help_if_requested(argv, "config", subcommand="show")
    if ret is not None:
        return ret
    cfg = _config_dir()
    print(f"config dir: {cfg}")
    print()
    for name in ("defaults.toml", "tools.toml", ".theme.conf", "prompt.conf"):
        p = cfg / name
        status = "✅" if p.is_file() else "❌ (missing)"
        print(f" {name:20s} {status}")
    return 0


def cmd_edit(argv: list[str]) -> int:
    from core.help_cli import handle_help_if_requested
    ret = handle_help_if_requested(argv, "config", subcommand="edit")
    if ret is not None:
        return ret
    cfg = _config_dir()
    target = argv[0] if argv else "defaults.toml"
    path = cfg / target
    if not path.is_file():
        print(f"config file not found: {path}", file=sys.stderr)
        return 1
    editor = os.environ.get("EDITOR", "vi")
    print(f"opening {path} with {editor}")
    if not sys.stdin.isatty():
        print("(non-tty; not launching editor)", file=sys.stderr)
        return 0
    try:
        subprocess.run([editor, str(path)])
    except FileNotFoundError:
        print(f"editor not found: {editor}", file=sys.stderr)
        return 1
    return 0


KNOWN_CATEGORIES = {
    "prompt",
    "auto_suggest",
    "navigation",
    "ui",
    "plugins",
    "theme",
    "version",
}

VALID_PROMPTS = {"starship", "powerlevel10k", "p10k", "pure", "none"}
VALID_SUGGEST = {"ziro-ghost", "zsh-autosuggestions", "none"}


def cmd_set(argv: list[str]) -> int:
    from core.help_cli import handle_help_if_requested
    ret = handle_help_if_requested(argv, "config", subcommand="set")
    if ret is not None:
        return ret

    if len(argv) < 2:
        print("usage: config set <category.key> <value>", file=sys.stderr)
        return 2

    key_arg, value_arg = argv[0], argv[1]
    if "." in key_arg:
        category, subkey = key_arg.split(".", 1)
    else:
        category, subkey = key_arg, "default"

    if category not in KNOWN_CATEGORIES:
        print(f"error: unknown configuration category '{category}'", file=sys.stderr)
        print(f"available categories: {', '.join(sorted(KNOWN_CATEGORIES))}", file=sys.stderr)
        return 2

    # Value validation
    if category == "prompt" and value_arg.lower() not in VALID_PROMPTS:
        print(f"error: unsupported prompt value '{value_arg}'", file=sys.stderr)
        print(f"supported: {', '.join(sorted(VALID_PROMPTS))}", file=sys.stderr)
        return 2

    if category == "auto_suggest" and value_arg.lower() not in VALID_SUGGEST:
        print(f"error: unsupported auto_suggest value '{value_arg}'", file=sys.stderr)
        print(f"supported: {', '.join(sorted(VALID_SUGGEST))}", file=sys.stderr)
        return 2

    if category == "ui" and subkey == "rich" and value_arg.lower() not in ("true", "false", "1", "0"):
        print(f"error: invalid boolean value '{value_arg}' for ui.rich", file=sys.stderr)
        return 2

    cfg = _config_dir()
    cfg.mkdir(parents=True, exist_ok=True)
    _ensure_secure_perms(cfg)
    defaults_path = cfg / "defaults.toml"

    import tomllib
    data: dict = {}
    if defaults_path.is_file():
        try:
            with defaults_path.open("rb") as f:
                data = tomllib.load(f)
        except Exception:
            data = {}

    old_val = data.get(category, {}).get(subkey, "<none>")
    if category not in data or not isinstance(data[category], dict):
        data[category] = {}

    if value_arg.lower() in ("true", "false"):
        val_to_save: bool | str = (value_arg.lower() == "true")
    else:
        val_to_save = value_arg

    data[category][subkey] = val_to_save

    # Write out defaults.toml
    lines = [
        "# ziro-shell — user defaults",
        "# Editable by hand. Regenerated only on `ziro config reset`.",
        "# Layer: 0 (config) · Spec: 006 · AUTO-GENERATED: no",
        "",
    ]
    for cat, section in data.items():
        if isinstance(section, dict):
            lines.append(f"[{cat}]")
            for k, v in section.items():
                if isinstance(v, bool):
                    lines.append(f"{k} = {'true' if v else 'false'}")
                elif isinstance(v, int):
                    lines.append(f"{k} = {v}")
                else:
                    lines.append(f'{k} = "{v}"')
            lines.append("")

    defaults_path.write_text("\n".join(lines))
    _ensure_secure_perms(defaults_path)
    print(f"✅ config updated: {category}.{subkey}: {old_val} -> {value_arg}")

    # Regenerate if affecting shell loading
    if category in ("plugins", "prompt", "auto_suggest"):
        try:
            from core.regenerate import regenerate
            ziro_home = Path(os.environ.get("ZIRO_HOME", Path.home() / ".ziro"))
            plugins_dir = ziro_home / "plugins"
            plugin_dirs: list[tuple[Path, str]] = []
            if plugins_dir.is_dir():
                plugin_dirs = [
                    (p, p.name)
                    for p in plugins_dir.iterdir()
                    if p.is_dir() and not p.name.startswith(".")
                ]
            res = regenerate(cfg, plugin_dirs, trigger="manual")
            print(f"✅ regenerated: {res.output}")
        except Exception:
            pass

    return 0


def main(argv: list[str]) -> int:
    from core.help_cli import handle_help_if_requested
    ret = handle_help_if_requested(argv, "config")
    if ret is not None:
        return ret
    if not argv:
        print("usage: config <show|edit|set>", file=sys.stderr)
        return 2
    sub, rest = argv[0], argv[1:]
    handlers = {
        "show": cmd_show,
        "edit": cmd_edit,
        "set": cmd_set,
    }
    handler = handlers.get(sub)
    if handler is None:
        print(f"unknown config subcommand: {sub}", file=sys.stderr)
        return 2
    return handler(rest)


__all__ = ["main"]
