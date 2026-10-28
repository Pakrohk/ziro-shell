"""ziro-shell — centralized help registry and command documentation.

Layer: 3 (Python core, cold-path only)
Spec: 008 R1, R2, R7, R10
"""

from __future__ import annotations

import difflib
import sys
from dataclasses import dataclass, field

from core.constants import REPO_URL


@dataclass
class HelpEntry:
    name: str
    summary: str
    usage: str
    subcommands: dict[str, str] = field(default_factory=dict)
    flags: list[tuple[str, str]] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if isinstance(self.subcommands, list):
            self.subcommands = {s: "" for s in self.subcommands}


HELP_REGISTRY: dict[str, HelpEntry] = {
    "install": HelpEntry(
        name="install",
        summary="Install ziro with defaults or custom profile",
        usage="ziro install [--default | --custom] [--dry-run] [--no-activate]",
        flags=[
            ("--default", "Install with pre-configured defaults (Starship, recommended plugins)"),
            ("--custom", "Interactive prompt to choose components manually"),
            ("--dry-run", "Preview files that would be written without writing"),
            ("--no-activate", "Skip modifying ~/.zshrc during install"),
        ],
        examples=[
            "ziro install",
            "ziro install --default",
            "ziro install --dry-run",
        ],
        related=["doctor", "config"],
    ),
    "plugin": HelpEntry(
        name="plugin",
        summary="Manage plugins (add, remove, list, show)",
        usage="ziro plugin <add|remove|list|show> [args...]",
        subcommands={
            "add": "Add and analyze a plugin from Git repository, GitHub slug, or local path",
            "remove": "Remove an installed plugin",
            "list": "List all installed plugins and their load strategies",
            "show": "Show detailed analysis and resolved strategy for a plugin",
        },
        flags=[
            ("--dry-run", "Simulate plugin addition or removal without disk changes"),
        ],
        examples=[
            "ziro plugin list",
            "ziro plugin add zsh-users/zsh-autosuggestions",
            "ziro plugin add --local ~/.ziro/lib/helpers.zsh helpers",
            "ziro plugin add ohmyzsh/ohmyzsh --subpath=plugins/git --name=git",
            "ziro plugin add romkatv/powerlevel10k @eager",
            "ziro plugin show zsh-autosuggestions",
            "ziro plugin remove zsh-autosuggestions",
        ],
        related=["tag"],
    ),
    "plugin add": HelpEntry(
        name="plugin add",
        summary="Add and analyze a plugin",
        usage="ziro plugin add <source> [name] [@tags...] [--local] [--subpath=<path>] [--dry-run]",
        flags=[
            ("--local", "Treat source as local path (skip GitHub detection)"),
            ("--subpath=<path>", "Relative path inside repository for plugin source"),
            ("--name=<name>", "Explicit plugin name"),
            ("--dry-run", "Preview plugin clone, analysis, and strategy without saving"),
        ],
        examples=[
            "ziro plugin add zsh-users/zsh-autosuggestions",
            "ziro plugin add https://github.com/zsh-users/zsh-syntax-highlighting.git",
            "ziro plugin add --local ~/.ziro/lib/helpers.zsh helpers",
            "ziro plugin add ohmyzsh/ohmyzsh --subpath=plugins/git --name=git",
            "ziro plugin add romkatv/powerlevel10k @eager",
        ],
        related=["plugin show", "tag add"],
    ),
    "plugin remove": HelpEntry(
        name="plugin remove",
        summary="Remove an installed plugin",
        usage="ziro plugin remove <name> [--dry-run]",
        flags=[
            ("<name>", "Name of plugin to remove"),
            ("--dry-run", "Preview plugin removal without deleting files"),
        ],
        examples=[
            "ziro plugin remove zsh-autosuggestions",
            "ziro plugin remove wd --dry-run",
        ],
        related=["plugin list"],
    ),
    "plugin list": HelpEntry(
        name="plugin list",
        summary="List all installed plugins and their load strategies",
        usage="ziro plugin list",
        examples=[
            "ziro plugin list",
        ],
        related=["plugin show"],
    ),
    "plugin show": HelpEntry(
        name="plugin show",
        summary="Show detailed plugin analysis and tags",
        usage="ziro plugin show <name>",
        flags=[
            ("<name>", "Name of plugin to inspect"),
        ],
        examples=[
            "ziro plugin show zsh-autosuggestions",
            "ziro plugin show wd",
        ],
        related=["plugin list", "tag show"],
    ),
    "tag": HelpEntry(
        name="tag",
        summary="Manage plugin tags (list, show, add, remove, reset, define)",
        usage="ziro tag <list|show|add|remove|reset|define> [args...]",
        subcommands={
            "list": "List available builtin and user tags",
            "show": "Show tags applied to a specific plugin",
            "add": "Apply a tag to a plugin",
            "remove": "Remove a tag from a plugin",
            "reset": "Reset user tags for a plugin to defaults",
            "define": "Define a custom tag in user.toml",
        },
        examples=[
            "ziro tag list",
            "ziro tag show zsh-autosuggestions",
            "ziro tag add zsh-autosuggestions @eager",
            "ziro tag remove zsh-autosuggestions @eager",
        ],
        related=["plugin"],
    ),
    "tag list": HelpEntry(
        name="tag list",
        summary="List available builtin and user tags",
        usage="ziro tag list [--builtin | --user]",
        flags=[
            ("--builtin", "Display only built-in system tags"),
            ("--user", "Display only user-defined tags"),
        ],
        examples=[
            "ziro tag list",
            "ziro tag list --builtin",
        ],
        related=["tag show"],
    ),
    "tag show": HelpEntry(
        name="tag show",
        summary="Show tags applied to a specific plugin",
        usage="ziro tag show <plugin>",
        flags=[
            ("<plugin>", "Name of plugin whose tags to display"),
        ],
        examples=[
            "ziro tag show zsh-autosuggestions",
            "ziro tag show git",
        ],
        related=["tag list", "tag add"],
    ),
    "tag add": HelpEntry(
        name="tag add",
        summary="Apply a tag to a plugin",
        usage="ziro tag add <plugin> <@tag>",
        flags=[
            ("<plugin>", "Target plugin name"),
            ("<@tag>", "Tag name to apply (e.g. @eager, @lazy, @no-compile)"),
        ],
        examples=[
            "ziro tag add zsh-autosuggestions @eager",
            "ziro tag add git @no-compile",
        ],
        related=["tag remove", "tag show"],
    ),
    "tag remove": HelpEntry(
        name="tag remove",
        summary="Remove a tag from a plugin",
        usage="ziro tag remove <plugin> <@tag>",
        flags=[
            ("<plugin>", "Target plugin name"),
            ("<@tag>", "Tag name to remove"),
        ],
        examples=[
            "ziro tag remove zsh-autosuggestions @eager",
        ],
        related=["tag add", "tag show"],
    ),
    "tag reset": HelpEntry(
        name="tag reset",
        summary="Reset user tags for a plugin",
        usage="ziro tag reset <plugin>",
        flags=[
            ("<plugin>", "Target plugin name to reset tags to empty"),
        ],
        examples=[
            "ziro tag reset zsh-autosuggestions",
        ],
        related=["tag show"],
    ),
    "tag define": HelpEntry(
        name="tag define",
        summary="Define a custom tag in user.toml",
        usage="ziro tag define <@name> --strategy=<eager|defer|raw> [--priority=<N>] [--description=<text>] [--force]",
        flags=[
            ("--strategy=<val>", "Load strategy: eager, defer, or raw"),
            ("--priority=<N>", "Priority integer 0-100 (default: 5)"),
            ("--description=<text>", "Short description of the tag"),
            ("--force", "Override existing builtin or user tag"),
        ],
        examples=[
            "ziro tag define @custom --strategy=eager --priority=7",
            "ziro tag define @slow --strategy=defer --priority=3 --description='Load late'",
        ],
        related=["tag list", "tag show"],
    ),
    "suggest": HelpEntry(
        name="suggest",
        summary="Manage auto-suggest component",
        usage="ziro suggest <list|set|disable> [args...]",
        subcommands={
            "list": "List available auto-suggest providers",
            "set": "Set active auto-suggest provider",
            "disable": "Disable auto-suggest component",
        },
        examples=[
            "ziro suggest list",
            "ziro suggest set zsh-autosuggestions",
            "ziro suggest disable",
        ],
        related=["theme"],
    ),
    "suggest list": HelpEntry(
        name="suggest list",
        summary="List available auto-suggest providers",
        usage="ziro suggest list",
        examples=[
            "ziro suggest list",
        ],
        related=["suggest set"],
    ),
    "suggest set": HelpEntry(
        name="suggest set",
        summary="Set active auto-suggest provider",
        usage="ziro suggest set <name>",
        flags=[
            ("<name>", "Provider name: ziro-ghost (default), zsh-autosuggestions, none"),
        ],
        examples=[
            "ziro suggest set ziro-ghost",
            "ziro suggest set zsh-autosuggestions",
            "ziro suggest set none",
        ],
        related=["suggest list", "suggest disable"],
    ),
    "suggest disable": HelpEntry(
        name="suggest disable",
        summary="Disable auto-suggest component",
        usage="ziro suggest disable",
        examples=[
            "ziro suggest disable",
        ],
        related=["suggest set"],
    ),
    "theme": HelpEntry(
        name="theme",
        summary="Manage shell themes and appearance",
        usage="ziro theme <list|current|apply|reset> [args...]",
        subcommands={
            "list": "List available theme components",
            "current": "Show currently active theme selection",
            "apply": "Apply a theme or component style",
            "reset": "Reset theme configuration to defaults",
        },
        flags=[
            ("--component <comp>", "Component to apply theme to (prompt, auto_suggest, colors, syntax_highlighting)"),
        ],
        examples=[
            "ziro theme current",
            "ziro theme list",
            "ziro theme apply default",
        ],
        related=["prompt", "suggest"],
    ),
    "theme list": HelpEntry(
        name="theme list",
        summary="List available theme presets and components",
        usage="ziro theme list [--component <comp>]",
        flags=[
            ("--component <comp>", "Component to filter by: prompt, auto_suggest, colors, syntax_highlighting"),
        ],
        examples=[
            "ziro theme list",
            "ziro theme list --component prompt",
        ],
        related=["theme current", "theme apply"],
    ),
    "theme current": HelpEntry(
        name="theme current",
        summary="Show currently active theme configuration",
        usage="ziro theme current",
        examples=[
            "ziro theme current",
        ],
        related=["theme apply"],
    ),
    "theme apply": HelpEntry(
        name="theme apply",
        summary="Apply a theme preset or component style",
        usage="ziro theme apply <name> [--component <comp>]",
        flags=[
            ("--component <comp>", "Component target: prompt, auto_suggest, colors, syntax_highlighting"),
        ],
        examples=[
            "ziro theme apply default",
            "ziro theme apply iris --component prompt",
        ],
        related=["theme current"],
    ),
    "theme reset": HelpEntry(
        name="theme reset",
        summary="Reset theme configuration to defaults",
        usage="ziro theme reset",
        examples=[
            "ziro theme reset",
        ],
        related=["theme current"],
    ),
    "prompt": HelpEntry(
        name="prompt",
        summary="Manage shell prompt engine",
        usage="ziro prompt <list|current|set> [args...]",
        subcommands={
            "list": "List supported prompt engines (starship, p10k, pure, none)",
            "current": "Display currently active prompt engine",
            "set": "Set active prompt engine",
        },
        examples=[
            "ziro prompt list",
            "ziro prompt current",
            "ziro prompt set starship",
            "ziro prompt set none",
        ],
        related=["theme"],
    ),
    "prompt list": HelpEntry(
        name="prompt list",
        summary="List supported prompt engines",
        usage="ziro prompt list",
        examples=[
            "ziro prompt list",
        ],
        related=["prompt set"],
    ),
    "prompt current": HelpEntry(
        name="prompt current",
        summary="Display currently active prompt engine",
        usage="ziro prompt current",
        examples=[
            "ziro prompt current",
        ],
        related=["prompt set"],
    ),
    "prompt set": HelpEntry(
        name="prompt set",
        summary="Set active prompt engine",
        usage="ziro prompt set <name>",
        flags=[
            ("<name>", "Supported prompt engines: starship, powerlevel10k (p10k), pure, none"),
        ],
        examples=[
            "ziro prompt set starship",
            "ziro prompt set p10k",
            "ziro prompt set pure",
            "ziro prompt set none",
        ],
        related=["prompt current", "prompt list"],
    ),
    "config": HelpEntry(
        name="config",
        summary="Inspect and manage configuration files",
        usage="ziro config <show|edit|set> [args...]",
        subcommands={
            "show": "Print contents of defaults.toml or tools.toml",
            "edit": "Open defaults.toml or tools.toml in $EDITOR",
            "set": "Set configuration key in defaults.toml",
        },
        examples=[
            "ziro config show",
            "ziro config show tools",
            "ziro config edit defaults",
        ],
        related=["install", "doctor"],
    ),
    "config show": HelpEntry(
        name="config show",
        summary="Display configuration file contents",
        usage="ziro config show [defaults | tools]",
        flags=[
            ("[defaults | tools]", "File to display (default: summarize all config files)"),
        ],
        examples=[
            "ziro config show",
            "ziro config show tools",
            "ziro config show defaults",
        ],
        related=["config edit"],
    ),
    "config edit": HelpEntry(
        name="config edit",
        summary="Edit configuration file in $EDITOR",
        usage="ziro config edit [defaults | tools]",
        flags=[
            ("[defaults | tools]", "File to edit in $EDITOR (default: defaults.toml)"),
        ],
        examples=[
            "ziro config edit defaults",
            "ziro config edit tools",
        ],
        related=["config show"],
    ),
    "config set": HelpEntry(
        name="config set",
        summary="Set configuration option in defaults.toml",
        usage="ziro config set <category.key> <value>",
        flags=[
            ("<category.key>", "Configuration path (e.g. prompt.default, auto_suggest.default, ui.rich)"),
            ("<value>", "New value to assign"),
        ],
        examples=[
            "ziro config set prompt.default pure",
            "ziro config set auto_suggest.default zsh-autosuggestions",
            "ziro config set ui.rich false",
        ],
        related=["config show", "config edit"],
    ),
    "doctor": HelpEntry(
        name="doctor",
        summary="Diagnose installation health and configuration",
        usage="ziro doctor [--verbose|-v]",
        flags=[
            ("--verbose, -v", "Display detailed diagnostic messages"),
        ],
        examples=[
            "ziro doctor",
            "ziro doctor --verbose",
        ],
        related=["bench", "config"],
    ),
    "bench": HelpEntry(
        name="bench",
        summary="Benchmark startup and command performance",
        usage="ziro bench [--iters <n>]",
        flags=[
            ("--iters <n>", "Number of iterations for min-of-N benchmark (default: 11)"),
        ],
        examples=[
            "ziro bench",
            "ziro bench --iters 15",
        ],
        related=["doctor"],
    ),
    "completion": HelpEntry(
        name="completion",
        summary="Generate shell completion script",
        usage="ziro completion [zsh]",
        flags=[
            ("-h, --help", "Show help information"),
        ],
        examples=[
            "ziro completion",
            "ziro completion zsh",
        ],
        related=["install", "help"],
    ),
    "update": HelpEntry(
        name="update",
        summary="Update Ziro Shell components, plugins, and compile artifacts",
        usage="ziro update [--check] [--force] [--dev] [--dry-run] [--yes] [--plugins-only] [--sync-only] [--plugin <name>] [--no-analyze] [--quiet]",
        flags=[
            ("-c, --check", "Check for available updates without applying"),
            ("-f, --force", "Bypass uncommitted tracked changes guard"),
            ("--dev", "Bypass uncommitted tracked changes guard with warning in dev mode"),
            ("--dry-run", "Show update orchestration plan without making changes"),
            ("-y, --yes", "Skip interactive confirmation prompts"),
            ("--plugins-only", "Fetch plugin updates only (skip self-check and sync)"),
            ("--sync-only", "Compile and rebuild boot artifacts only (alias for ziro sync)"),
            ("--plugin <name>", "Update only the specified plugin by name"),
            ("--no-analyze", "Skip analyze prompt after updates, proceed directly to sync"),
            ("-q, --quiet", "Suppress progress messages"),
        ],
        examples=[
            "ziro update",
            "ziro update --check",
            "ziro update --dry-run",
            "ziro update --force",
            "ziro update --sync-only",
            "ziro update --plugin zsh-completions",
        ],
        related=["sync", "analyze", "doctor"],
    ),
    "analyze": HelpEntry(
        name="analyze",
        summary="Analyze tools and inspect load manifest",
        usage="ziro analyze [tool] [--full] [--dry-run]",
        flags=[
            ("-h, --help", "Show help information"),
            ("--full", "Full re-analysis from scratch (regenerates load.toml)"),
            ("--dry-run", "Show summary without writing"),
        ],
        examples=[
            "ziro analyze",
            "ziro analyze --full",
            "ziro analyze starship",
        ],
        related=["sync", "doctor"],
    ),
    "sync": HelpEntry(
        name="sync",
        summary="Compile and synchronize shell boot artifacts",
        usage="ziro sync [--config <path>]",
        flags=[
            ("-h, --help", "Show help information"),
            ("--config", "Path to load.toml manifest"),
        ],
        examples=[
            "ziro sync",
        ],
        related=["analyze", "doctor"],
    ),
    "help": HelpEntry(
        name="help",
        summary="Show help information for ziro commands",
        usage="ziro help [command [subcommand]]",
        examples=[
            "ziro help",
            "ziro help install",
            "ziro help plugin",
            "ziro help plugin add",
        ],
        related=[],
    ),
}


