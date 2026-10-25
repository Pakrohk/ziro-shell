# core/scheduler.zsh - Main dispatch loop and task execution engine.
# Per ARCHITECTURE S3.1. Uses REPLY pattern for queue pop (no subshell).
# Every loop and branch is justified inline.

emulate -L zsh

# Internal state
typeset -gi _ziro_defer_stage_current=5
typeset -gi _ziro_defer_first_precmd_consumed=0
typeset -gi _ziro_defer_stage_6_ran=0
typeset -gF _ziro_defer_last_precmd_ts=0
typeset -gF _ziro_defer_hotpath_total=0.0
typeset -gi _ziro_defer_idle_threshold=5

# -----------------------------------------------------------------------------
# _ziro_defer_core_dispatch_precmd
# Single precmd hook. Called once per prompt cycle.
# -----------------------------------------------------------------------------
_ziro_defer_core_dispatch_precmd() {
  emulate -L zsh
  local -F now=$EPOCHREALTIME

  # @O(1)-justified: single boolean flag check (first-cycle gate).
  # No loop, no fork. Shortest possible form.
  if (( ! _ziro_defer_first_precmd_consumed )); then
    _ziro_defer_first_precmd_consumed=1
    _ziro_defer_last_precmd_ts=$now
    _ziro_defer_core_dispatch_stage 5
    return 0
  fi

  local -F elapsed=0.0
  (( elapsed = now - _ziro_defer_last_precmd_ts ))
  _ziro_defer_last_precmd_ts=$now

  # @O(1)-justified: single idle-threshold check, one-shot per session.
  if (( ! _ziro_defer_stage_6_ran )) && (( elapsed > _ziro_defer_idle_threshold )); then
    _ziro_defer_stage_6_ran=1
    _ziro_defer_core_dispatch_stage 6
  fi

  return 0
}

# -----------------------------------------------------------------------------
# _ziro_defer_core_dispatch_stage <stage>
# Drains all slots in a->b->c->d order. Held tasks retried and then re-enqueued.
# -----------------------------------------------------------------------------
_ziro_defer_core_dispatch_stage() {
  emulate -L zsh
  local -i stage="${1:-5}"
  _ziro_defer_stage_current=$stage

  typeset -g _ZIRO_DEFER_SKIP_STAGE=0

  local slot task_id rc
  local -a held=()

  # @O(4)-justified: fixed 4-slot iteration (per RULES R6). Cannot use O(1)
  # because slots MUST be processed in a->b->c->d order per RULES R6.2.
  # Zero-fork per iteration.
  for slot in a b c d; do
    (( _ZIRO_DEFER_SKIP_STAGE )) && break
    # @O(k)-justified: drain the queue for this (stage, slot). k = queue size.
    # Unavoidable — processing k items requires at least k operations.
    # Uses REPLY pattern (no command substitution) — no fork per iteration.
    while _ziro_defer_core_queue_pop "$stage" "$slot"; do
      task_id="$REPLY"
      _ziro_defer_core_execute_task "$task_id"
      rc=$?
      (( rc == 1 )) && held+=("$task_id")
      (( _ZIRO_DEFER_SKIP_STAGE )) && break 2
    done
  done

  # M-2 FIX: retry held tasks in same dispatch while progress is made.
  # @O(rounds * held)-justified: bounded by max_rounds (10) and held count.
  # Unavoidable for in-dispatch dependency resolution. Zero-fork per iteration.
  local -i max_rounds=10 round=0
  while (( ${#held} > 0 && round < max_rounds )); do
    local -a next_held=()
    local -i progress=0
    local h
    for h in "${held[@]}"; do
      _ziro_defer_core_execute_task "$h"
      local -i h_rc=$?
      if (( h_rc == 1 )); then
        next_held+=("$h")
      else
        progress=1
      fi
      (( _ZIRO_DEFER_SKIP_STAGE )) && break
    done
    held=("${next_held[@]}")
    (( progress )) || break
    (( round++ ))
    (( _ZIRO_DEFER_SKIP_STAGE )) && break
  done

  # Re-enqueue any remaining held tasks for next precmd cycle
  # @O(h)-justified: one push per held task. Zero-fork per iteration.
  local hs
  for h in "${held[@]}"; do
    hs="${_ziro_defer_task_slot[$h]:-b}"
    _ziro_defer_core_queue_push "$stage" "$hs" "$h"
  done

  return 0
}

# -----------------------------------------------------------------------------
# _ziro_defer_core_maybe_timeout_prompt <task_id> <timeout_ms>
# C-3: Interactive timeout prompt per R11.5. Shown at most once per session.
# Sets _ZIRO_DEFER_SKIP_STAGE or _ZIRO_DEFER_QUIT_CYCLE based on user choice.
# @O(1)-justified: single read -k 1, no loop, no fork.
# -----------------------------------------------------------------------------
_ziro_defer_core_maybe_timeout_prompt() {
  emulate -L zsh
  local task_id="$1" timeout_ms="$2"

  [[ "${_ZIRO_DEFER_INTERACTIVE_TIMEOUT_PROMPT:-true}" == "true" ]] || return 0
  [[ -n "${_ZIRO_DEFER_TIMEOUT_PROMPTED:-}" ]] && return 0
  [[ -t 0 && -t 1 ]] || return 0

  typeset -g _ZIRO_DEFER_TIMEOUT_PROMPTED=1

  print -nru2 -- "ziro-defer: task '$task_id' exceeded ${timeout_ms}ms. [s]kip remaining · [c]ontinue · [q]uit stage: "
  local user_key=""
  read -k 1 user_key 2>/dev/null || return 0
  print -ru2 -- ""

  case "$user_key" in
    s|S)
      typeset -g _ZIRO_DEFER_SKIP_STAGE=1
      ;;
    q|Q)
      typeset -g _ZIRO_DEFER_SKIP_STAGE=1
      typeset -g _ZIRO_DEFER_QUIT_CYCLE=1
      ;;
    *)
      : ;;  # continue
  esac
  return 0
}

