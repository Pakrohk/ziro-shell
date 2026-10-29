#!/usr/bin/env zsh
# ziro-shell — CLI dispatcher (Layer: 0, Spec: 008)

_ziro_dispatch() {
  emulate -L zsh
  if [[ "$1" == "--list-commands" ]]; then
    (cd "${ZIRO_HOME:="$HOME/.ziro"}" && python3 -m core --list-commands); return $?
  fi
  local cmd="${1:-help}"
  [[ $# -gt 0 ]] && shift
  case "$cmd" in
    --help|-h) cmd="help" ;;
    --version|-v)
      local c="${ZIRO_HOME:-$HOME/.ziro}/core/constants.py" v=""
      [[ -r "$c" ]] && while IFS= read -r l; do [[ "$l" == VERSION\ =\ * ]] && { v="${${l#*\"}%\"*}"; break; }; done < "$c"
      print "ziro-shell v${v:-1.2.1}"; return 0 ;;
  esac
  : ${ZIRO_HOME:="$HOME/.ziro"}
  local module="$ZIRO_HOME/commands/${cmd}.zsh"
  if [[ ! -r "$module" ]]; then
    source "$ZIRO_HOME/commands/help.zsh" 2>/dev/null
    _ziro_cmd_help "$cmd"
    return 1
  fi
  source "$module"
  "_ziro_cmd_${cmd}" "$@"
}

ziro() { _ziro_dispatch "$@"; }
