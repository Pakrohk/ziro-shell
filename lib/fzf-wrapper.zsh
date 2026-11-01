#!/usr/bin/env zsh
# ziro — FZF root wrapper (spec 022 M1, ADL-036)
# Blocks execute() bindings in root. No-op for non-root.

[[ $EUID -eq 0 ]] || return 0

# Root only from here
typeset -g ZIRO_ROOT_FZF_WRAPPED=1

# Safe defaults for FZF_DEFAULT_OPTS
if [[ -z "${ZIRO_ALLOW_ROOT_FZF_EXECUTE:-}" ]]; then
  export FZF_DEFAULT_OPTS="--no-mouse --height=40% --layout=reverse"
  if [[ -z "${FZF_DEFAULT_COMMAND:-}" ]]; then
    if (( $+commands[fd] )); then
      export FZF_DEFAULT_COMMAND='fd --type f --hidden --exclude .git --exclude /proc --exclude /sys --exclude /dev'
    else
      export FZF_DEFAULT_COMMAND='find . -type f -not -path "*/.git/*" -not -path "/proc/*" -not -path "/sys/*" -not -path "/dev/*" 2>/dev/null'
    fi
  fi
fi

fzf() {
  emulate -L zsh
  if [[ -z "${ZIRO_ALLOW_ROOT_FZF_EXECUTE:-}" ]]; then
    local arg
    for arg in "$@"; do
      if [[ "$arg" == *"execute("* ]] || [[ "$arg" == *"execute-silent("* ]]; then
        print -u2 "ziro: fzf execute() bindings are disabled in root (spec 022 M1)."
        print -u2 "Set ZIRO_ALLOW_ROOT_FZF_EXECUTE=1 to override (not recommended)."
        return 1
      fi
    done
    if [[ "$FZF_DEFAULT_OPTS" == *"execute"* ]]; then
      print -u2 "ziro: FZF_DEFAULT_OPTS contained execute(); resetting to safe defaults."
      export FZF_DEFAULT_OPTS="--no-mouse --height=40% --layout=reverse"
    fi
  fi
  command fzf "$@"
}
