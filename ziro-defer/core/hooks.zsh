# core/hooks.zsh - Hook registration and teardown.
# Per ARCHITECTURE S3.1 and RULES R4.5. Zero loops, zero branches.

emulate -L zsh

_ziro_defer_core_hooks_install() {
  emulate -L zsh
  autoload -Uz add-zsh-hook 2>/dev/null || return 1
  add-zsh-hook precmd _ziro_defer_core_dispatch_precmd
}

_ziro_defer_core_hooks_remove() {
  emulate -L zsh
  autoload -Uz add-zsh-hook 2>/dev/null || return 1
  add-zsh-hook -d precmd _ziro_defer_core_dispatch_precmd 2>/dev/null || true
}
