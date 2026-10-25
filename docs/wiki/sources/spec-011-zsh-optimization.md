# Spec 011: Zsh Optimization Specification

**Spec ID**: 011  
**Title**: Zsh Optimization Specification (Performance Discipline & Idioms)  
**Version**: 0.1.0  
**Status**: Active  
**Created**: 2026-10-16  
**Parent Specs**: `000-architecture` (Layer 0/3), `004-shell-bootstrap`  
**Relates to**: `ADR-009` (Code Style Guide), `ADR-010-candidate` (Superseded)  

---

## 1. Overview & Purpose

Spec 011 defines the performance and coding standards for all Zsh code written within the Ziro Shell ecosystem. Its primary goal is keeping the Layer 0 shell bootstrap under the **5ms** budget by eliminating process forks, subshells, and redundant control flow.

---

## 2. Layered Strictness Model

- **Hot Path (`< 5.0ms`)**: Shell startup files (`integration.zsh`, `ziro.zsh`). Zero external commands, zero subshells, max 1 file read, `emulate -L zsh`, idempotency guard.
- **Warm Path (`< 100ms`)**: User commands and interactive ZLE widgets. In-memory caching, no forks in loops.
- **Cold Path (Unconstrained)**: Install and update routines. Idempotency and error recovery prioritized.

---

## 3. Core Optimization Guidelines

1. **Eliminate Process Forks**: Use Zsh builtins and modules (`zmodload zsh/datetime` for time, `$(<file)` for reading, `zsh/stat` for file sizes).
2. **Native Parameter Expansion**: Replace `sed`, `tr`, `awk`, and `basename` with native expansions:
   - `${var:u}` (uppercase)
   - `${var%.ext}` (strip suffix)
   - `${path:t}` (tail / basename)
   - `${path:h}` (head / dirname)
3. **Glob Qualifiers**: Filter directory contents during traversal (`*(N.)` for regular files, `*(N/)` for directories) instead of using inner loops with `[[ -f ]]` tests.
4. **Associative Arrays for Dispatch**: Use `typeset -A handlers` for $O(1)$ dispatch tables instead of long `if/elif` ladders.
5. **Hoisted Modules**: Always place `zmodload` statements at file top level with silent fallbacks.

---

## 4. Conditional Optimization (if/elif Replacement)

> *"Do not use imperative `if` when the shell language offers a faster, cleaner idiom."*

- **Default Value Fallback**: `: ${var:="default"}` instead of `if [[ -z $var ]]`.
- **Early Return Guards**: `[[ -r "$f" ]] || return 1` instead of nested `if` trees.
- **Short-Circuit Statements**: `[[ -f "$f" ]] && source "$f"` for single-branch actions.
- **Associative Array Dispatch**: `typeset -A actions=(add h_add del h_del); ${actions[$cmd]:-h_help} "$@"` instead of 5-branch `if/elif`.
- **Precomputed Flags**: `typeset -g _HAS_COLOR=$(( ... ))` with `(( _HAS_COLOR )) && print ...`.
- **Arithmetic Logic**: `(( x > 10 ))` instead of string `if [[ $x -gt 10 ]]`.
- **Idempotent Expansions**: `${path%.zsh}` without prior matching checks.
- **Pattern Jump Tables**: `case` compiled jump tables for wildcard pattern branches.
- **When `if` Remains Mandatory**: Multi-branch side-effects, complex multi-variable preconditions, and wherever clarity exceeds cleverness.

---

## 5. Measurement & Benchmarking Protocol

All performance-sensitive shell changes must be verified using the **Min-of-11** protocol:

```zsh
zsh -c '
zmodload zsh/datetime
for i in {1..11}; do
  t0=$EPOCHREALTIME
  source ./integration.zsh
  t1=$EPOCHREALTIME
  echo "$(( (t1 - t0) * 1000 ))"
  unset ZIRO_LOADED
done | sort -n | head -1'
```

Zero external process forks must be verified via `strace -f -e trace=execve -c zsh -c "source ./integration.zsh"`.
