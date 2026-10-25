# api/ziro-defer-batch.zsh - Batch registration for multiple plugins.
# Per ARCHITECTURE S3.5 and Spec 005 §8 R20. Reduces overhead vs multiple calls.

emulate -L zsh

# _ziro_defer_batch_process <stage> <slot> <source_mode> <plugins...>
# @O(n)-justified: register N plugins requires N calls. Zero-fork per iteration.
_ziro_defer_batch_process() {
  emulate -L zsh
  local -i stage="$1"
  local slot_str="$2" source_mode="$3"
  shift 3
  local plugin name cmd
  for plugin in "$@"; do
    name="batch_${plugin:t}"
    if [[ "$source_mode" == "znap" ]]; then
      cmd="znap source $plugin"
    else
      cmd="source $plugin"
    fi
    ziro-defer --stage="$stage" --slot="$slot_str" --name="$name" "$cmd"
  done
  return 0
}

ziro-defer-batch() {
  emulate -L zsh
  local -i stage=5
  local slot="b" source_mode="znap"

  # @O(n)-justified: option parsing requires O(n). Zero-fork per iteration.
  while (( $# > 0 )); do
    case "$1" in
      --stage=*)       stage="${1#--stage=}" ;;
      --slot=*)        slot="${1#--slot=}" ;;
      --source-mode=*) source_mode="${1#--source-mode=}" ;;
      --)              shift; break ;;
      --*)             print -ru2 -- "ziro-defer-batch: unknown: $1"; return 1 ;;
      *)               break ;;
    esac
    shift
  done

  (( $# == 0 )) && { print -ru2 -- "ziro-defer-batch: no plugins specified"; return 1; }

  case "$source_mode" in
    znap|source) : ;;
    *) print -ru2 -- "ziro-defer-batch: invalid source-mode '$source_mode' (znap|source)"; return 1 ;;
  esac

  local -i limit="${_ZIRO_DEFER_BATCH_SIZE_LIMIT:-50}"
  local -i total=$#

  if (( total <= limit )); then
    _ziro_defer_batch_process "$stage" "$slot" "$source_mode" "$@"
  else
    local -a all_args=("$@")
    local -i offset=0
    local -i chunk_count=0
    (( chunk_count = (total + limit - 1) / limit ))
    print -ru2 -- "ziro-defer-batch: $total plugins exceeds limit ($limit); splitting into $chunk_count batches"
    # @O(chunks)-justified: process each chunk sequentially, each chunk bounded.
    # Unavoidable per spec §13.1. Zero-fork per chunk (delegates to helper).
    local -i i start end
    for (( i = 0; i < chunk_count; i++ )); do
      (( start = offset + 1 ))
      (( end = offset + limit ))
      (( end > total )) && end=$total
      local -a chunk=("${(@)all_args[start,end]}")
      _ziro_defer_batch_process "$stage" "$slot" "$source_mode" "${chunk[@]}"
      offset=$end
    done
  fi

  return 0
}
