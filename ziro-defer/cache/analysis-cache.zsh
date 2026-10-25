# cache/analysis-cache.zsh - Plugin analyzer JSON cache (Spec 005 §5 R9.3).
# TTL: 7 days default (RULES R5.2). Invalidated when plugin dir mtime changes.

emulate -L zsh
zmodload zsh/stat 2>/dev/null || true
zmodload zsh/mapfile 2>/dev/null || true

# _ziro_defer_cache_analysis_path <plugin_slug>
# Sets REPLY to analysis cache file path.
# @O(1)-justified: single path construction, zero-fork.
_ziro_defer_cache_analysis_path() {
  emulate -L zsh
  local slug="$1"
  [[ -z "$slug" ]] && { REPLY=""; return 1; }
  _ziro_defer_lib_cache_dir_for analysis
  REPLY="${REPLY}/${slug}.json"
  return 0
}

# _ziro_defer_cache_analysis_valid <plugin_slug> [plugin_dir] [ttl_seconds]
# Returns 0 if cache exists and is fresh (age < TTL, and if plugin_dir given, cache newer).
# @O(1)-justified: single stat comparison, no loop, no fork.
_ziro_defer_cache_analysis_valid() {
  emulate -L zsh
  local slug="$1" plugin_dir="${2:-}" ttl="${3:-604800}"  # 7 days default
  _ziro_defer_cache_analysis_path "$slug" || return 1
  local cache_file="$REPLY"
  [[ -r "$cache_file" ]] || return 1

  _ziro_defer_lib_cache_age_seconds "$cache_file" || return 1
  (( REPLY < ttl )) || return 1

  # If plugin_dir given, cache must be newer than plugin dir (RULES R5.2)
  if [[ -n "$plugin_dir" && -d "$plugin_dir" ]]; then
    local -a p_stat=() c_stat=()
    zstat -A p_stat +mtime "$plugin_dir" 2>/dev/null || return 1
    zstat -A c_stat +mtime "$cache_file" 2>/dev/null || return 1
    (( c_stat[1] >= p_stat[1] )) || return 1
  fi
  return 0
}

# _ziro_defer_cache_analysis_read <plugin_slug>
# Sets REPLY to cached JSON or empty string.
# @O(1)-justified: single mapfile read, zero-fork.
_ziro_defer_cache_analysis_read() {
  emulate -L zsh
  local slug="$1"
  _ziro_defer_cache_analysis_path "$slug" || { REPLY=""; return 1; }
  local cache_file="$REPLY"
  [[ -r "$cache_file" ]] || { REPLY=""; return 1; }
  REPLY="${mapfile[$cache_file]}"
  return 0
}

# _ziro_defer_cache_analysis_write <plugin_slug> <json>
# @O(1)-justified: atomic file write, zero-fork.
_ziro_defer_cache_analysis_write() {
  emulate -L zsh
  local slug="$1" json="$2"
  _ziro_defer_cache_analysis_path "$slug" || return 1
  local cache_file="$REPLY"
  _ziro_defer_lib_cache_write_atomic "$cache_file" "$json"
}

# _ziro_defer_cache_analysis_invalidate <plugin_slug>
# @O(1)-justified: file removal, zero-fork.
_ziro_defer_cache_analysis_invalidate() {
  emulate -L zsh
  _ziro_defer_cache_analysis_path "$1" || return 1
  local cache_file="$REPLY"
  rm -f "$cache_file" 2>/dev/null
  return 0
}
