# lib/toml-parser.zsh - Minimal TOML reader per ARCHITECTURE S3.4 / RULES R13.5.

emulate -L zsh

# @O(lines)-justified: called only at config load (Phase 4). Loop is O(lines) and
# unavoidable for line-by-line TOML parsing. Phase 4 will cache results
# in an associative array for O(1) lookups; this function stays cold.
# Zero-fork per iteration (uses read builtin, not $(...)).
_ziro_defer_lib_toml_get() {
  emulate -L zsh
  local file="$1" section="$2" key="$3" default="${4:-}"

  [[ -r "$file" ]] || { REPLY="$default"; return 1; }

  local in_section=0 line k v
  while IFS= read -r line || [[ -n "$line" ]]; do
    # Guard clauses (short-circuit, not if)
    [[ "$line" == \#* ]] && continue
    [[ -z "${line//[[:space:]]/}" ]] && continue

    # Section header detection — single pattern match, O(1)
    if [[ "$line" == \[*\] ]]; then
      local sec="${line#\[}"
      sec="${sec%\]}"
      sec="${sec//[[:space:]]/}"
      [[ "$sec" == "$section" ]] && in_section=1 || in_section=0
      continue
    fi

    (( in_section )) || continue

    k="${line%%=*}"
    k="${k//[[:space:]]/}"
    v="${line#*=}"
    v="${v#"${v%%[![:space:]]*}"}"
    v="${v%"${v##*[![:space:]]}"}"
    v="${v#\"}"
    v="${v%\"}"

    if [[ "$k" == "$key" ]]; then
      REPLY="$v"
      return 0
    fi
  done < "$file"

  REPLY="$default"
  return 1
}
