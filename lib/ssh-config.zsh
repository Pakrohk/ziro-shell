#!/usr/bin/env zsh
# ziro-shell — SSH agent configuration
# Disconnect broken GCR / gnome-keyring socket if present so OpenSSH agent runs cleanly
if [[ "$SSH_AUTH_SOCK" == */gcr/* || "$SSH_AUTH_SOCK" == */gnome-keyring/* ]]; then
  unset SSH_AUTH_SOCK
fi

zstyle :omz:plugins:ssh-agent quiet yes
zstyle :omz:plugins:ssh-agent lazy yes

# identities deliberately not auto-added to avoid blocking prompt with passphrase prompts.
# To opt-in specific keys, add to your ~/.config/ziro/load.toml or local config:
#   zstyle :omz:plugins:ssh-agent identities id_ed25519 aur