# -----------------------------------------------------------------------------
# _ziro_defer_core_execute_task <task_id>
# Return: 0=terminal, 1=held (dependency not ready), 2=not found.
# -----------------------------------------------------------------------------
_ziro_defer_core_execute_task() {
  emulate -L zsh
  local task_id="$1"

  _ziro_defer_core_has_task "$task_id" || return 2

  local cmd="${_ziro_defer_task_cmd[$task_id]}"
  local stage="${_ziro_defer_task_stage[$task_id]}"
  local slot="${_ziro_defer_task_slot[$task_id]}"
  local timeout="${_ziro_defer_task_timeout[$task_id]:-5000}"
  local condition="${_ziro_defer_task_condition[$task_id]:-}"
  local deps="${_ziro_defer_task_depends[$task_id]:-${_ziro_defer_task_after[$task_id]:-}}"

  # @O(1)-justified: short-circuit condition check. `[[ -n ]] && ! eval`
  # avoids evaluating the condition function when there's no condition.
  if [[ -n "$condition" ]] && ! _ziro_defer_lib_eval_condition "$condition"; then
    _ziro_defer_task_status[$task_id]="skipped"
    _ziro_defer_core_emit_metric "$task_id" 0.0 "skipped"
    return 0
  fi

  # @O(1)-justified: dependency gate with fast path for single dep.
  # Fast path handles ~95% of cases (0 or 1 dependency) with a single status check.
  # Multi-dep uses native ${(s: :)} split (zero fork). Held tasks return 1.
  if [[ -n "$deps" ]]; then
    if [[ "$deps" != *" "* ]]; then
      # ─── Fast path: single dependency (common case) ───
      if ! _ziro_defer_core_has_task "$deps"; then
        print -ru2 -- "ziro-defer: task '$task_id' depends on unknown '$deps'; proceeding"
      else
        case "${_ziro_defer_task_status[$deps]:-}" in
          success|failure|timeout|skipped) : ;;
          *) return 1 ;;
        esac
      fi
    else
      # ─── Slow path: multiple dependencies ───
      # @O(n)-justified: n = dependency count (typically 2-3). Unavoidable for multi-dep.
      # Zero-fork per iteration (native split, no subshell).
      local _dep
      for _dep in ${(s: :)deps}; do
        [[ -z "$_dep" ]] && continue
        if ! _ziro_defer_core_has_task "$_dep"; then
          print -ru2 -- "ziro-defer: task '$task_id' depends on unknown '$_dep'; proceeding"
          continue
        fi
        case "${_ziro_defer_task_status[$_dep]:-}" in
          success|failure|timeout|skipped) : ;;
          *) return 1 ;;
        esac
      done
    fi
  fi

  _ziro_defer_task_status[$task_id]="running"

  # @O(1)-justified: single zle -M call (builtin, zero fork). Interactive stages 5-7 only.
  local -i _progress_shown=0
  if (( stage >= 5 )) && [[ -o interactive ]] && [[ "${_ZIRO_DEFER_SHOW_PROGRESS_MESSAGE:-true}" == "true" ]]; then
    zle -M "ziro-defer: running '${_ziro_defer_task_name[$task_id]:-$task_id}'..." 2>/dev/null && _progress_shown=1
  fi

  _ziro_defer_lib_timer_start

  # @O(attempts)-justified: retry loop bounded by config (typically 1-2 attempts).
  # Unavoidable for R24 tier-1 (retry). Zero-fork per iteration.
  local -i max_attempts=1
  if [[ "${_ZIRO_DEFER_RETRY_ON_FAILURE:-false}" == "true" ]]; then
    (( max_attempts = 1 + ${_ZIRO_DEFER_MAX_RETRIES:-1} ))
  fi

  local -i attempt=0 exec_rc=1
  while (( attempt < max_attempts )); do
    eval "$cmd"
    exec_rc=$?
    (( exec_rc == 0 )) && break
    (( attempt++ ))
  done

  _ziro_defer_lib_timer_elapsed_ms
  local elapsed=$REPLY

  # @O(1)-justified: single zle -M clear (builtin, zero fork). Only if shown.
  (( _progress_shown )) && zle -M "" 2>/dev/null

  # Isolated warning (R24 tier-3) if retry exhausted
  if (( exec_rc != 0 )) && [[ "${_ZIRO_DEFER_SUPPRESS_WARNINGS:-false}" != "true" ]]; then
    print -ru2 -- "ziro-defer: task '$task_id' failed after $attempt attempt(s)"
  fi

  # C-3: interactive timeout prompt per R11.5 (only if elapsed > timeout AND TTY)
  if (( elapsed > timeout )); then
    _ziro_defer_task_status[$task_id]="timeout"
    _ziro_defer_core_maybe_timeout_prompt "$task_id" "$timeout"
  elif (( exec_rc == 0 )); then
    _ziro_defer_task_status[$task_id]="success"
  else
    _ziro_defer_task_status[$task_id]="failure"
  fi

  _ziro_defer_core_emit_metric "$task_id" "$elapsed" "${_ziro_defer_task_status[$task_id]}"
  return 0
}

