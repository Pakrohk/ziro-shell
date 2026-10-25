# stages/stage-7-on-demand.zsh - Lazy loading (command/key interception).
# Per ARCHITECTURE S3.3. Only runs when explicitly triggered.

emulate -L zsh

# @O(1)-justified: no-op builtin, zero fork.
_ziro_defer_stage_7_builtin() {
  emulate -L zsh
  # No built-in action. All work is queued tasks triggered by:
  # - `ziro-defer-dispatch 7` (explicit)
  # - `ziro-defer --on-key=<key>` (via bind-widget)
  return 0
}

# @O(1)-justified: constant string output.
_ziro_defer_stage_7_budget_ms() { print -- "30.0" }
