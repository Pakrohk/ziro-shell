# lib/condition-eval.zsh - Predicate evaluator per RULES R8.
# Uses `case` (compiled jump table) instead of if/elif chain — O(1) dispatch.

emulate -L zsh

_ziro_defer_lib_eval_condition() {
  emulate -L zsh
  local condition="$1"
  [[ -z "$condition" ]] && return 0

  # case: O(1) pattern dispatch (RULES R8.1) — no fork per branch.
  case "$condition" in
    if-var=*)    [[ -n "${(P)${condition#if-var=}}" ]] ;;
    if-cmd=*)    (( $+commands[${condition#if-cmd=}] )) ;;
    if-ssh)      [[ -n "$SSH_CONNECTION" || -n "$SSH_TTY" ]] ;;
    if-not-root) (( EUID != 0 )) ;;
    if-dir=*)    [[ -d "${condition#if-dir=}" ]] ;;
    *)           return 0 ;;
  esac
}