# -----------------------------------------------------------------------------
# _ziro_defer_core_emit_metric <task_id> <elapsed_ms> <status>
# Best-effort JSONL append. Silent on any error (RULES R10.4).
# -----------------------------------------------------------------------------
_ziro_defer_core_emit_metric() {
  emulate -L zsh
  local task_id="$1"
  local elapsed_ms="$2"
  local task_status="$3"

  local metrics_dir="${XDG_CACHE_HOME:-$HOME/.cache}/ziro/defer"
  local metrics_file="$metrics_dir/metrics.jsonl"

  # @O(1)-justified: mkdir guard. Short-circuit avoids forking mkdir when dir exists.
  [[ -d "$metrics_dir" ]] || mkdir -p "$metrics_dir" 2>/dev/null || return 0

  local cmd="${_ziro_defer_task_cmd[$task_id]:-}"
  local stage="${_ziro_defer_task_stage[$task_id]:-0}"
  local slot="${_ziro_defer_task_slot[$task_id]:-b}"
  local ts=$EPOCHREALTIME

  local record
  _ziro_defer_lib_json_record "$ts" "$cmd" "$task_id" "$stage" "$slot" "$elapsed_ms" "$task_status" "false" "0"
  record=$REPLY

  print -r -- "$record" >> "$metrics_file" 2>/dev/null || true
}
