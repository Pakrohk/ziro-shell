# core/task-registry.zsh - Task lifecycle, dependency graph, cycle detection.
# Per ARCHITECTURE S3.1.
#
# Public (internal) API:
#   _ziro_defer_core_register <task_id> <stage> <slot> <cmd> [after] [before] [condition] [timeout_ms]
#   _ziro_defer_core_unregister <task_id>
#   _ziro_defer_core_task_status <task_id>
#   _ziro_defer_core_has_task <task_id>
#   _ziro_defer_core_cycle_check <task_id> <after_id>

emulate -L zsh

# Task property storage (per ARCHITECTURE S3.1)
typeset -gA _ziro_defer_task_cmd=()
typeset -gA _ziro_defer_task_stage=()
typeset -gA _ziro_defer_task_slot=()
typeset -gA _ziro_defer_task_timeout=()
typeset -gA _ziro_defer_task_after=()
typeset -gA _ziro_defer_task_before=()
typeset -gA _ziro_defer_task_pending_before=()  # tasks waiting for a before-target to be registered
typeset -gA _ziro_defer_task_depends=()         # primary dependency graph (space-separated task IDs)
typeset -gA _ziro_defer_task_condition=()
typeset -gA _ziro_defer_task_status=()
typeset -gA _ziro_defer_task_name=()

# -----------------------------------------------------------------------------
# _ziro_defer_core_has_task <task_id>
# Returns 0 if task is registered, 1 otherwise.
# -----------------------------------------------------------------------------
_ziro_defer_core_has_task() {
  emulate -L zsh
  [[ -n "${_ziro_defer_task_cmd[$1]:-}" ]]
}

