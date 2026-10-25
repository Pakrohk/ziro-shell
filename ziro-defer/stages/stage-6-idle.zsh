# stages/stage-6-idle.zsh - Idle maintenance (metrics rotation, cache cleanup).
# Per ARCHITECTURE S3.3 and RULES R10.3. Triggered after idle threshold.

emulate -L zsh
zmodload zsh/stat 2>/dev/null || true
zmodload zsh/files 2>/dev/null || true

# @O(1)-justified: file size check and rotation, zero fork.
_ziro_defer_stage_6_builtin() {
  emulate -L zsh
  local metrics_file="${_ZIRO_DEFER_CACHE_ROOT:-${XDG_CACHE_HOME:-$HOME/.cache}/ziro/defer}/metrics.jsonl"

  # Metrics rotation (RULES R10.3): rotate if > 1024 KB
  [[ -r "$metrics_file" ]] || return 0
  local -a stat_arr=()
  zstat -A stat_arr +size "$metrics_file" 2>/dev/null || return 0
  local size_bytes="${stat_arr[1]:-0}"
  if (( size_bytes > 1048576 )); then
    mv -f "$metrics_file" "${metrics_file}.1" 2>/dev/null || true
  fi
  return 0
}

# @O(1)-justified: constant string output.
_ziro_defer_stage_6_budget_ms() { print -- "unbounded" }
