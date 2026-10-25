# stages/stage-2-pre-compinit.zsh - fpath injection before compinit.
# Per ARCHITECTURE S3.3 and RULES R3.3. Budget: < 1.0ms. Zero forks.

emulate -L zsh

_ziro_defer_stage_2_builtin() {
  emulate -L zsh
  local compl_path
  # @O(n)-justified: iterate over configured completion paths (typically 0-3).
  # Unavoidable for adding multiple fpath entries. Zero-fork per iteration.
  for compl_path in "${_ZIRO_DEFER_COMPLETION_PATHS[@]}"; do
    [[ -d "$compl_path" ]] && fpath+=("$compl_path")
  done
  return 0
}

# @O(1)-justified: constant string output.
_ziro_defer_stage_2_budget_ms() { print -- "1.0" }