def get_entry(name: str) -> HelpEntry | None:
    """Retrieve help entry by command name or composite subcommand."""
    normalized = " ".join(name.strip().split())
    if not normalized:
        return None
    if normalized in HELP_REGISTRY:
        return HELP_REGISTRY[normalized]

    parts = normalized.split()
    if len(parts) > 1 and parts[0] in HELP_REGISTRY:
        parent = HELP_REGISTRY[parts[0]]
        sub = parts[1]
        if sub in parent.subcommands:
            return HelpEntry(
                name=f"{parent.name} {sub}",
                summary=parent.subcommands[sub],
                usage=f"ziro {parent.name} {sub} [args...]",
                related=[parent.name],
            )
    return None


def suggest_similar(name: str) -> str | None:
    """Fuzzy match unknown command to registered commands or subcommands."""
    normalized = " ".join(name.strip().split()).lower()
    if not normalized:
        return None

    # Check if this matches a subcommand of a top-level command
    for parent_name, entry in HELP_REGISTRY.items():
        if " " not in parent_name and normalized in entry.subcommands:
            return f"{parent_name} {normalized}"

    # Fuzzy match against top-level command names
    top_cmds = [k for k in HELP_REGISTRY if " " not in k]
    matches = difflib.get_close_matches(normalized, top_cmds, n=1, cutoff=0.5)
    if matches:
        return matches[0]

    # Fuzzy match against all registered keys
    all_keys = list(HELP_REGISTRY.keys())
    matches = difflib.get_close_matches(normalized, all_keys, n=1, cutoff=0.5)
    return matches[0] if matches else None


