"""ziro-shell — unified Cyclopts CLI application.

Layer: 3 (Python core, cold-path only)
Spec: 013 (CLI Modernization with Cyclopts Declarative Framework)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from cyclopts import App

from core.constants import VERSION

COMMANDS: tuple[str, ...] = (
    "analyze",
    "bench",
    "completion",
    "config",
    "doctor",
    "install",
    "plugin",
    "prompt",
    "suggest",
    "sync",
    "tag",
    "theme",
    "update",
)

app = App(
    name="ziro",
    help="Fast, layered Zsh runtime customization",
    version=f"ziro-shell v{VERSION}",
    version_flags=["--version", "-v"],
    group_commands="Commands:",
)


@app.command
def help(*tokens: str) -> int:
    """Show help documentation for ziro or a specific command."""
    from core import help_cli
    return help_cli.cmd_help(list(tokens))


@app.command
def doctor(verbose: bool = False) -> int:
    """Run full system health checks on runtime, bytecode, and dependencies."""
    from core import doctor_cli
    args = ["--verbose"] if verbose else []
    return doctor_cli.cmd_doctor(args)


@app.command
def sync(
    rebuild_caches: bool = False,
    force: bool = False,
    no_strict_zwc: bool = False,
    config: Optional[Path] = None,
) -> int:
    """Synchronize configuration, compile bytecode artifacts, and validate freshness."""
    from core import build
    args: list[str] = []
    if rebuild_caches:
        args.append("--rebuild-caches")
    if force:
        args.append("--force")
    if no_strict_zwc:
        args.append("--no-strict-zwc")
    if config:
        args.extend(["--config", str(config)])
    return build.main(args)


@app.command
def analyze(
    tool: Optional[str] = None,
    full: bool = False,
    dry_run: bool = False,
) -> int:
    """Analyze tools and generate or audit load.toml configuration."""
    from core import analyze_cli
    args: list[str] = []
    if full:
        args.append("--full")
    if dry_run:
        args.append("--dry-run")
    if tool:
        args.append(tool)
    return analyze_cli.main(args)


@app.command
def update(
    check: bool = False,
    force: bool = False,
    dev: bool = False,
    dry_run: bool = False,
    yes: bool = False,
    plugins_only: bool = False,
    sync_only: bool = False,
    no_analyze: bool = False,
    plugin: Optional[str] = None,
    quiet: bool = False,
) -> int:
    """Update ziro repository, plugins, and recompile runtime artifacts."""
    from core import update_cli
    args: list[str] = []
    if check:
        args.append("--check")
    if force:
        args.append("--force")
    if dev:
        args.append("--dev")
    if dry_run:
        args.append("--dry-run")
    if yes:
        args.append("--yes")
    if plugins_only:
        args.append("--plugins-only")
    if sync_only:
        args.append("--sync-only")
    if no_analyze:
        args.append("--no-analyze")
    if quiet:
        args.append("--quiet")
    if plugin:
        args.extend(["--plugin", plugin])
    return update_cli.main(args)


# ---------------------------------------------------------------------------
# Subcommand group: plugin
# ---------------------------------------------------------------------------
plugin_app = App(name="plugin", help="Manage shell plugins (install, remove, list, inspect)", group_commands="Subcommands:")
app.command(plugin_app)


@plugin_app.command(name="list")
def plugin_list(names: bool = False, raw: bool = False) -> int:
    """List installed plugins with stage, method, and status."""
    from core import plugin_cli
    args: list[str] = []
    if names or raw:
        args.append("--names")
    return plugin_cli.cmd_list(args)


@plugin_app.command(name="show")
def plugin_show(name: str) -> int:
    """Show detailed metadata and files for an installed plugin."""
    from core import plugin_cli
    return plugin_cli.cmd_show([name])


@plugin_app.command(name="remove")
def plugin_remove(name: str, dry_run: bool = False) -> int:
    """Remove an installed plugin and its configuration tags."""
    from core import plugin_cli
    args: list[str] = []
    if dry_run:
        args.append("--dry-run")
    args.append(name)
    return plugin_cli.cmd_remove(args)


@plugin_app.command(name="add")
def plugin_add(*tokens: str) -> int:
    """Add a plugin from git source, local path, or catalog with tags."""
    from core import plugin_cli
    return plugin_cli.cmd_add(list(tokens))


# ---------------------------------------------------------------------------
# Subcommand group: tag
# ---------------------------------------------------------------------------
tag_app = App(name="tag", help="Manage tags assigned to plugins and tools", group_commands="Subcommands:")
app.command(tag_app)


@tag_app.command(name="list")
def tag_list() -> int:
    """List all available and user-defined tags."""
    from core import tag_cli
    return tag_cli.cmd_list([])


@tag_app.command(name="show")
def tag_show(name: str) -> int:
    """Show tags assigned to a specific plugin or tool."""
    from core import tag_cli
    return tag_cli.cmd_show([name])


@tag_app.command(name="add")
def tag_add(name: str, tag: str) -> int:
    """Add a tag to a plugin or tool."""
    from core import tag_cli
    return tag_cli.cmd_add([name, tag])


@tag_app.command(name="remove")
def tag_remove(name: str, tag: str) -> int:
    """Remove a tag from a plugin or tool."""
    from core import tag_cli
    return tag_cli.cmd_remove([name, tag])


@tag_app.command(name="reset")
def tag_reset(name: str) -> int:
    """Reset tags for a plugin or tool to defaults."""
    from core import tag_cli
    return tag_cli.cmd_reset([name])


@tag_app.command(name="define")
def tag_define(tag: str, description: Optional[str] = None) -> int:
    """Define a custom tag with optional description."""
    from core import tag_cli
    args = [tag]
    if description:
        args.append(description)
    return tag_cli.cmd_define(args)


# ---------------------------------------------------------------------------
# Subcommand group: suggest
# ---------------------------------------------------------------------------
suggest_app = App(name="suggest", help="Manage autosuggestion provider (ziro-ghost, zsh-autosuggestions, none)", group_commands="Subcommands:")
app.command(suggest_app)


@suggest_app.command(name="list")
def suggest_list() -> int:
    """List available autosuggestion options."""
    from core import suggest_cli
    return suggest_cli.cmd_list([])


@suggest_app.command(name="set")
def suggest_set(name: str) -> int:
    """Set the active autosuggestion provider."""
    from core import suggest_cli
    return suggest_cli.cmd_set([name])


@suggest_app.command(name="disable")
def suggest_disable() -> int:
    """Disable autosuggestions."""
    from core import suggest_cli
    return suggest_cli.cmd_disable([])


# ---------------------------------------------------------------------------
# Subcommand group: theme
# ---------------------------------------------------------------------------
theme_app = App(name="theme", help="Manage shell themes and appearance", group_commands="Subcommands:")
app.command(theme_app)


@theme_app.command(name="list")
def theme_list(component: Optional[str] = None) -> int:
    """List available theme presets and components."""
    from core import theme_cli
    args: list[str] = []
    if component:
        args.extend(["--component", component])
    return theme_cli.cmd_list(args)


@theme_app.command(name="current")
def theme_current() -> int:
    """Show currently active theme selection."""
    from core import theme_cli
    return theme_cli.cmd_current([])


@theme_app.command(name="apply")
def theme_apply(name: str, component: Optional[str] = None) -> int:
    """Apply a theme preset or component style."""
    from core import theme_cli
    args = [name]
    if component:
        args.extend(["--component", component])
    return theme_cli.cmd_apply(args)


@theme_app.command(name="reset")
def theme_reset() -> int:
    """Reset theme configuration to defaults."""
    from core import theme_cli
    return theme_cli.cmd_reset([])


# ---------------------------------------------------------------------------
# Subcommand group: prompt
# ---------------------------------------------------------------------------
prompt_app = App(name="prompt", help="Manage shell prompt style and engine", group_commands="Subcommands:")
app.command(prompt_app)


@prompt_app.command(name="list")
def prompt_list() -> int:
    """List available prompt engines."""
    from core import prompt_cli
    return prompt_cli.cmd_list([])


@prompt_app.command(name="current")
def prompt_current() -> int:
    """Show currently configured prompt."""
    from core import prompt_cli
    return prompt_cli.cmd_current([])


@prompt_app.command(name="set")
def prompt_set(name: str) -> int:
    """Set the active prompt engine."""
    from core import prompt_cli
    return prompt_cli.cmd_set([name])


# ---------------------------------------------------------------------------
# Subcommand group: config
# ---------------------------------------------------------------------------
config_app = App(name="config", help="Inspect and modify Ziro user configuration", group_commands="Subcommands:")
app.command(config_app)


@config_app.command(name="show")
def config_show(key: Optional[str] = None) -> int:
    """Display configuration key or full settings."""
    from core import config_cli
    args = [key] if key else []
    return config_cli.cmd_show(args)


@config_app.command(name="edit")
def config_edit() -> int:
    """Open configuration file in default editor."""
    from core import config_cli
    return config_cli.cmd_edit([])


@config_app.command(name="set")
def config_set(key: str, value: str) -> int:
    """Set a configuration parameter."""
    from core import config_cli
    return config_cli.cmd_set([key, value])


# ---------------------------------------------------------------------------
# Additional top-level commands
# ---------------------------------------------------------------------------
@app.command
def bench(iters: int = 10, warmup: int = 2, quiet: bool = False) -> int:
    """Benchmark interactive shell startup time across iterations."""
    from core import bench_cli
    args = ["--iters", str(iters), "--warmup", str(warmup)]
    if quiet:
        args.append("--quiet")
    return bench_cli.cmd_bench(args)


@app.command
def completion(shell: str = "zsh", rebuild: bool = False, clean: bool = False) -> int:
    """Generate and manage shell completions."""
    from core import completion_cli
    args = ["--shell", shell]
    if rebuild:
        args.append("--rebuild")
    if clean:
        args.append("--clean")
    return completion_cli.cmd_completion(args)


@app.command
def install(
    default: bool = False,
    custom: bool = False,
    dry_run: bool = False,
    no_activate: bool = False,
) -> int:
    """Install Ziro shell framework with defaults or custom profile."""
    from core import install_cli
    args: list[str] = []
    if default:
        args.append("--default")
    if custom:
        args.append("--custom")
    if dry_run:
        args.append("--dry-run")
    if no_activate:
        args.append("--no-activate")
    return install_cli.cmd_install(args)


@app.command
def local(*tokens: str) -> int:
    """Manage local plugins (deprecated layer-0 helper; use 'ziro plugin add --local' instead)."""
    import shutil
    import subprocess
    cmd = shutil.which("ziro-local")
    if cmd:
        res = subprocess.run([cmd, *tokens])
        return res.returncode
    print("ziro: 'local' is a deprecated layer-0 helper; use 'ziro plugin add --local' instead.", file=sys.stderr)
    return 1


def run(argv: list[str] | None = None) -> int:
    """Execute Cyclopts application and return standard integer exit code."""
    args = list(argv or sys.argv[1:])
    try:
        res = app(args)
        return res if isinstance(res, int) else 0
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else (0 if exc.code is None else 1)
