# api/ziro-defer.zsh - Primary CLI: parse args and register task.
# Per ARCHITECTURE S3.5 and Spec 005 §8 R19.
# Zero forks in arg parsing (pure Zsh). No subshells or command substitutions.

emulate -L zsh

ziro-defer() {
  emulate -L zsh
  local -i stage=5
  local slot="b" name="" after="" before="" condition="" timeout_ms=5000
  local on_key="" measure=0 quiet=0

  # @O(n)-justified: arg parsing requires O(n) where n = arg count.
  # Unavoidable — each arg must be inspected. Zero-fork per iteration.
  while (( $# > 0 )); do
    case "$1" in
      --stage=*)   stage="${1#--stage=}" ;;
      --slot=*)    slot="${1#--slot=}" ;;
      --name=*)    name="${1#--name=}" ;;
      --after=*)   after="${after:+$after }${1#--after=}" ;;
      --depends=*) after="${after:+$after }${1#--depends=}" ;;
      --before=*)  before="${1#--before=}" ;;
      --on-key=*)  on_key="${1#--on-key=}" ;;
      --if-var=*|--if-cmd=*|--if-ssh|--if-not-root|--if-dir=*)
                   condition="${1#--}" ;;
      --timeout=*) timeout_ms="${1#--timeout=}" ;;
      --measure)   measure=1 ;;
      --quiet)     quiet=1 ;;
      --)          shift; break ;;
      --*)         print -ru2 -- "ziro-defer: unknown option: $1"; return 1 ;;
      *)           break ;;
    esac
    shift
  done

  (( $# == 0 )) && { print -ru2 -- "ziro-defer: no command specified"; return 1; }

  # Validate stage/slot before proceeding
  [[ "$stage" != [0-7] ]] && { print -ru2 -- "ziro-defer: invalid stage '$stage' (0-7)"; return 1; }
  [[ "$slot" != [abcd] ]] && { print -ru2 -- "ziro-defer: invalid slot '$slot' (a-d)"; return 1; }

  local cmd="$*"

  # On-key mode: bypass queue, bind ZLE widget directly (per Spec 005 §8 R19)
  if [[ -n "$on_key" ]]; then
    _ziro_defer_api_bind_key "$on_key" "$cmd"
    return $?
  fi

  # Auto-generate task_id if --name not provided
  [[ -z "$name" ]] && name="ziro_${RANDOM}_${RANDOM}"

  _ziro_defer_core_register "$name" "$stage" "$slot" "$cmd" \
    "$after" "$before" "$condition" "$timeout_ms"
}

# Upstream compatibility alias (RULES R9.3)
zsh-defer() { ziro-defer "$@" }
