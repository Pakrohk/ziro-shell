# stages/stage-0-pre-source.zsh - Environment setup before any other source.
# Per ARCHITECTURE S3.3 and RULES R3.3. Budget: < 0.1ms. Zero forks.

emulate -L zsh

# @O(1)-justified: inline environment exports, zero fork.
_ziro_defer_stage_0_builtin() {
  emulate -L zsh

  # Hoist zsh/datetime for EPOCHREALTIME (per ARCHITECTURE S3.3)
  zmodload -F zsh/datetime b:EPOCHREALTIME 2>/dev/null || zmodload zsh/datetime 2>/dev/null

  # Canonicalize XDG paths
  typeset -g ZIRO_DATA="${XDG_DATA_HOME:-$HOME/.local/share}/ziro"
  typeset -g ZIRO_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/ziro"
  typeset -g ZIRO_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/ziro"

  # Record boot start (used for stats)
  typeset -gF _ZIRO_DEFER_BOOT_T0=${EPOCHREALTIME:-0}

  return 0
}

# @O(1)-justified: constant string output.
_ziro_defer_stage_0_budget_ms() { print -- "0.1" }
