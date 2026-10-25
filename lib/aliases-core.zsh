#!/usr/bin/env zsh
# ziro-shell — Core aliases: ls color, cd navigation, ll/la with eza fallback
# Layer: 0 (Shell Aliases) · Eager stage

setopt autocd 2>/dev/null

# ─── Defensive navigation: functions + aliases ───
unalias .. ... .... 2>/dev/null
function .. { cd ..; }
function ... { cd ../..; }
function .... { cd ../../..; }

alias ..='cd ..'
alias ...='cd ../..'
alias ....='cd ../../..'

# ─── Colors ───
alias ls='ls --color=auto'
alias grep='grep --color=auto'

# ─── Directory listing with eza fallback ───
if command -v eza >/dev/null 2>&1; then
  alias ll='eza -la --icons --group-directories-first'
  alias la='eza -a --icons --group-directories-first'
  alias lt='eza --tree --level=2 --icons'
else
  alias ll='ls -la'
  alias la='ls -a'
  alias lt='ls -R'
fi
