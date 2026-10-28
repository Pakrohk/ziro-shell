#!/usr/bin/env zsh
# ziro-shell — plugin command
# Layer: 0 (CLI)
# Spec: 001 FR-001
# AUTO-GENERATED: no

_ziro_cmd_plugin() {
  emulate -L zsh
  : ${ZIRO_HOME:="$HOME/.ziro"}
  : ${ZIRO_CONFIG:="${XDG_CONFIG_HOME:-$HOME/.config}/ziro"}

  if ! command -v python3 &>/dev/null; then
    print -u2 "ziro: python3 not found"
    return 1
  fi

  (cd "$ZIRO_HOME" && ZIRO_HOME="$ZIRO_HOME" ZIRO_CONFIG="$ZIRO_CONFIG" \
    python3 -m core plugin "$@")
}
