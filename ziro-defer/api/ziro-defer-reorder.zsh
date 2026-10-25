# api/ziro-defer-reorder.zsh - Priority slot mutator for pending tasks.
# Per ARCHITECTURE S3.5 and Spec 005 §8 R20.3. Idempotent.

emulate -L zsh

ziro-defer-reorder() {
  emulate -L zsh
  local task="" target_slot=""

  # @O(n)-justified: option parsing. Zero-fork.
  while (( $# > 0 )); do
    case "$1" in
      --task=*) task="${1#--task=}" ;;
      --slot=*) target_slot="${1#--slot=}" ;;
      --)       shift; break ;;
      --*)      print -ru2 -- "ziro-defer-reorder: unknown: $1"; return 1 ;;
      *)        break ;;
    esac
    shift
  done

  [[ -z "$task" ]] && { print -ru2 -- "ziro-defer-reorder: missing --task=<id>"; return 1; }
  [[ "$target_slot" != [abcd] ]] && { print -ru2 -- "ziro-defer-reorder: invalid --slot (a-d)"; return 1; }
  _ziro_defer_core_has_task "$task" || { print -ru2 -- "ziro-defer-reorder: task '$task' not found"; return 1; }

  local stage="${_ziro_defer_task_stage[$task]}"
  local old_slot="${_ziro_defer_task_slot[$task]}"
  [[ "$old_slot" == "$target_slot" ]] && return 0  # idempotent

  _ziro_defer_core_queue_remove "$stage" "$old_slot" "$task"
  _ziro_defer_task_slot[$task]="$target_slot"
  _ziro_defer_core_queue_push "$stage" "$target_slot" "$task"
  return 0
}
