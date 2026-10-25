# cache/zwc-cache.zsh - Bytecode compilation manager (Spec 005 §5 R9.2).
# Invalidation: source -nt source.zwc (RULES R5.2).

emulate -L zsh
zmodload zsh/stat 2>/dev/null || true
zmodload zsh/files 2>/dev/null || true

# _ziro_defer_cache_zwc_valid <source_file>
# Returns 0 if .zwc exists and is newer than source.
# @O(1)-justified: single stat comparison, no loop, no fork.
_ziro_defer_cache_zwc_valid() {
  emulate -L zsh
  local src="$1" zwc="${1}.zwc"
  [[ -r "$src" && -r "$zwc" ]] || return 1
  local -a s_stat=() z_stat=()
  zstat -A s_stat +mtime "$src" 2>/dev/null || return 1
  zstat -A z_stat +mtime "$zwc" 2>/dev/null || return 1
  (( z_stat[1] >= s_stat[1] ))
}

# _ziro_defer_cache_zwc_compile <source_file>
# Compiles to .zwc via zcompile builtin. Returns 0 on success.
# Cold path only — do not call in Stage 0-4.
# @O(1)-justified: single zcompile builtin call, no fork.
_ziro_defer_cache_zwc_compile() {
  emulate -L zsh
  local src="$1"
  [[ -r "$src" ]] || return 1
  zcompile "$src" 2>/dev/null || return 1
  return 0
}

# _ziro_defer_cache_zwc_source <source_file>
# Sources .zwc if valid, else sources plaintext (RULES R5.6 fallback).
# @O(1)-justified: single source call, zero-fork.
_ziro_defer_cache_zwc_source() {
  emulate -L zsh
  local src="$1"
  if _ziro_defer_cache_zwc_valid "$src"; then
    source "${src}.zwc"
  elif [[ -r "$src" ]]; then
    source "$src"
  else
    return 1
  fi
  return 0
}
