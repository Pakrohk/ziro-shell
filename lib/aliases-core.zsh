#!/usr/bin/env zsh
# ziro-shell — Core aliases: ls color, cd navigation, ll/la with eza fallback
# Layer: 0 (Shell Aliases) · Eager stage

setopt autocd 2>/dev/null

# ─── Live path completion & binary detection ───
# Automatically update the internal command hash table when completing commands,
# allowing newly installed packages/binaries to be found immediately without shell restart.
zstyle ':completion:*' rehash true


# ─── Defensive navigation: functions + aliases ───
unalias .. ... .... 2>/dev/null
function .. { cd ..; }
function ... { cd ../..; }
function .... { cd ../../..; }

alias ..='cd ..'
alias ...='cd ../..'
alias ....='cd ../../..'

# ─── Directory history sync: cd ↔ z (zoxide) ───
autoload -Uz add-zsh-hook 2>/dev/null

_ziro_chpwd_zoxide() {
  if (( $+commands[zoxide] )); then
    if (( ${+functions[_ziro_proxy_zoxide]} )); then
      _ziro_proxy_zoxide true 2>/dev/null
    fi
    if (( ${+functions[__zoxide_hook]} )); then
      add-zsh-hook -d chpwd _ziro_chpwd_zoxide 2>/dev/null
      __zoxide_hook
    else
      command zoxide add -- "$PWD"
    fi
  fi
}

if (( ${+functions[add-zsh-hook]} )); then
  add-zsh-hook chpwd _ziro_chpwd_zoxide
fi

# ─── Colors, classification indicators & directory grouping ───
if [[ "$OSTYPE" == darwin* ]]; then
  if command -v gls >/dev/null 2>&1; then
    alias ls='gls -F --group-directories-first --color=auto'
  else
    alias ls='ls -F -G'
  fi
else
  alias ls='ls -F --group-directories-first --color=auto'
fi
alias grep='grep --color=auto'

# ─── Directory listing with eza fallback ───
if command -v eza >/dev/null 2>&1; then
  alias ll='eza -la --icons --group-directories-first'
  alias la='eza -a --icons --group-directories-first'
  alias lt='eza --tree --level=2 --icons'
else
  if [[ "$OSTYPE" == darwin* ]] && ! command -v gls >/dev/null 2>&1; then
    alias ll='ls -la -F -G'
    alias la='ls -a -F -G'
  else
    alias ll='ls -la -F --group-directories-first'
    alias la='ls -a -F --group-directories-first'
  fi
  alias lt='ls -R'
fi
