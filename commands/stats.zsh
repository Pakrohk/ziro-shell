#!/usr/bin/env zsh
# ziro-shell — stats command
# Layer: 0 (CLI)
# Spec: 038
# AUTO-GENERATED: no

_ziro_cmd_stats() {
  emulate -L zsh
  : ${ZIRO_HOME:="$HOME/.ziro"}
  : ${ZIRO_CONFIG:="${XDG_CONFIG_HOME:-$HOME/.config}/ziro"}

  if ! command -v python3 &>/dev/null; then
    print -u2 "ziro: python3 not found"
    return 1
  fi

  (cd "$ZIRO_HOME" && ZIRO_HOME="$ZIRO_HOME" ZIRO_CONFIG="$ZIRO_CONFIG" \
    python3 -m core stats "$@")
}
