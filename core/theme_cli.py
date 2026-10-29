"""ziro-shell — theme CLI subcommands.

Layer: 3 (Python core, cold-path only)
Spec: 006 R4
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from core.theme import (
    COMPONENTS, ThemeSelection,
    list_themes, read_theme_conf, theme_path, write_theme_conf,
)


def _config_dir() -> Path:
    base = os.environ.get("ZIRO_CONFIG")
    if base:
        return Path(base)
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "ziro"


def _themes_dir() -> Path:
    home = os.environ.get("ZIRO_HOME", Path.home() / ".ziro")
    return Path(home) / "themes"


def cmd_list(argv: list[str]) -> int:
    from core.help_cli import handle_help_if_requested
    ret = handle_help_if_requested(argv, "theme", subcommand="list")
    if ret is not None:
        return ret
    component = "prompt"
    if "--component" in argv:
        idx = argv.index("--component")
        if idx + 1 < len(argv):
            component = argv[idx + 1]
    themes = list_themes(_themes_dir(), component, include_starship_presets=True)
    if not themes:
        print(f"(no themes for component: {component})")
        return 0
    from core.rich_helpers import render_columns
    if not render_columns(themes):
        for name in themes:
            print(name)
    return 0


def cmd_current(argv: list[str]) -> int:
    from core.help_cli import handle_help_if_requested
    ret = handle_help_if_requested(argv, "theme", subcommand="current")
    if ret is not None:
        return ret
    sel = read_theme_conf(_config_dir())
    print(f"prompt: {sel.prompt} ({sel.prompt_component})")
    print(f"auto_suggest: {sel.auto_suggest} ({sel.auto_suggest_component})")
    print(f"colors: {sel.colors}")
    print(f"syntax_highlighting: {sel.syntax_highlighting}")
    return 0


def cmd_apply(argv: list[str]) -> int:
    from core.help_cli import handle_help_if_requested
    ret = handle_help_if_requested(argv, "theme", subcommand="apply")
    if ret is not None:
        return ret
    if not argv:
        print("usage: theme apply <name> [--component <comp>]", file=sys.stderr)
        return 2
    name = argv[0]
    component = "prompt"
    if "--component" in argv:
        idx = argv.index("--component")
        if idx + 1 < len(argv):
            component = argv[idx + 1]
    if component not in COMPONENTS:
        print(f"unknown component: {component}", file=sys.stderr)
        return 2

    cfg = _config_dir()
    sel = read_theme_conf(cfg)
    data = {
        "prompt": sel.prompt,
        "prompt_component": sel.prompt_component,
        "auto_suggest": sel.auto_suggest,
        "auto_suggest_component": sel.auto_suggest_component,
        "colors": sel.colors,
        "syntax_highlighting": sel.syntax_highlighting,
    }
    data[component] = name
    sel = ThemeSelection(**data)
    write_theme_conf(cfg, sel)

    # If applying a prompt theme and prompt_component is starship, apply preset/file to starship.toml
    if component == "prompt" and sel.prompt_component == "starship":
        _apply_starship_preset_or_file(name, _themes_dir())

    print(f"applied: {component} = {name}")
    return 0


def _apply_starship_preset_or_file(name: str, themes_dir: Path) -> bool:
    """Apply a prompt theme to ~/.config/starship.toml."""
    import shutil
    import subprocess
    starship_toml = Path(os.environ.get("STARSHIP_CONFIG", Path.home() / ".config" / "starship.toml"))
    starship_toml.parent.mkdir(parents=True, exist_ok=True)

    # 1. Check local file in themes/prompt/<name>.toml
    src_file = theme_path(themes_dir, "prompt", name)
    if src_file.is_file():
        try:
            shutil.copy2(src_file, starship_toml)
            return True
        except Exception:
            pass

    # 2. Try starship preset CLI
    if shutil.which("starship"):
        try:
            res = subprocess.run(["starship", "preset", name, "-o", str(starship_toml)], capture_output=True, text=True, timeout=3)
            return res.returncode == 0
        except Exception:
            pass
    return False


def cmd_edit(argv: list[str]) -> int:
    """Edit active prompt theme (or specified starship/theme config)."""
    from core.help_cli import handle_help_if_requested
    ret = handle_help_if_requested(argv, "theme", subcommand="edit")
    if ret is not None:
        return ret

    target_file = Path(os.environ.get("STARSHIP_CONFIG", Path.home() / ".config" / "starship.toml"))
    if argv:
        target_name = argv[0]
        custom_file = theme_path(_themes_dir(), "prompt", target_name)
        if custom_file.is_file():
            target_file = custom_file

    if not target_file.is_file():
        # Create minimal fallback if missing
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("# Starship theme configuration\n", encoding="utf-8")

    editor = os.environ.get("EDITOR", "vi")
    print(f"opening {target_file} with {editor}")
    if not sys.stdin.isatty():
        print("(non-tty; not launching editor)", file=sys.stderr)
        return 0
    try:
        import subprocess
        subprocess.run([editor, str(target_file)])
    except FileNotFoundError:
        print(f"editor not found: {editor}", file=sys.stderr)
        return 1
    return 0



def cmd_reset(argv: list[str]) -> int:
    from core.help_cli import handle_help_if_requested
    ret = handle_help_if_requested(argv, "theme", subcommand="reset")
    if ret is not None:
        return ret
    cfg = _config_dir()
    write_theme_conf(cfg, ThemeSelection())
    print("theme reset to defaults")
    return 0


def main(argv: list[str]) -> int:
    from core.help_cli import handle_help_if_requested
    ret = handle_help_if_requested(argv, "theme")
    if ret is not None:
        return ret
    if not argv:
        print("usage: theme <list|current|apply|edit|reset>", file=sys.stderr)
        return 2
    sub, rest = argv[0], argv[1:]
    handlers = {
        "list": cmd_list,
        "current": cmd_current,
        "apply": cmd_apply,
        "edit": cmd_edit,
        "reset": cmd_reset,
    }
    handler = handlers.get(sub)
    if handler is None:
        print(f"unknown theme subcommand: {sub}", file=sys.stderr)
        return 2
    return handler(rest)



__all__ = ["main"]
