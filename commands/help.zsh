#!/usr/bin/env zsh
# ziro-shell — help command
# Layer: 0 (CLI)
# Spec: 008
# AUTO-GENERATED: no

_ziro_cmd_help() {
  emulate -L zsh
  : ${ZIRO_HOME:="$HOME/.ziro"}
  : ${ZIRO_CONFIG:="${XDG_CONFIG_HOME:-$HOME/.config}/ziro"}

  if [[ $# -gt 0 && "$1" != "--help" && "$1" != "-h" ]] && command -v python3 &>/dev/null; then
    (cd "$ZIRO_HOME" && ZIRO_HOME="$ZIRO_HOME" ZIRO_CONFIG="$ZIRO_CONFIG" \
      python3 -m core help "$@")
    return $?
  fi

  cat << 'HELP'
ziro — fast, layered Zsh runtime customization

Usage:
  ziro <command> [args...]
  ziro [flags]

Flags:
  -h, --help     Show help information
  -v, --version  Show version

Commands:
  install     Install ziro with defaults or custom profile
  plugin      Manage plugins (add, remove, list, show)
  tag         Manage plugin tags (list, show, add, remove, reset, define)
  suggest     Manage auto-suggest component
  theme       Manage shell themes and appearance
  prompt      Manage shell prompt engine
  config      Inspect and manage configuration files
  doctor      Diagnose installation health and configuration
  bench       Benchmark startup and command performance
  completion  Generate shell completion script
  analyze     Analyze tools and inspect load manifest
  sync        Compile and synchronize shell boot artifacts
  update      Check for updates and update ziro components
  help        Show help information for ziro commands

Run 'ziro help <command>' or 'ziro <command> --help' for details on a command.
For more: https://github.com/Pakrohk/ziro-shell
HELP
}
