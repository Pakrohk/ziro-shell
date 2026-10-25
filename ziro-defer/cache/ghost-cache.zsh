# cache/ghost-cache.zsh - LRU candidate cache (Spec 005 §5 R9.6).
# In-memory, max 1000 entries. Invalidated on SIGUSR1 or chpwd.

emulate -L zsh

typeset -gA _ziro_defer_ghost_lru=()      # query -> results
typeset -ga _ziro_defer_ghost_lru_keys=()  # insertion order
typeset -gi _ziro_defer_ghost_lru_max=1000
typeset -gi _ziro_defer_ghost_lru_size=0

# _ziro_defer_cache_ghost_get <query>
# Sets REPLY to results or empty. Returns 0 if hit.
# @O(1)-justified: single assoc lookup.
_ziro_defer_cache_ghost_get() {
  emulate -L zsh
  local query="$1"
  [[ -z "$query" ]] && { REPLY=""; return 1; }
  local val="${_ziro_defer_ghost_lru[$query]:-}"
  if [[ -n "$val" ]]; then
    # Move to end (most-recently-used)
    _ziro_defer_ghost_lru_keys=(${_ziro_defer_ghost_lru_keys:#$query} $query)
    REPLY="$val"
    return 0
  fi
  REPLY=""
  return 1
}

# _ziro_defer_cache_ghost_put <query> <results>
# @O(1)-justified: assoc insert + possible single-key eviction.
_ziro_defer_cache_ghost_put() {
  emulate -L zsh
  local query="$1" results="$2"
  [[ -z "$query" ]] && return 1

  if [[ -z "${_ziro_defer_ghost_lru[$query]:-}" ]]; then
    (( _ziro_defer_ghost_lru_size++ ))
  else
    _ziro_defer_ghost_lru_keys=(${_ziro_defer_ghost_lru_keys:#$query})
  fi

  _ziro_defer_ghost_lru[$query]="$results"
  _ziro_defer_ghost_lru_keys+=("$query")

  # Evict oldest if over max
  if (( _ziro_defer_ghost_lru_size > _ziro_defer_ghost_lru_max )); then
    local evict="${_ziro_defer_ghost_lru_keys[1]}"
    _ziro_defer_ghost_lru_keys=("${_ziro_defer_ghost_lru_keys[@]:1}")
    unset "_ziro_defer_ghost_lru[$evict]"
    (( _ziro_defer_ghost_lru_size-- ))
  fi
  return 0
}

# _ziro_defer_cache_ghost_invalidate
# Called on SIGUSR1 or chpwd.
# @O(1)-justified: memory map reset.
_ziro_defer_cache_ghost_invalidate() {
  emulate -L zsh
  _ziro_defer_ghost_lru=()
  _ziro_defer_ghost_lru_keys=()
  _ziro_defer_ghost_lru_size=0
  return 0
}
