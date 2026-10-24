#!/usr/bin/env zsh
# ziro-shell — Layer 0 bootstrap integration
# Layer: 0 (Shell Bootstrap)
# Spec: 004
# AUTO-GENERATED: no
#
# Hot-path file. Must stay under the 5ms budget (spec 004 R1).
# Sources znap, ziro-defer, and the generated plugin list.

# Idempotency guard
(( ${+ZIRO_LOADED} )) && return 0

# Resolve paths (XDG-compliant with legacy fallback)
: ${XDG_DATA_HOME:="$HOME/.local/share"}
: ${XDG_CONFIG_HOME:="$HOME/.config"}
: ${XDG_CACHE_HOME:="$HOME/.cache"}
: ${ZIRO_DATA:="$XDG_DATA_HOME/ziro"}
: ${ZIRO_CONFIG:="$XDG_CONFIG_HOME/ziro"}
: ${ZIRO_CACHE:="$XDG_CACHE_HOME/ziro"}
: ${ZIRO_HOME:="$HOME/.ziro"}  # legacy compat (repo root)
export ZIRO_DATA ZIRO_CONFIG ZIRO_CACHE ZIRO_HOME

# Add completions directory to fpath if present
local _ziro_comp="${ZIRO_DATA:-$XDG_DATA_HOME/ziro}/completions"
if [[ -d "$_ziro_comp" && ! ${fpath[(Ie)$_ziro_comp]} ]]; then
  fpath=("$_ziro_comp" $fpath)
fi

# Source znap (permanent backend, ADR-002)
if [[ -r "$ZIRO_DATA/vendor/znap/znap.zsh" ]]; then
  source "$ZIRO_DATA/vendor/znap/znap.zsh"
elif [[ -r "$ZIRO_HOME/vendor/znap/znap.zsh" ]]; then
  source "$ZIRO_HOME/vendor/znap/znap.zsh"
fi

# Fallback chain (per Spec 004 R2 + ADR-002):
# 1. Ziro-defer (canonical fork — when available)
# 2. Zsh-defer upstream (current interim)
# 3. Eager stub (safe no-op)
if [[ -r "$ZIRO_HOME/ziro-defer/ziro-defer.plugin.zsh" ]]; then
  source "$ZIRO_HOME/ziro-defer/ziro-defer.plugin.zsh"
elif [[ -r "$ZIRO_DATA/vendor/ziro-defer/ziro-defer.plugin.zsh" ]]; then
  source "$ZIRO_DATA/vendor/ziro-defer/ziro-defer.plugin.zsh"
elif [[ -r "$ZIRO_HOME/vendor/ziro-defer/ziro-defer.plugin.zsh" ]]; then
  source "$ZIRO_HOME/vendor/ziro-defer/ziro-defer.plugin.zsh"
elif [[ -r "$ZIRO_DATA/vendor/ziro-defer/zsh-defer.plugin.zsh" ]]; then
  source "$ZIRO_DATA/vendor/ziro-defer/zsh-defer.plugin.zsh"
elif [[ -r "$ZIRO_HOME/vendor/ziro-defer/zsh-defer.plugin.zsh" ]]; then
  source "$ZIRO_HOME/vendor/ziro-defer/zsh-defer.plugin.zsh"
elif (( $+commands[zsh-defer] )); then
  source "$commands[zsh-defer]"
else
  # Eager fallback: run the command immediately
  ziro-defer() { "$@"; }
fi

