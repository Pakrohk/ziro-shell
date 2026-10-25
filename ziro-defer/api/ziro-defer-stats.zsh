# api/ziro-defer-stats.zsh - Aggregate metrics.jsonl reporter.
# Per ARCHITECTURE S3.5 and Spec 005 §9 R22.
# Zero forks: uses zsh/mapfile + native parameter expansion (no awk/grep/jq).

emulate -L zsh

_ziro_defer_api_stats_extract_int() {
  emulate -L zsh
  local line="$1" key="$2"
  local v="${line##*,\"${key}\":}"
  v="${v%%,*}"
  v="${v%%[^0-9-]*}"
  REPLY="$v"
}

_ziro_defer_api_stats_extract_str() {
  emulate -L zsh
  local line="$1" key="$2"
  local v="${line##*,\"${key}\":}"
  v="${v%%,*}"
  v="${v%%[^a-z]*}"
  REPLY="$v"
}

ziro-defer-stats() {
  emulate -L zsh
  local metrics_file="${XDG_CACHE_HOME:-$HOME/.cache}/ziro/defer/metrics.jsonl"

  # @O(1)-justified: single existence check, no loop.
  [[ -r "$metrics_file" ]] || { print -- "No metrics recorded yet."; return 0; }

  zmodload zsh/mapfile 2>/dev/null
  local content="${mapfile[$metrics_file]}"
  [[ -z "$content" ]] && { print -- "No metrics recorded yet."; return 0; }

  local -a lines=("${(f)content}")
  local -A stage_total stage_count
  local -i total_lines=0 cache_hits=0

  # @O(n)-justified: one pass over N metric records, unavoidable for aggregation.
  # Zero-fork per iteration (native parameter expansion only).
  local line stage elapsed cached
  for line in "${lines[@]}"; do
    [[ -z "$line" ]] && continue
    [[ "$line" == *'"stage":'* ]] || continue
    (( total_lines++ ))

    _ziro_defer_api_stats_extract_int "$line" "stage"; stage="$REPLY"
    _ziro_defer_api_stats_extract_int "$line" "elapsed_ms"; elapsed="$REPLY"
    _ziro_defer_api_stats_extract_str "$line" "cached"; cached="$REPLY"

    [[ -z "$stage" || -z "$elapsed" ]] && continue
    (( stage_total[$stage] += elapsed ))
    (( stage_count[$stage]++ ))
    [[ "$cached" == "true" ]] && (( cache_hits++ ))
  done

  print -- "Stage Summary:"
  local -a stage_names=(pre-source bootstrap pre-compinit compinit post-compinit post-prompt idle on-demand)
  local -i i
  # @O(8)-justified: fixed 8-stage iteration, cannot be O(1). Zero-fork.
  for (( i = 0; i <= 7; i++ )); do
    printf "  Stage %d (%-14s): %7dms  (%d tasks)\n" \
      "$i" "${stage_names[i+1]}" \
      "${stage_total[$i]:-0}" "${stage_count[$i]:-0}"
  done

  print -- ""
  print -- "Cache & Totals:"
  printf "  Total records:      %d\n" "$total_lines"
  printf "  Cache hits:         %d\n" "$cache_hits"
  return 0
}
