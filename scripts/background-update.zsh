#!/usr/bin/env zsh
# scripts/background-update.zsh — idle update check (called by _ziro_idle_update_check)
# Runs in background on shell idle; must be safe to run repeatedly.
emulate -L zsh
setopt err_return no_unset pipe_fail

# Only run if ziro command is available
(( $+commands[ziro] )) || exit 0

# Skip if recently checked (within last 24h) — use marker file
local marker="${ZIRO_CACHE:-$HOME/.cache/ziro}/.update_checked"
if [[ -f "$marker" ]]; then
  local mtime=0
  if zmodload -F zsh/stat b:zstat 2>/dev/null; then
    mtime=$(zstat +mtime "$marker" 2>/dev/null || echo 0)
  else
    mtime=$(stat -c %Y "$marker" 2>/dev/null || stat -f %m "$marker" 2>/dev/null || echo 0)
  fi
  if [[ $(( EPOCHSECONDS - mtime )) -lt 86400 ]]; then
    exit 0
  fi
fi

# Run check (non-blocking, quiet)
ziro update --check --quiet 2>/dev/null || true
mkdir -p "${marker:h}" && touch "$marker" 2>/dev/null || true
