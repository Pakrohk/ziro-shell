# lib/cache-io.zsh - Shared atomic I/O helpers for all cache controllers.
# Per RULES R5.3 (atomic writes). Uses zsh/files builtins (mv, rm, mkdir) — zero fork.
# Hot-path safe: zero command substitutions, no subshell, no external commands.

emulate -L zsh

# Load zsh/files to make mv, rm, mkdir, etc. builtins (zero-fork atomic ops)
zmodload zsh/files 2>/dev/null || true
zmodload zsh/stat 2>/dev/null || true
zmodload zsh/datetime 2>/dev/null || true

# Base cache directory per RULES R5.5
typeset -g _ZIRO_DEFER_CACHE_ROOT="${XDG_CACHE_HOME:-$HOME/.cache}/ziro/defer"

# _ziro_defer_lib_cache_dir_for <subdir>
# Sets REPLY to the cache subdirectory path. Creates it if missing (best-effort).
# @O(1)-justified: single mkdir call, no loop.
_ziro_defer_lib_cache_dir_for() {
  emulate -L zsh
  local subdir="$1"
  local dir="${_ZIRO_DEFER_CACHE_ROOT}/${subdir}"
  [[ -d "$dir" ]] || mkdir -p "$dir" 2>/dev/null || true
  REPLY="$dir"
  return 0
}

# _ziro_defer_lib_cache_write_atomic <target_file> <content>
# RULES R5.3: write to tmp sibling, then atomic mv -f. Uses zsh/files builtin mv.
# Returns 0 on success, 1 on any failure (never throws).
_ziro_defer_lib_cache_write_atomic() {
  emulate -L zsh
  local target_file="$1" content="$2"
  [[ -z "$target_file" ]] && return 1

  local cache_dir="${target_file:h}"
  [[ -d "$cache_dir" ]] || mkdir -p "$cache_dir" 2>/dev/null || return 1

  local tmp_file="${target_file}.tmp.$$"
  print -r -- "$content" >| "$tmp_file" 2>/dev/null || return 1
  mv -f "$tmp_file" "$target_file" 2>/dev/null || { rm -f "$tmp_file" 2>/dev/null; return 1; }
  return 0
}

# _ziro_defer_lib_cache_mtime <file>
# Sets REPLY to file mtime (integer seconds) via zsh/stat builtin. 0 if missing.
# @O(1)-justified: single zstat call, no fork.
_ziro_defer_lib_cache_mtime() {
  emulate -L zsh
  local file="$1"
  REPLY=0
  [[ -r "$file" ]] || return 1
  local -a stat_arr=()
  zstat -A stat_arr +mtime "$file" 2>/dev/null || return 1
  REPLY="${stat_arr[1]:-0}"
  return 0
}

# _ziro_defer_lib_cache_age_seconds <file>
# Sets REPLY to age in seconds. Negative or large if file missing.
# @O(1)-justified: arithmetic age calculation, no fork.
_ziro_defer_lib_cache_age_seconds() {
  emulate -L zsh
  local file="$1"
  _ziro_defer_lib_cache_mtime "$file" || { REPLY=999999999; return 1; }
  local mtime="$REPLY"
  (( REPLY = EPOCHSECONDS - mtime ))
  return 0
}
