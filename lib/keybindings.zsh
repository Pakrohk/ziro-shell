#!/usr/bin/env zsh
# ziro-shell — standard keybindings (Home, End, Delete, PageUp, PageDown)
# Supports xterm, kitty, linux console, tmux, and screen terminals.

bindkey '^[[H' beginning-of-line      # Home (xterm)
bindkey '^[[F' end-of-line            # End (xterm)
bindkey '^[[1~' beginning-of-line     # Home (linux/screen)
bindkey '^[[4~' end-of-line           # End (linux/screen)
bindkey '^[[3~' delete-char           # Delete
bindkey '^[[5~' up-line-or-history    # PageUp
bindkey '^[[6~' down-line-or-history  # PageDown
