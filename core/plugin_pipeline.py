"""ziro-shell — plugin pipeline (clone + analyze + generate).

Layer: 3 (Python core, cold-path only)
Spec: 001 FR-001 + 002 R5 + 003
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from core.analyzer import analyze_with_cache
from core.generator import EmitOptions, default_output_path, generate
from core.resolver import ConflictError, resolve
from core.tags import save_plugin_tags


@dataclass(frozen=True)
class AddResult:
    plugin: str
    plugin_dir: Path
    strategy: str
    generated: Path
    dry_run: bool = False
    skipped_clone: bool = False


def _plugins_root(ziro_home: Path) -> Path:
    return ziro_home / "plugins"


def _clone_repo(source: str, dest: Path, dry_run: bool) -> bool:
    """Clone or copy plugin repo. Returns True if cloned/copied, False if existed."""
    if dest.is_dir():
        return False
    if dry_run:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)

    src_p = Path(source).expanduser()
    if src_p.is_dir():
        if (src_p / ".git").is_dir():
            cmd = ["git", "clone", "--depth=1", str(src_p.resolve()), str(dest)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                raise RuntimeError(f"git clone failed: {result.stderr.strip()}")
            return True
        else:
            shutil.copytree(src_p, dest)
            return True
    elif src_p.is_file():
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_p, dest / src_p.name)
        return True

    result = subprocess.run(
        ["git", "clone", "--depth=1", source, str(dest)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git clone failed: {result.stderr.strip()}")
    return True


def add_plugin(
    source: str,
    *,
    name: str = "",
    subpath: str = "",
    tags: list[str] | None = None,
    ziro_home: Path | None = None,
    config_dir: Path | None = None,
    all_configs: list | None = None,
    dry_run: bool = False,
    is_local: bool = False,
) -> AddResult:
    """Full pipeline: clone → analyze → resolve → regenerate."""
    ziro_home = ziro_home or Path.home() / ".ziro"
    config_dir = config_dir or Path.home() / ".config" / "ziro"
    tags = tags or []
    all_configs = all_configs or []

    if subpath:
        sub_name = subpath.rstrip("/").split("/")[-1]
        plugin_name = name or sub_name
        repo_name = source.rstrip("/").split("/")[-1].removesuffix(".git")
        dest_base = _plugins_root(ziro_home) / (name if name and name != sub_name else repo_name)
        dest = dest_base / subpath
    else:
        plugin_name = name or source.rstrip("/").split("/")[-1].removesuffix(".git")
        dest_base = _plugins_root(ziro_home) / plugin_name
        dest = dest_base

    # 1. Clone or copy
    if is_local:
        src_p = Path(source).expanduser()
        if not dry_run:
            dest.mkdir(parents=True, exist_ok=True)
            if src_p.is_file():
                shutil.copy2(src_p, dest / src_p.name)
            elif src_p.is_dir():
                if (src_p / ".git").is_dir():
                    subprocess.run(["git", "clone", "--depth=1", str(src_p.resolve()), str(dest)], check=True, capture_output=True)
                else:
                    shutil.copytree(src_p, dest, dirs_exist_ok=True)
        skipped = False
    else:
        skipped = not _clone_repo(source, dest_base, dry_run)

    # 2. Save tags (if any)
    if tags and not dry_run:
        save_plugin_tags(config_dir, plugin_name, tags)

    # 3. Analyze
    if not dest.is_dir():
        if is_local:
            src_p = Path(source).expanduser()
            if src_p.exists():
                analysis_target = src_p.parent if src_p.is_file() else src_p
                analysis = analyze_with_cache(analysis_target, plugin_name)
            else:
                from core.models import AnalysisResult
                analysis = AnalysisResult.empty(plugin_name, source)
        else:
            from core.models import AnalysisResult
            analysis = AnalysisResult.empty(plugin_name, source)
    else:
        analysis = analyze_with_cache(dest, plugin_name)

    # 4. Resolve
    try:
        resolved = resolve(analysis, config_dir)
    except ConflictError as e:
        raise RuntimeError(f"tag conflict: {e}") from e

    # 5. Regenerate plugins.gen.zsh (preserve factory tools and avoid duplicates)
    generated = default_output_path(config_dir)
    configs = [c for c in all_configs if getattr(c, "plugin", "") != plugin_name] + [resolved]
    if not dry_run:
        generate(configs, generated, options=EmitOptions(enforce_order=True))

    return AddResult(
        plugin=plugin_name,
        plugin_dir=dest,
        strategy=resolved.strategy.value if hasattr(resolved.strategy, "value") else str(resolved.strategy),
        generated=generated,
        dry_run=dry_run,
        skipped_clone=skipped,
    )


def remove_plugin(
    name: str,
    *,
    ziro_home: Path | None = None,
    config_dir: Path | None = None,
    all_configs: list | None = None,
    dry_run: bool = False,
) -> bool:
    """Remove plugin dir + tags + regenerate. Returns True if removed."""
    ziro_home = ziro_home or Path.home() / ".ziro"
    config_dir = config_dir or Path.home() / ".config" / "ziro"
    all_configs = all_configs or []

    dest = _plugins_root(ziro_home) / name
    if not dest.is_dir():
        return False
    if dry_run:
        return True

    # Remove plugin dir
    shutil.rmtree(dest, ignore_errors=True)

    # Remove tag file
    tag_file = config_dir / "tags" / "plugins" / f"{name}.toml"
    if tag_file.is_file():
        tag_file.unlink()

    # Regenerate without this plugin
    configs = [c for c in all_configs if c.plugin != name]
    if configs:
        generate(configs, default_output_path(config_dir), options=EmitOptions(enforce_order=True))

    return True


__all__ = ["AddResult", "add_plugin", "remove_plugin"]
