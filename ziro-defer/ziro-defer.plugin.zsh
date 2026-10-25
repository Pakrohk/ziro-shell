# ziro-defer.plugin.zsh - Main entry point (v2.0.0 Module-Lazy).
# Per ARCHITECTURE S3.3 and RULES R10.2.
# Idempotent, < 100 lines, zero forks during load.

[[ -n "${_ZIRO_DEFER_LOADED:-}" ]] && return 0
emulate -L zsh
typeset -g _ZIRO_DEFER_ROOT="${${(%):-%x}:A:h}"

# ─── Eager Minimal Core (10 files) ───
source "${_ZIRO_DEFER_ROOT}/stages/stage-0-pre-source.zsh"
_ziro_defer_stage_0_builtin
source "${_ZIRO_DEFER_ROOT}/core/version.zsh"
source "${_ZIRO_DEFER_ROOT}/config/defaults.zsh"
source "${_ZIRO_DEFER_ROOT}/core/queue.zsh"
source "${_ZIRO_DEFER_ROOT}/core/task-registry.zsh"
source "${_ZIRO_DEFER_ROOT}/core/scheduler.zsh"
source "${_ZIRO_DEFER_ROOT}/core/hooks.zsh"
source "${_ZIRO_DEFER_ROOT}/api/ziro-defer.zsh"
source "${_ZIRO_DEFER_ROOT}/api/ziro-defer-bind-widget.zsh"
source "${_ZIRO_DEFER_ROOT}/api/ziro-defer-dispatch.zsh"

# ─── Lazy Module Loader ───
typeset -gA _ZIRO_DEFER_LAZY_MODULES=(
  timer lib/timer.zsh
  json-writer lib/json-writer.zsh
  cycle-detect lib/cycle-detect.zsh
  condition-eval lib/condition-eval.zsh
  toml-parser lib/toml-parser.zsh
  cache-io lib/cache-io.zsh
  eval-cache cache/eval-cache.zsh
  zwc-cache cache/zwc-cache.zsh
  analysis-cache cache/analysis-cache.zsh
  tag-cache cache/tag-cache.zsh
  marker-cache cache/marker-cache.zsh
  ghost-cache cache/ghost-cache.zsh
  batch api/ziro-defer-batch.zsh
  stats api/ziro-defer-stats.zsh
  reorder api/ziro-defer-reorder.zsh
  stage-1 stages/stage-1-bootstrap.zsh
  stage-2 stages/stage-2-pre-compinit.zsh
  stage-3 stages/stage-3-compinit.zsh
  stage-4 stages/stage-4-post-compinit.zsh
  stage-5 stages/stage-5-post-prompt.zsh
  stage-6 stages/stage-6-idle.zsh
  stage-7 stages/stage-7-on-demand.zsh
)
typeset -gA _ZIRO_DEFER_LOADED_MODULES=()

_ziro_defer_need() {
  local mod="$1"
  [[ -n "${_ZIRO_DEFER_LOADED_MODULES[$mod]:-}" ]] && return 0
  local rel="${_ZIRO_DEFER_LAZY_MODULES[$mod]:-}"
  if [[ -n "$rel" && -r "${_ZIRO_DEFER_ROOT}/${rel}" ]]; then
    source "${_ZIRO_DEFER_ROOT}/${rel}"
    _ZIRO_DEFER_LOADED_MODULES[$mod]=1
    return 0
  fi
  return 1
}

# ─── Stubs for Lazy Public APIs & Builtins ───
ziro-defer-stats() { _ziro_defer_need stats && ziro-defer-stats "$@"; }
ziro-defer-reorder() { _ziro_defer_need reorder && ziro-defer-reorder "$@"; }
ziro-defer-batch() { _ziro_defer_need batch && ziro-defer-batch "$@"; }
_ziro_defer_lib_timer_start() { _ziro_defer_need timer && _ziro_defer_lib_timer_start "$@"; }
_ziro_defer_lib_timer_elapsed_ms() { _ziro_defer_need timer && _ziro_defer_lib_timer_elapsed_ms "$@"; }
_ziro_defer_lib_eval_condition() { _ziro_defer_need condition-eval && _ziro_defer_lib_eval_condition "$@"; }
_ziro_defer_lib_json_record() { _ziro_defer_need json-writer && _ziro_defer_lib_json_record "$@"; }
_ziro_defer_stage_1_builtin() { _ziro_defer_need stage-1 && _ziro_defer_stage_1_builtin "$@"; }
_ziro_defer_stage_2_builtin() { _ziro_defer_need stage-2 && _ziro_defer_stage_2_builtin "$@"; }
_ziro_defer_stage_3_builtin() { _ziro_defer_need stage-3 && _ziro_defer_stage_3_builtin "$@"; }
_ziro_defer_stage_4_builtin() { _ziro_defer_need stage-4 && _ziro_defer_stage_4_builtin "$@"; }
_ziro_defer_stage_5_builtin() { _ziro_defer_need stage-5 && _ziro_defer_stage_5_builtin "$@"; }
_ziro_defer_stage_6_builtin() { _ziro_defer_need stage-6 && _ziro_defer_stage_6_builtin "$@"; }
_ziro_defer_stage_7_builtin() { _ziro_defer_need stage-7 && _ziro_defer_stage_7_builtin "$@"; }

# ─── Register Stage 2/3/4 builtins (run when dispatched) ───
ziro-defer --stage=2 --slot=a --name=_builtin_stage_2 _ziro_defer_stage_2_builtin
ziro-defer --stage=3 --slot=a --name=_builtin_stage_3 _ziro_defer_stage_3_builtin
ziro-defer --stage=4 --slot=a --name=_builtin_stage_4 _ziro_defer_stage_4_builtin

# ─── Install precmd hook & finalize ───
_ziro_defer_core_hooks_install
typeset -g _ZIRO_DEFER_LOADED=1
return 0