def t(key: str, default: str) -> str:
    """i18n translation stub. Defaults to English text, ready for future localization."""
    return default


def _use_color(stream: Any = None) -> bool:
    try:
        from core.tty import is_tty
        return is_tty(stream or sys.stdout)
    except Exception:
        return False


_BOLD = "\033[1m"
_CYAN = "\033[36m"
_BOLD_CYAN = "\033[1;36m"
_RESET = "\033[0m"


def _c(text: str, code: str, enabled: bool) -> str:
    return f"{code}{text}{_RESET}" if enabled else text


def render_entry(entry: HelpEntry, level: str = "top", colorize: bool | None = None) -> str:
    """Render a HelpEntry into structured, aligned terminal text."""
    if colorize is None:
        colorize = _use_color()

    lines: list[str] = []
    lines.append(f"{_c('ziro ' + entry.name, _BOLD, colorize)} — {entry.summary}")
    lines.append("")
    lines.append(_c(t("help.usage", "Usage:"), _BOLD_CYAN, colorize))
    lines.append(f"  {entry.usage}")

    if entry.subcommands:
        lines.append("")
        lines.append(_c(t("help.subcommands", "Subcommands:"), _BOLD_CYAN, colorize))
        max_sub = max(len(s) for s in entry.subcommands)
        pad = max(max_sub + 2, 10)
        for sub, desc in entry.subcommands.items():
            lines.append(f"  {_c(sub.ljust(pad), _CYAN, colorize)} {desc}")

    if entry.flags:
        lines.append("")
        lines.append(_c(t("help.flags", "Flags:"), _BOLD_CYAN, colorize))
        max_flag = max(len(f[0]) for f in entry.flags)
        pad = max(max_flag + 2, 12)
        for flag, desc in entry.flags:
            lines.append(f"  {_c(flag.ljust(pad), _CYAN, colorize)} {desc}")

    if entry.examples:
        lines.append("")
        lines.append(_c(t("help.examples", "Examples:"), _BOLD_CYAN, colorize))
        for ex in entry.examples:
            lines.append(f"  {ex}")

    if entry.related:
        lines.append("")
        lines.append(f"{_c(t('help.related', 'Related:'), _BOLD_CYAN, colorize)} {', '.join(entry.related)}")

    return "\n".join(lines)


