# api/ziro-defer-dispatch.zsh - Synchronous stage dispatcher.
# Per ARCHITECTURE S3.5 and Spec 005 §8 R20.1.
# Used by integration.zsh to run stages 2/3/4 before prompt render.

emulate -L zsh

ziro-defer-dispatch() {
  emulate -L zsh
  local -i force=0

  # @O(n)-justified: option parsing. Zero-fork.
  while (( $# > 0 )); do
    case "$1" in
      --force) force=1; shift ;;
      --)      shift; break ;;
      --*)     print -ru2 -- "ziro-defer-dispatch: unknown: $1"; return 1 ;;
      *)       break ;;
    esac
  done

  local -i stage="${1:-5}"
  [[ "$stage" != [0-7] ]] && { print -ru2 -- "ziro-defer-dispatch: invalid stage '$stage' (0-7)"; return 1; }

  _ziro_defer_core_dispatch_stage "$stage"
  return $?
}
