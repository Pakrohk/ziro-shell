# cache/eval-cache.zsh - Version-keyed eval output cache (Spec 005 §5 R9.1).
# Read (Stage 4 hot path): zero-fork via source builtin + zsh/stat for mtime.
# Write (cold path): zero-fork via zsh/files builtin mv.
#
# Cache key: <cmd_name>_<mtime_hash>.zsh
# Version hash = binary mtime (detects binary updates without forking --version).
# Rationale: capturing --version would require a fork at write time (acceptable cold),
# but mtime is pure stat and detects updates reliably. Documented deviation from
# spec's "version string" — logged here for META_RULE compliance.

emulate -L zsh
zmodload zsh/files 2>/dev/null || true
zmodload zsh/stat 2>/dev/null || true

# _ziro_defer_cache_eval_path <cmd_name>
# Sets REPLY to the cache file path. Returns 1 if binary not found.
# @O(1)-justified: single stat, no fork.
_ziro_defer_cache_eval_path() {
  emulate -L zsh
  local cmd_name="$1"
  [[ -z "$cmd_name" ]] && { REPLY=""; return 1; }

  # Locate binary in $commands (zsh/parameter assoc — zero fork)
  local binary="${commands[$cmd_name]:-}"
  [[ -z "$binary" || ! -r "$binary" ]] && { REPLY=""; return 1; }

  local -a stat_arr=()
  zstat -A stat_arr +mtime "$binary" 2>/dev/null || { REPLY=""; return 1; }
  local mtime="${stat_arr[1]:-0}"
  [[ "$mtime" == "0" ]] && { REPLY=""; return 1; }

  _ziro_defer_lib_cache_dir_for eval-cache
  REPLY="${REPLY}/${cmd_name}_${mtime}.zsh"
  return 0
}

# _ziro_defer_cache_eval_valid <cmd_name>
# Returns 0 if a valid cache file exists for the current binary version.
# @O(1)-justified: single path check, zero-fork.
_ziro_defer_cache_eval_valid() {
  emulate -L zsh
  _ziro_defer_cache_eval_path "$1" || return 1
  local cache_file="$REPLY"
  [[ -r "$cache_file" && -s "$cache_file" ]]
}

# _ziro_defer_cache_eval_source <cmd_name>
# Sources the cached file. Returns 0 on success.
# @O(1)-justified: single source call, zero-fork.
_ziro_defer_cache_eval_source() {
  emulate -L zsh
  _ziro_defer_cache_eval_path "$1" || return 1
  local cache_file="$REPLY"
  [[ -r "$cache_file" ]] || return 1
  source "$cache_file"
}

# _ziro_defer_cache_eval_write <cmd_name> <content>
# Writes content atomically to the current-version cache file.
# @O(1)-justified: atomic file write, zero-fork.
_ziro_defer_cache_eval_write() {
  emulate -L zsh
  local cmd_name="$1" content="$2"
  _ziro_defer_cache_eval_path "$cmd_name" || return 1
  local cache_file="$REPLY"
  _ziro_defer_lib_cache_write_atomic "$cache_file" "$content"
}
