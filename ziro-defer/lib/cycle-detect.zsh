# lib/cycle-detect.zsh - Dependency cycle detection (DFS walk over depends graph).
# Per ARCHITECTURE S3.4 and RULES R7.3.

emulate -L zsh

# _ziro_defer_lib_detect_cycle <current> <target>
# Returns 1 if adding current --after target creates a cycle in depends graph.
# DFS traversal of depends edges. @O(V+E)-justified: full graph walk.
# Zero-fork per iteration (native split, no subshell).
_ziro_defer_lib_detect_cycle() {
  emulate -L zsh
  local current="$1" target="$2"
  [[ -z "$target" ]] && return 0

  local -a to_visit=(${(s: :)target})
  local -i guard=0
  local node deps d
  while (( ${#to_visit} > 0 )); do
    node="${to_visit[1]}"
    to_visit=("${to_visit[@]:1}")
    [[ "$node" == "$current" ]] && return 1
    (( guard++ > 1000 )) && return 1
    deps="${_ziro_defer_task_depends[$node]:-${_ziro_defer_task_after[$node]:-}}"
    if [[ -n "$deps" ]]; then
      for d in ${(s: :)deps}; do
        [[ -n "$d" ]] && to_visit+=("$d")
      done
    fi
  done
  return 0
}
