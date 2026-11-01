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

# Spec 022 M3: SSH agent forwarding — explicit no (opt-in via ZIRO_SSH_FORWARDING=1)
# DD1: even in SSH sessions (SSH_TTY set), forwarding is OFF by default.
# Rationale: agent socket exposure on remote host outweighs convenience.
if [[ "${ZIRO_SSH_FORWARDING:-0}" == "1" ]]; then
  zstyle :omz:plugins:ssh-agent agent-forwarding yes
else
  zstyle :omz:plugins:ssh-agent agent-forwarding no
fi

