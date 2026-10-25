# stages/stage-3-compinit.zsh - Initialize completion system with cache freshness check.
# Per ARCHITECTURE S3.3. Budget: < 2.0ms. Zero forks (uses zsh/stat).

emulate -L zsh
zmodload zsh/stat 2>/dev/null || true
zmodload zsh/datetime 2>/dev/null || true

# @O(1)-justified: single stat check and compinit, zero fork.
_ziro_defer_stage_3_builtin() {
  emulate -L zsh
  local zcompdump="${_ZIRO_DEFER_CACHE_ROOT:-${XDG_CACHE_HOME:-$HOME/.cache}/ziro/defer}/zcompdump"

  # Check freshness (20 hours = 72000 seconds per ARCHITECTURE S3.3)
  local use_cache=0
  if [[ -r "$zcompdump" ]]; then
    local -a stat_arr=()
    zstat -A stat_arr +mtime "$zcompdump" 2>/dev/null && {
      local mtime="${stat_arr[1]:-0}"
      local -i age=0
      (( age = EPOCHSECONDS - mtime ))
      (( age < 72000 )) && use_cache=1
    }
  fi

  autoload -Uz compinit 2>/dev/null || return 0
  if (( use_cache )); then
    compinit -C -d "$zcompdump" 2>/dev/null || true
  else
    compinit -d "$zcompdump" 2>/dev/null || true
  fi
  return 0
}

# @O(1)-justified: constant string output.
_ziro_defer_stage_3_budget_ms() { print -- "2.0" }
