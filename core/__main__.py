"""ziro-shell — Python CLI dispatcher.

Layer: 3 (Python core, cold-path only)
Spec: 006 R4

Usage: python3 -m core <subcommand> [args...]
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = list(argv or sys.argv[1:])
    if not args:
        print("usage: python3 -m core <subcommand> [args...]", file=sys.stderr)
        print("subcommands: theme, prompt, install, plugin, tag, config, suggest, doctor, bench, completion, update, sync, analyze", file=sys.stderr)
        return 2

    sub = args[0]
    rest = args[1:]

    if sub in ("--help", "-h"):
        from core import help_cli
        return help_cli.cmd_help(rest)
    if sub in ("--version", "-v"):
        print("ziro-shell v1.2.0")
        return 0
    if sub == "help":
        from core import help_cli
        return help_cli.cmd_help(rest)
    if sub == "completion":
        from core import completion_cli
        return completion_cli.main(rest)
    if sub == "theme":
        from core import theme_cli
        return theme_cli.main(rest)
    if sub == "prompt":
        from core import prompt_cli
        return prompt_cli.main(rest)
    if sub == "install":
        from core import install_cli
        return install_cli.main(rest)
    if sub == "plugin":
        from core import plugin_cli
        return plugin_cli.main(rest)
    if sub == "tag":
        from core import tag_cli
        return tag_cli.main(rest)
    if sub == "config":
        from core import config_cli
        return config_cli.main(rest)
    if sub == "suggest":
        from core import suggest_cli
        return suggest_cli.main(rest)
    if sub == "doctor":
        from core import doctor_cli
        return doctor_cli.main(rest)
    if sub == "bench":
        from core import bench_cli
        return bench_cli.main(rest)
    if sub == "update":
        from core import update_cli
        return update_cli.main(rest)
    if sub == "sync":
        from core import build
        return build.main(rest)
    if sub == "analyze":
        from core import analyze_cli
        return analyze_cli.main(rest)

    print(f"unknown subcommand: {sub}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
