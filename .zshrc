#!/usr/bin/env zsh
#
# ziro-shell minimal template
# Customize in ~/.config/ziro/defaults.toml
# Add your own aliases and functions below.
#

: ${ZIRO_HOME:="$HOME/.ziro"}

if [[ -f "$ZIRO_HOME/integration.zsh" ]]; then
  source ~/.config/ziro/boot.zsh
fi

# --- user customizations below ---


# ═══════════════════════════════════════
# History configuration
# Restored after commit 3a6814e (2026-10-15) removed these lines
# See BACKLOG-BUG-1 for the installer/cleanup bug that caused this
# ═══════════════════════════════════════
HISTFILE=~/.zsh_history
HISTSIZE=100000
SAVEHIST=100000

setopt HIST_IGNORE_ALL_DUPS
setopt HIST_SAVE_NO_DUPS
setopt INC_APPEND_HISTORY
setopt SHARE_HISTORY

# Smart arrow keys — search from beginning of typed line
bindkey '^[[A' history-beginning-search-backward
bindkey '^[[B' history-beginning-search-forward

