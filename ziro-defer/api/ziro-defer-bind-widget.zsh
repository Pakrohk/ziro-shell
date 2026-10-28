# api/ziro-defer-bind-widget.zsh - Bind a command to a ZLE key (one-shot).
# Per ARCHITECTURE S3.5 and Spec 005 §8 R20.2.
# Also provides internal _ziro_defer_api_bind_key used by --on-key flag.

emulate -L zsh

# _ziro_defer_api_bind_key <key> <cmd>
# Registers a one-shot ZLE widget that executes <cmd> and unbinds itself.
# Uses a global var to hold the cmd string without eval-injection of the cmd itself.
_ziro_defer_api_bind_key() {
  emulate -L zsh
  local key="$1" cmd="$2"
  [[ -z "$key" || -z "$cmd" ]] && return 1

  # Only works in interactive shells with ZLE
  (( ${+widgets} )) || { print -ru2 -- "ziro-defer-bind-widget: not an interactive ZLE shell"; return 1; }

  local widget_name="ziro_defer_kw_${RANDOM}_${RANDOM}"
  local cmd_var="_ziro_defer_kw_cmd_${widget_name}"
  typeset -g "$cmd_var"="$cmd"

  # @O(1)-justified: single eval to define widget, unavoidable for dynamic name.
  # The cmd is stored in $cmd_var and read at press time (not baked into widget).
  eval "${widget_name}() {
    emulate -L zsh
    zle -D '${widget_name}' 2>/dev/null
    bindkey -r '${key}' 2>/dev/null
    local _c=\"\${${cmd_var}}\"
    unset ${cmd_var}
    eval \"\$_c\"
    zle -R 2>/dev/null || true
  }"

  zle -N "$widget_name" 2>/dev/null || { unset "$cmd_var"; return 1; }
  bindkey "$key" "$widget_name" 2>/dev/null || {
    zle -D "$widget_name" 2>/dev/null
    unset "$cmd_var"
    return 1
  }
  return 0
}

ziro-defer-bind-widget() {
  emulate -L zsh
  local key="$1"
  shift
  (( $# == 0 )) && { print -ru2 -- "Usage: ziro-defer-bind-widget <key> <cmd>"; return 1; }
  _ziro_defer_api_bind_key "$key" "$*"
}
