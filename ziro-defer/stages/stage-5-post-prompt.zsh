# stages/stage-5-post-prompt.zsh - Default deferred loading stage.
# Per ARCHITECTURE S3.3. Triggered by first precmd. Unbudgeted.

emulate -L zsh

# @O(1)-justified: no-op builtin, zero fork.
_ziro_defer_stage_5_builtin() {
  emulate -L zsh
  # No built-in action. All work is queued tasks (registered by user/integration).
  # The precmd dispatcher (core/scheduler.zsh) drains the queue automatically.
  return 0
}

# @O(1)-justified: constant string output.
_ziro_defer_stage_5_budget_ms() { print -- "unbounded" }
