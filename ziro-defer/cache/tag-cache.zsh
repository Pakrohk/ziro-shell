# cache/tag-cache.zsh - In-memory tag→path resolution map (Spec 005 §5 R9.4).
# Session-scoped only (never persisted to disk).

emulate -L zsh

# In-memory associative array (session lifetime)
typeset -gA _ziro_defer_tag_map=()

# _ziro_defer_cache_tag_get <tag>
# Sets REPLY to resolved path or empty. Returns 0 if found.
# @O(1)-justified: single assoc lookup.
_ziro_defer_cache_tag_get() {
  emulate -L zsh
  local tag="$1"
  [[ -z "$tag" ]] && { REPLY=""; return 1; }
  local val="${_ziro_defer_tag_map[$tag]:-}"
  REPLY="$val"
  [[ -n "$val" ]]
}

# _ziro_defer_cache_tag_set <tag> <target_path>
# @O(1)-justified: single assoc assignment.
_ziro_defer_cache_tag_set() {
  emulate -L zsh
  local tag="$1" target_path="$2"
  [[ -z "$tag" ]] && return 1
  _ziro_defer_tag_map[$tag]="$target_path"
  return 0
}

# _ziro_defer_cache_tag_clear
# @O(1)-justified: array reset.
_ziro_defer_cache_tag_clear() {
  emulate -L zsh
  _ziro_defer_tag_map=()
  return 0
}

# _ziro_defer_cache_tag_list
# Prints all tags one per line (sorted).
_ziro_defer_cache_tag_list() {
  emulate -L zsh
  local tag
  # @O(n log n)-justified: sorting output is a single native call, unavoidable for
  # deterministic output. Zero-fork.
  for tag in ${(ok)_ziro_defer_tag_map}; do
    print -r -- "$tag"
  done
}