def list_all(colorize: bool | None = None) -> str:
    """Render top-level command summary."""
    if colorize is None:
        colorize = _use_color()

    lines = [
        _c(t("help.title", "ziro — fast, layered Zsh runtime customization"), _BOLD, colorize),
        "",
        _c(t("help.usage", "Usage:"), _BOLD_CYAN, colorize),
        "  ziro <command> [args...]",
        "  ziro [flags]",
        "",
        _c(t("help.flags", "Flags:"), _BOLD_CYAN, colorize),
        "  -h, --help     Show help information",
        "  -v, --version  Show version",
        "",
        _c(t("help.commands", "Commands:"), _BOLD_CYAN, colorize),
    ]
    top_entries = [
        ("install", "Install ziro with defaults or custom profile"),
        ("plugin", "Manage plugins (add, remove, list, show)"),
        ("tag", "Manage plugin tags (list, show, add, remove, reset, define)"),
        ("suggest", "Manage auto-suggest component"),
        ("theme", "Manage shell themes and appearance"),
        ("prompt", "Manage shell prompt engine"),
        ("config", "Inspect and manage configuration files"),
        ("doctor", "Diagnose installation health and configuration"),
        ("bench", "Benchmark startup and command performance"),
        ("completion", "Generate shell completion script"),
        ("analyze", "Analyze tools and inspect load manifest"),
        ("sync", "Compile and synchronize shell boot artifacts"),
        ("update", "Check for updates and update ziro components"),
        ("help", "Show help information for ziro commands"),
    ]
    for cmd, summary in top_entries:
        lines.append(f"  {_c(cmd.ljust(11), _CYAN, colorize)} {summary}")

    lines.append("")
    lines.append("Run 'ziro help <command>' or 'ziro <command> --help' for details on a command.")
    lines.append(f"For more: {REPO_URL}")
    return "\n".join(lines)


