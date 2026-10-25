# stages/stage-1-bootstrap.zsh - Verify znap loaded (integration.zsh sourced it first).
# Per ARCHITECTURE S3.3. Budget: < 0.5ms. Zero forks.

emulate -L zsh

# @O(1)-justified: function check, zero fork.
_ziro_defer_stage_1_builtin() {
  emulate -L zsh
  # In standalone mode, znap may not be loaded. Not a failure.
  # In integrated mode, integration.zsh sources znap BEFORE plugin.zsh.
  if (( ! $+functions[znap] )); then
    # Quiet — standalone mode is valid
    return 0
  fi
  return 0
}

# @O(1)-justified: constant string output.
_ziro_defer_stage_1_budget_ms() { print -- "0.5" }