# -----------------------------------------------------------------------------
# _ziro_defer_core_cycle_check <task_id> <after_id>
# Returns 1 if adding after-edge task_id->after_id would create a cycle.
# Uses Tarjan-style walk through _ziro_defer_task_after.
# Per RULES R7.3.
# -----------------------------------------------------------------------------
_ziro_defer_core_cycle_check() {
  emulate -L zsh
  local current="$1" target="$2"
  [[ -z "$target" ]] && return 0
  if (( $+functions[_ziro_defer_lib_detect_cycle] )); then
    _ziro_defer_lib_detect_cycle "$current" "$target"
    return $?
  fi
  # Fallback inline DFS if cycle-detect lib not yet loaded
  local -a to_visit=(${(s: :)target})
  local -i guard=0
  local node deps d
  while (( ${#to_visit} > 0 )); do
    node="${to_visit[1]}"
    to_visit=("${to_visit[@]:1}")
    [[ "$node" == "$current" ]] && return 1
    (( guard++ > 1000 )) && return 1
    deps="${_ziro_defer_task_depends[$node]:-${_ziro_defer_task_after[$node]:-}}"
    if [[ -n "$deps" ]]; then
      for d in ${(s: :)deps}; do
        [[ -n "$d" ]] && to_visit+=("$d")
      done
    fi
  done
  return 0
}

# -----------------------------------------------------------------------------
# _ziro_defer_core_register <task_id> <stage> <slot> <cmd> [after] [before] [condition] [timeout_ms]
# Registers a task. Validates parameters, checks cycle, enqueues. Per RULES R4.3.
# -----------------------------------------------------------------------------
_ziro_defer_core_register() {
  emulate -L zsh
  local task_id="$1" stage="$2" slot="$3" cmd="$4"
  local after="${5:-}" before="${6:-}" condition="${7:-}" timeout_ms="${8:-5000}"

  # Validation
  [[ -z "$task_id" || -z "$cmd" ]] && {
    print -ru2 -- "ziro-defer: register requires task_id and cmd"
    return 1
  }
  [[ "$stage" != [0-7] ]] && {
    print -ru2 -- "ziro-defer: invalid stage '$stage' (must be 0-7)"
    return 1
  }
  [[ "$slot" != [abcd] ]] && {
    print -ru2 -- "ziro-defer: invalid slot '$slot' (must be a, b, c, or d)"
    return 1
  }

  # Duplicate check
  if _ziro_defer_core_has_task "$task_id"; then
    print -ru2 -- "ziro-defer: task '$task_id' already registered"
    return 1
  fi

  # Cycle check for --after
  if [[ -n "$after" ]] && ! _ziro_defer_core_cycle_check "$task_id" "$after"; then
    print -ru2 -- "ziro-defer: cycle detected: '$task_id' --after '$after'"
    return 1
  fi

  # Cycle check for --before
  if [[ -n "$before" ]]; then
    if [[ "$before" == "$task_id" ]]; then
      print -ru2 -- "ziro-defer: cycle detected: '$task_id' --before itself"
      return 1
    fi
    if [[ -n "$after" && "$before" == "$after" ]]; then
      print -ru2 -- "ziro-defer: cycle detected: '$task_id' cannot be both --after and --before '$before'"
      return 1
    fi
    if [[ "${_ziro_defer_task_pending_before[$before]:-}" == "$task_id" ]]; then
      print -ru2 -- "ziro-defer: cycle detected: mutual --before between '$task_id' and '$before'"
      return 1
    fi
    if _ziro_defer_core_has_task "$before"; then
      _ziro_defer_task_after[$task_id]="$after"
      if ! _ziro_defer_core_cycle_check "$before" "$task_id"; then
        unset "_ziro_defer_task_after[$task_id]"
        print -ru2 -- "ziro-defer: cycle detected: '$task_id' --before '$before'"
        return 1
      fi
      unset "_ziro_defer_task_after[$task_id]"
    fi
  fi

  # Store properties
  _ziro_defer_task_cmd[$task_id]="$cmd"
  _ziro_defer_task_stage[$task_id]="$stage"
  _ziro_defer_task_slot[$task_id]="$slot"
  _ziro_defer_task_after[$task_id]="$after"
  _ziro_defer_task_before[$task_id]="$before"
  _ziro_defer_task_condition[$task_id]="$condition"
  _ziro_defer_task_timeout[$task_id]="$timeout_ms"
  _ziro_defer_task_status[$task_id]="pending"
  _ziro_defer_task_name[$task_id]="$task_id"

  # ─── Chain model (v2.0.0): populate depends graph ───
  # --after=X → depends[task_id] includes X
  if [[ -n "$after" ]]; then
    _ziro_defer_task_depends[$task_id]="$after"
  fi
  # --before=Y → depends[Y] includes task_id (Y needs to wait for task_id)
  if [[ -n "$before" ]]; then
    if _ziro_defer_core_has_task "$before"; then
      local _ex="${_ziro_defer_task_depends[$before]:-}"
      _ziro_defer_task_depends[$before]="${_ex:+$_ex }$task_id"
      local _ex_after="${_ziro_defer_task_after[$before]:-}"
      _ziro_defer_task_after[$before]="${_ex_after:+$_ex_after }$task_id"
    else
      _ziro_defer_task_pending_before[$task_id]="$before"
    fi
  fi
  # Consume any pending_before entries pointing to us
  # @O(p)-justified: iterate over pending tasks waiting for $task_id. Zero-fork.
  local _pending
  for _pending in ${(k)_ziro_defer_task_pending_before}; do
    if [[ "${_ziro_defer_task_pending_before[$_pending]}" == "$task_id" ]]; then
      local _ex2="${_ziro_defer_task_depends[$task_id]:-}"
      _ziro_defer_task_depends[$task_id]="${_ex2:+$_ex2 }$_pending"
      local _ex2_after="${_ziro_defer_task_after[$task_id]:-}"
      _ziro_defer_task_after[$task_id]="${_ex2_after:+$_ex2_after }$_pending"
      unset "_ziro_defer_task_pending_before[$_pending]"
    fi
  done

  # Enqueue
  _ziro_defer_core_queue_push "$stage" "$slot" "$task_id"
  return 0
}

# -----------------------------------------------------------------------------
# _ziro_defer_core_unregister <task_id>
# Removes a task from the registry and its queue.
# -----------------------------------------------------------------------------
_ziro_defer_core_unregister() {
  emulate -L zsh
  local task_id="$1"
  _ziro_defer_core_has_task "$task_id" || return 1

  local stage="${_ziro_defer_task_stage[$task_id]}"
  local slot="${_ziro_defer_task_slot[$task_id]}"

  # Remove from queue
  _ziro_defer_core_queue_remove "$stage" "$slot" "$task_id"

  # Clear properties
  unset "_ziro_defer_task_cmd[$task_id]"
  unset "_ziro_defer_task_stage[$task_id]"
  unset "_ziro_defer_task_slot[$task_id]"
  unset "_ziro_defer_task_after[$task_id]"
  unset "_ziro_defer_task_before[$task_id]"
  unset "_ziro_defer_task_pending_before[$task_id]"
  unset "_ziro_defer_task_depends[$task_id]"
  unset "_ziro_defer_task_condition[$task_id]"
  unset "_ziro_defer_task_timeout[$task_id]"
  unset "_ziro_defer_task_status[$task_id]"
  unset "_ziro_defer_task_name[$task_id]"
  return 0
}

# -----------------------------------------------------------------------------
# _ziro_defer_core_task_status <task_id>
# Prints current status string. Empty if task not found.
# -----------------------------------------------------------------------------
_ziro_defer_core_task_status() {
  emulate -L zsh
  print -r -- "${_ziro_defer_task_status[$1]:-}"
}
