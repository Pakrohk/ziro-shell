# core/queue.zsh - O(1) priority slot queues per stage.
# Per ARCHITECTURE S3.1 and RULES R6.
#
# Interface:
#   _ziro_defer_core_queue_push <stage> <slot> <task_id>
#   _ziro_defer_core_queue_pop <stage> <slot>      # sets REPLY, returns 0 on success
#   _ziro_defer_core_queue_remove <stage> <slot> <task_id>
#   _ziro_defer_core_queue_size <stage> [slot]     # prints count to stdout
#   _ziro_defer_core_queue_clear <stage> [slot]
#
# Implementation: flat indexed arrays per (stage, slot).
#   _ziro_defer_q_<stage>_<slot> = ( task_id_1 task_id_2 ... )
# Push = O(1) append. Pop = O(1) via head index (stored in _ziro_defer_q_head).
#
# IMPORTANT: pop sets REPLY and does NOT print to stdout. This ensures the
# head index increment persists in the caller's shell scope (no subshell).
# Callers MUST use:
#     _ziro_defer_core_queue_pop 5 b
#     local task_id="$REPLY"
# NOT:
#     local task_id=$(_ziro_defer_core_queue_pop 5 b)   # BROKEN - subshell
#
# Zero I/O, zero subprocess, zero subshell. Complies with RULES R3.1.

emulate -L zsh

# Per (stage, slot): head index into the array (0 = no pop yet)
typeset -gA _ziro_defer_q_head=()

# -----------------------------------------------------------------------------
# _ziro_defer_core_queue_push <stage> <slot> <task_id>
# Appends task_id. O(1). Returns 0.
# -----------------------------------------------------------------------------
_ziro_defer_core_queue_push() {
  emulate -L zsh
  local stage="$1" slot="$2" task_id="$3"
  [[ -z "$stage" || -z "$slot" || -z "$task_id" ]] && return 1

  local qname="_ziro_defer_q_${stage}_${slot}"
  local hkey="${stage}_${slot}"

  if (( ! ${(P)+qname} )); then
    typeset -ga "$qname"
  fi

  local head="${_ziro_defer_q_head[$hkey]:-0}"
  if (( head > 0 )); then
    local -a remaining=("${(@P)qname}")
    remaining=("${remaining[@]:$head}")
    set -A "$qname" "${remaining[@]}"
    _ziro_defer_q_head[$hkey]=0
  fi

  set -A "$qname" "${(@P)qname}" "$task_id"
  return 0
}

# -----------------------------------------------------------------------------
# _ziro_defer_core_queue_pop <stage> <slot>
# Sets REPLY to the head task_id (FIFO). Returns 0 on success, 1 if empty.
# Does NOT print to stdout. Caller must read $REPLY.
# -----------------------------------------------------------------------------
_ziro_defer_core_queue_pop() {
  emulate -L zsh
  local stage="$1" slot="$2"
  local qname="_ziro_defer_q_${stage}_${slot}"
  local hkey="${stage}_${slot}"

  (( ${(P)+qname} )) || return 1

  local -a qarr=("${(@P)qname}")
  (( ${#qarr} == 0 )) && return 1

  local head="${_ziro_defer_q_head[$hkey]:-0}"
  (( head >= ${#qarr} )) && return 1

  REPLY="${qarr[$((head+1))]}"
  head=$(( head + 1 ))
  _ziro_defer_q_head[$hkey]=$head

  if (( head > 100 )); then
    local -a remaining=("${qarr[@]:$head}")
    set -A "$qname" "${remaining[@]}"
    _ziro_defer_q_head[$hkey]=0
  fi

  return 0
}

# -----------------------------------------------------------------------------
# _ziro_defer_core_queue_remove <stage> <slot> <task_id>
# Removes a specific task_id. O(n) but rare. Returns 0 if found, 1 otherwise.
# -----------------------------------------------------------------------------
_ziro_defer_core_queue_remove() {
  emulate -L zsh
  local stage="$1" slot="$2" task_id="$3"
  local qname="_ziro_defer_q_${stage}_${slot}"
  local hkey="${stage}_${slot}"
  (( ${(P)+qname} )) || return 1

  local -a qarr=("${(@P)qname}")
  local head="${_ziro_defer_q_head[$hkey]:-0}"
  if (( head > 0 )); then
    qarr=("${qarr[@]:$head}")
    _ziro_defer_q_head[$hkey]=0
  fi

  local -a newarr=()
  local found=0
  local item
  for item in "${qarr[@]}"; do
    if [[ "$item" == "$task_id" ]]; then
      found=1
    else
      newarr+=("$item")
    fi
  done
  set -A "$qname" "${newarr[@]}"
  return $(( ! found ))
}

# -----------------------------------------------------------------------------
# _ziro_defer_core_queue_size <stage> [slot]
# Prints count to stdout. No subshell trap — caller may use $().
# -----------------------------------------------------------------------------
_ziro_defer_core_queue_size() {
  emulate -L zsh
  local stage="$1" slot="${2:-}"
  local total=0
  local s qname hkey head count

  if [[ -n "$slot" ]]; then
    qname="_ziro_defer_q_${stage}_${slot}"
    hkey="${stage}_${slot}"
    (( ${(P)+qname} )) || { print 0; return 0; }
    head="${_ziro_defer_q_head[$hkey]:-0}"
    count=$(( ${#${(@P)qname}} - head ))
    (( count < 0 )) && count=0
    print -- "$count"
    return 0
  fi

  for s in a b c d; do
    qname="_ziro_defer_q_${stage}_${s}"
    hkey="${stage}_${s}"
    (( ${(P)+qname} )) || continue
    head="${_ziro_defer_q_head[$hkey]:-0}"
    count=$(( ${#${(@P)qname}} - head ))
    (( count > 0 )) && total=$(( total + count ))
  done
  print -- "$total"
}

# -----------------------------------------------------------------------------
# _ziro_defer_core_queue_clear <stage> [slot]
# Clears a queue (or all slots for a stage).
# -----------------------------------------------------------------------------
_ziro_defer_core_queue_clear() {
  emulate -L zsh
  local stage="$1" slot="${2:-}"
  local s qname hkey
  if [[ -n "$slot" ]]; then
    qname="_ziro_defer_q_${stage}_${slot}"
    hkey="${stage}_${slot}"
    [[ -n "${(P)qname+x}" ]] && set -A "$qname"
    _ziro_defer_q_head[$hkey]=0
  else
    for s in a b c d; do
      qname="_ziro_defer_q_${stage}_${s}"
      hkey="${stage}_${s}"
      [[ -n "${(P)qname+x}" ]] && set -A "$qname"
      _ziro_defer_q_head[$hkey]=0
    done
  fi
  return 0
}
