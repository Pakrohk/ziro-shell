"""ziro-shell — theme provider (T2).

Layer: 3 (Python core, cold-path only)
Spec: 006 R6
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


COMPONENTS = ("prompt", "auto_suggest", "colors", "syntax_highlighting")


@dataclass(frozen=True)
class ThemeSelection:
    """Active theme per component."""
    prompt: str = "powerline"
    prompt_component: str = "starship"
    auto_suggest: str = "default"
    auto_suggest_component: str = "ziro-ghost"
    colors: str = "default"
    syntax_highlighting: str = "default"


def _theme_conf_path(config_dir: Path) -> Path:
    return config_dir / ".theme.conf"


def read_theme_conf(config_dir: Path) -> ThemeSelection:
    """Read .theme.conf (hand-rolled minimal TOML)."""
    path = _theme_conf_path(config_dir)
    if not path.is_file():
        return ThemeSelection()
    data: dict[str, str] = {}
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("["):
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            data[key.strip()] = val.strip().strip('"')
    except OSError:
        return ThemeSelection()
    return ThemeSelection(
        prompt=data.get("prompt", "powerline"),
        prompt_component=data.get("prompt_component", "starship"),
        auto_suggest=data.get("auto_suggest", "default"),
        auto_suggest_component=data.get("auto_suggest_component", "ziro-ghost"),
        colors=data.get("colors", "default"),
        syntax_highlighting=data.get("syntax_highlighting", "default"),
    )


def write_theme_conf(config_dir: Path, sel: ThemeSelection) -> None:
    """Write .theme.conf (deterministic order)."""
    config_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "[themes]",
        f'prompt = "{sel.prompt}"',
        f'prompt_component = "{sel.prompt_component}"',
        f'auto_suggest = "{sel.auto_suggest}"',
        f'auto_suggest_component = "{sel.auto_suggest_component}"',
        f'colors = "{sel.colors}"',
        f'syntax_highlighting = "{sel.syntax_highlighting}"',
        "",
    ]
    _theme_conf_path(config_dir).write_text("\n".join(lines))


def list_themes(themes_dir: Path, component: str, include_starship_presets: bool = False) -> list[str]:
    """List available themes for component."""
    themes: set[str] = set()
    comp_dir = themes_dir / component
    if comp_dir.is_dir():
        for p in comp_dir.iterdir():
            if p.is_file() and not p.name.startswith("."):
                themes.add(p.stem)

    # Optionally include built-in starship presets if available
    if component == "prompt" and include_starship_presets:
        import shutil
        import subprocess
        if shutil.which("starship"):
            try:
                res = subprocess.run(["starship", "preset", "--list"], capture_output=True, text=True, timeout=2)
                if res.returncode == 0:
                    for line in res.stdout.splitlines():
                        preset = line.strip()
                        if preset:
                            themes.add(preset)
            except Exception:
                pass

    return sorted(themes)




def theme_path(themes_dir: Path, component: str, name: str) -> Path:
    """Return path to specific theme (may not exist)."""
    # Try common extensions
    for ext in ("", ".toml", ".zsh", ".omp.json"):
        candidate = themes_dir / component / (name + ext)
        if candidate.is_file():
            return candidate
    return themes_dir / component / name


__all__ = [
    "COMPONENTS",
    "ThemeSelection",
    "read_theme_conf",
    "write_theme_conf",
    "list_themes",
    "theme_path",
]