# ─── ziro local source: source + .zwc compile for local plugins ───
# Uses `znap compile` when available; falls back to `zcompile`.
_ziro_local_source() {
  emulate -L zsh
  local path=""
  local defer=""
  local target=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --defer) defer="--defer" ;;
      *) path="${1:A}" ;;
    esac
    shift
  done

  # ۱. Resolve target file
  if [[ -d "$path" ]]; then
    local -a patterns=(
      "$path"/*.plugin.zsh(N)
      "$path"/*/*.plugin.zsh(N)
      "$path"/*.zsh(N)
    )
    for f in "${patterns[@]}"; do
      target="$f"
      break
    done
    if [[ -z "$target" ]]; then
      print -u2 "ziro: no plugin file (.plugin.zsh/.zsh) found in $path"
      return 1
    fi
  elif [[ -f "$path" ]]; then
    target="$path"
  else
    print -u2 "ziro: path not found: $path"
    return 1
  fi

  # ۲. Compile with znap if available, else zcompile
  local zwc="${target}.zwc"
  if [[ ! -f "$zwc" || "$target" -nt "$zwc" ]]; then
    if (( $+functions[znap] )); then
      znap compile "$target" 2>/dev/null || zcompile "$target" 2>/dev/null || true
    else
      zcompile "$target" 2>/dev/null || true
    fi
  fi

  # ۳. Source (eager or deferred)
  if [[ "$defer" == "--defer" ]]; then
    if [[ -o interactive ]]; then
      ziro-defer source "$target"
    else
      # In non-interactive shell (scripts, tests, CI), ZLE idle loop is absent;
      # invoke ziro-defer for queueing then source immediately so definitions are active.
      ziro-defer source "$target" 2>/dev/null || true
      source "$target"
    fi
  else
    source "$target"
  fi
}

# ─── ziro-local dispatcher ───
ziro-local() {
  emulate -L zsh
  case "${1:-}" in
    source) shift; _ziro_local_source "$@" ;;
    *) print -u2 "ziro: unknown local subcommand: ${1:-<none>}"; return 2 ;;
  esac
}

# ─── ziro wrapper for local command ───
if ! (( $+functions[ziro] )); then
  ziro() {
    if [[ "$1" == "local" ]]; then
      shift
      ziro-local "$@"
    elif (( $+functions[_ziro_dispatch] )); then
      _ziro_dispatch "$@"
    elif [[ -r "$ZIRO_HOME/ziro.zsh" ]]; then
      source "$ZIRO_HOME/ziro.zsh"
      _ziro_dispatch "$@"
    else
      print -u2 "ziro: unknown command: $1"
      return 1
    fi
  }
fi

# Source the generated plugin list if present
[[ -r "$ZIRO_CONFIG/derived/plugins.gen.zsh" ]] && \
  source "$ZIRO_CONFIG/derived/plugins.gen.zsh"

# ─── Prompt adapter (Spec 004 R1 §7, Spec 006 Principle XIII) ───
typeset -g _ziro_prompt=""
if [[ -r "${ZIRO_CONFIG}/prompt.conf" ]]; then
  _ziro_prompt="$(<"${ZIRO_CONFIG}/prompt.conf")"
fi
_ziro_prompt="${_ziro_prompt//[[:space:]]/}"
if [[ -n "$_ziro_prompt" && "$_ziro_prompt" != "none" && -r "${ZIRO_HOME}/prompts/${_ziro_prompt}.zsh" ]]; then
  source "${ZIRO_HOME}/prompts/${_ziro_prompt}.zsh"
fi
unset _ziro_prompt

# ─── Background update check (non-blocking, opt-out, 24h cache) ───
_ziro_update_check_background() {
  # 1. Non-interactive and non-TTY guard (fast exit for CI, scripts, subshells)
  [[ -o interactive ]] || return 0
  [[ -t 1 ]] || return 0

  # 2. Opt-out guard from defaults.toml
  local cfg="${ZIRO_CONFIG:-$HOME/.config/ziro}/defaults.toml"
  if [[ -f "$cfg" ]]; then
    if grep -qE '^(check_for_updates|enabled)[[:space:]]*=[[:space:]]*false' "$cfg" 2>/dev/null; then
      return 0
    fi
  fi

  local cache_dir="${ZIRO_CACHE:-$HOME/.cache/ziro}"
  local cache_file="$cache_dir/update-check.json"

  # 3. Notification: if cache indicates update is available, alert user once
  if [[ -f "$cache_file" ]]; then
    if grep -q '"available":[[:space:]]*true' "$cache_file" 2>/dev/null; then
      local notify_flag="$cache_dir/.update_notified"
      if [[ ! -f "$notify_flag" ]]; then
        print -P "\n%F{yellow}[*] A new update is available for Ziro Shell! Run '%F{cyan}ziro update%F{yellow}' to apply.%f\n"
        touch "$notify_flag" 2>/dev/null || true
      fi
    fi
  fi

  # 4. Cache TTL check (24h = 86400s)
  if [[ -f "$cache_file" ]]; then
    local last_mtime=0
    zmodload -F zsh/stat b:zstat 2>/dev/null
    local -A s_info
    if zstat -H s_info "$cache_file" 2>/dev/null; then
      last_mtime=${s_info[mtime]:-0}
    fi
    local now=$EPOCHSECONDS
    (( ${+EPOCHSECONDS} )) || local now=$(date +%s)
    if (( now - last_mtime < 86400 )); then
      return 0
    fi
  fi

  # 5. Non-blocking background fetch & check
  (
    if [[ -d "$ZIRO_HOME/.git" ]] && command -v git &>/dev/null; then
      mkdir -p "$cache_dir" 2>/dev/null || true
      cd "$ZIRO_HOME" || exit 0
      git fetch -q origin main >/dev/null 2>&1 || exit 0
      local lhash=$(git rev-parse HEAD 2>/dev/null)
      local rhash=$(git rev-parse origin/main 2>/dev/null)
      local avail="false"
      local behind=0
      if [[ -n "$lhash" && -n "$rhash" && "$lhash" != "$rhash" ]]; then
        behind=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)
        if (( behind > 0 )); then
          avail="true"
          rm -f "$cache_dir/.update_notified" 2>/dev/null || true
        fi
      fi
      local ts=$(date +%s)
      cat > "$cache_file" <<EOF
{"available": $avail, "local": "${lhash:-unknown}", "remote": "${rhash:-unknown}", "behind": $behind, "checked_at": $ts, "error": null}
EOF
    fi
  ) &!
}

_ziro_update_check_background

# Mark bootstrap complete
typeset -g ZIRO_LOADED=1
