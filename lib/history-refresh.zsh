#!/usr/bin/env zsh
# ziro-shell — history refresh hook (ADL-026, 2026-10-25)
# Backup for ziro-ghost history cache bug — same-terminal instant + cross-terminal 2s
# Safe no-op if ziro-ghost is not loaded or functions are missing.

autoload -Uz add-zsh-hook 2>/dev/null

# Same-terminal: append last command to ghost cache
_ziro_ghost_history_append() {
  emulate -L zsh
  (( ${+functions[ghost_history_load]} )) || return 0
  (( ${+_ghost_history_cache} )) || return 0
  local last
  last=$(fc -ln -1 2>/dev/null) || return 0
  last=${last##[[:space:]]#}
  [[ -z "$last" ]] && return 0
  [[ "${_ghost_history_cache[1]}" == "$last" ]] && return 0
  _ghost_history_cache=("$last" "${_ghost_history_cache[@]}")
}

# Cross-terminal: check HISTFILE mtime every 2s, invalidate on change
typeset -g _ziro_hist_mtime_last=0
typeset -g _ziro_hist_mtime_check=0
_ziro_ghost_history_mtime_check() {
  emulate -L zsh
  (( ${+functions[ghost_history_cache_invalidate]} )) || return 0
  local now=$EPOCHSECONDS
  (( now - _ziro_hist_mtime_check >= 2 )) || return 0
  _ziro_hist_mtime_check=$now
  local hist="${HISTFILE:-$HOME/.zsh_history}"
  [[ -r "$hist" ]] || return 0
  local mtime
  mtime=$(command stat -c %Y "$hist" 2>/dev/null || command stat -f %m "$hist" 2>/dev/null) || return 0
  [[ "$mtime" == "$_ziro_hist_mtime_last" ]] && return 0
  _ziro_hist_mtime_last=$mtime
  ghost_history_cache_invalidate
}

if (( ${+functions[add-zsh-hook]} )); then
  add-zsh-hook precmd _ziro_ghost_history_append
  add-zsh-hook precmd _ziro_ghost_history_mtime_check
fi
