# ==============================================================================
# ziro-shell — Ghost Commands (commands/ghost.zsh)
# Layer: 1 (Zsh CLI Interface) · Spec: 024 · Version: 1.3.0
# ==============================================================================

_ziro_cmd_ghost() {
  local sub="${1:-}"
  if [[ "$sub" == "preview" ]]; then
    print -u2 "ziro: warning: 'ziro ghost preview' is deprecated in v1.3.0 and will be removed in v1.4.0. Please use 'ziro update' instead."
    return 0
  fi

  if (( $+commands[ghost-popup] )); then
    ghost-popup "$@"
  else
    print -u2 "ziro: ghost-popup binary not found. Run 'ziro update' to install."
    return 1
  fi
}
