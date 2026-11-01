#!/usr/bin/env zsh
# ziro-shell — history refresh hook (ADL-026, 2026-10-25)
# Backup for ziro-ghost history cache bug — same-terminal instant + cross-terminal 2s
# Safe no-op if ziro-ghost is not loaded or functions are missing.

[[ -o interactive ]] || return 0

autoload -Uz add-zsh-hook 2>/dev/null

# Same-terminal: append and filter single executed command to ghost cache
_ziro_ghost_history_append() {
  emulate -L zsh
  if (( ${+functions[ghost_history_append_last]} )); then
    ghost_history_append_last
    return 0
  fi
  (( ${+functions[ghost_history_load]} )) || return 0
  (( ${+_ghost_history_cache} )) || return 0
  local last
  last=$(fc -ln -1 2>/dev/null) || return 0
  last=${last##[[:space:]]#}
  [[ -z "$last" ]] && return 0
  if (( ${+functions[ghost_history_is_sensitive]} )); then
    ghost_history_is_sensitive "$last" && return 0
  fi
  [[ "${_ghost_history_cache[1]}" == "$last" ]] && return 0
  _ghost_history_cache=("$last" "${_ghost_history_cache[@]}")
}

# Cross-terminal: check HISTFILE mtime every 5s non-destructively
typeset -g _ziro_hist_mtime_last=0
typeset -g _ziro_hist_mtime_check=0
_ziro_ghost_history_mtime_check() {
  emulate -L zsh
  local now=$EPOCHSECONDS
  (( now - _ziro_hist_mtime_check >= 5 )) || return 0
  _ziro_hist_mtime_check=$now
  local hist="${HISTFILE:-$HOME/.zsh_history}"
  [[ -r "$hist" ]] || return 0
  local mtime
  mtime=$(command stat -c %Y "$hist" 2>/dev/null || command stat -f %m "$hist" 2>/dev/null) || return 0
  [[ "$mtime" == "$_ziro_hist_mtime_last" ]] && return 0
  _ziro_hist_mtime_last=$mtime
  # Reload pre-filtered cache non-destructively (never leaves cache empty)
  (( ${+functions[ghost_history_load]} )) && ghost_history_load
}

if (( ${+functions[add-zsh-hook]} )); then
  add-zsh-hook precmd _ziro_ghost_history_append
  add-zsh-hook precmd _ziro_ghost_history_mtime_check
fi