def cmd_help(argv: list[str] | None = None) -> int:
    """Entry point for `ziro help [cmd]`."""
    args = [a for a in (argv or []) if a not in ("--help", "-h")]
    if not args:
        print(list_all())
        return 0

    target = " ".join(args).strip()
    entry = get_entry(target)
    if entry is not None:
        print(render_entry(entry))
        return 0

    # If composite command, check if parent exists (fallback)
    parts = target.split()
    if len(parts) > 1 and parts[0] in HELP_REGISTRY:
        parent_entry = HELP_REGISTRY[parts[0]]
        print(render_entry(parent_entry))
        return 0

    suggestion = suggest_similar(target)
    print(f"ziro: unknown command or topic '{target}'", file=sys.stderr)
    if suggestion:
        print(f"Did you mean: ziro {suggestion}?", file=sys.stderr)
    print("Run 'ziro help' to view all available commands.", file=sys.stderr)
    return 1


def handle_help_if_requested(
    argv: list[str] | None,
    command_name: str,
    subcommand: str | None = None,
) -> int | None:
    """Helper for core/*_cli.py modules to intercept --help and -h flags."""
    args = argv or []
    if "--help" not in args and "-h" not in args:
        return None

    if subcommand:
        target = f"{command_name} {subcommand}"
    else:
        rest = [a for a in args if a not in ("--help", "-h") and not a.startswith("-")]
        if rest:
            target = f"{command_name} {' '.join(rest)}"
        else:
            target = command_name

    if get_entry(target) is None and get_entry(command_name) is not None:
        target = command_name

    return cmd_help([target])


__all__ = [
    "HelpEntry",
    "HELP_REGISTRY",
    "get_entry",
    "suggest_similar",
    "render_entry",
    "list_all",
    "cmd_help",
    "handle_help_if_requested",
]
