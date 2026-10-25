# stages/stage-4-post-compinit.zsh - Source cached prompt initialization.
# Per ARCHITECTURE S3.3. Budget: < 1.0ms (fast mode). Zero forks.
# Full mode (10ms) is an explicit user action (ziro install), not stage-4.

# NOTE (v2.0.0): Only 'fast' mode (source from cache) is implemented.
# 'full' mode (evaluate prompt cmd on first run) is DEFERRED to v2.1.0 when
# the analyzer (Spec 001) can decide per-plugin whether hot-path eval is safe.
# The config key `[stages.4] prompt_cache_mode` exists but 'full' is currently
# a no-op. See CHANGELOG.md 'Known Limitations'.

emulate -L zsh

# @O(1)-justified: single prompt cache source, zero fork.
_ziro_defer_stage_4_builtin() {
  emulate -L zsh
  local prompt_cmd="${_ZIRO_DEFER_PROMPT_CMD:-starship}"

  # Fast mode: source from cache only
  if _ziro_defer_cache_eval_source "$prompt_cmd" 2>/dev/null; then
    return 0
  fi

  # Fallback: default prompt (per ARCHITECTURE S3.3 "Failure Mode")
  [[ -z "${PROMPT:-}" || "${PROMPT}" == "%# " ]] && PROMPT='%# '
  return 0
}

# @O(1)-justified: constant string output.
_ziro_defer_stage_4_budget_ms() { print -- "1.0" }
