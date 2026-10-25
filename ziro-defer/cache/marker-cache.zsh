# cache/marker-cache.zsh - Project directory markers (Spec 005 §5 R9.5).
# TTL: 1 hour default + chpwd invalidation (RULES R5.2).

emulate -L zsh
zmodload zsh/stat 2>/dev/null || true
zmodload zsh/mapfile 2>/dev/null || true

# _ziro_defer_cache_marker_hash <dir>
# Sets REPLY to a path-safe hash of the absolute dir path.
# @O(1)-justified: string substitution, zero-fork.
_ziro_defer_cache_marker_hash() {
  emulate -L zsh
  local dir="${1:A}"
  # Replace / with _ for filename safety
  REPLY="${${dir//\//_}#_}"
  [[ -z "$REPLY" ]] && REPLY="_root"
  return 0
}

# _ziro_defer_cache_marker_path <dir>
# Sets REPLY to marker cache file path.
# @O(1)-justified: single path construction, zero-fork.
_ziro_defer_cache_marker_path() {
  emulate -L zsh
  _ziro_defer_cache_marker_hash "$1"
  local hash="$REPLY"
  _ziro_defer_lib_cache_dir_for markers
  REPLY="${REPLY}/${hash}.json"
  return 0
}

# _ziro_defer_cache_marker_valid <dir> [ttl_seconds]
# @O(1)-justified: single age check, zero-fork.
_ziro_defer_cache_marker_valid() {
  emulate -L zsh
  local dir="$1" ttl="${2:-3600}"
  _ziro_defer_cache_marker_path "$dir" || return 1
  local cache_file="$REPLY"
  [[ -r "$cache_file" ]] || return 1
  _ziro_defer_lib_cache_age_seconds "$cache_file" || return 1
  (( REPLY < ttl ))
}

# _ziro_defer_cache_marker_read <dir>
# @O(1)-justified: single mapfile read, zero-fork.
_ziro_defer_cache_marker_read() {
  emulate -L zsh
  _ziro_defer_cache_marker_path "$1" || { REPLY=""; return 1; }
  local cache_file="$REPLY"
  [[ -r "$cache_file" ]] || { REPLY=""; return 1; }
  REPLY="${mapfile[$cache_file]}"
  return 0
}

# _ziro_defer_cache_marker_write <dir> <json>
# @O(1)-justified: atomic file write, zero-fork.
_ziro_defer_cache_marker_write() {
  emulate -L zsh
  local dir="$1" json="$2"
  _ziro_defer_cache_marker_path "$dir" || return 1
  local cache_file="$REPLY"
  _ziro_defer_lib_cache_write_atomic "$cache_file" "$json"
}

# _ziro_defer_cache_marker_invalidate <dir>
# @O(1)-justified: file removal, zero-fork.
_ziro_defer_cache_marker_invalidate() {
  emulate -L zsh
  _ziro_defer_cache_marker_path "$1" || return 1
  local cache_file="$REPLY"
  rm -f "$cache_file" 2>/dev/null
  return 0
}
