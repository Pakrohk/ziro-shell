#!/usr/bin/env zsh
# ziro-shell — Core utility helper functions
# Layer: 0 (Shell Helpers) · Spec: 006 v0.2.1
# Loaded via ziro-defer: hot-path cost is 0ms.
# ADR-009 compliant: pure functions, fast built-in checks, minimal subshells.

# ─── Navigation Helpers ───

mkcd() {
  if (( ! $# )); then
    print -u2 "usage: mkcd <directory>"
    return 1
  fi
  mkdir -p -- "$1" && builtin cd -- "$1"
}

take() {
  mkcd "$@"
}

'..'() {
  builtin cd ..
}

'...'() {
  builtin cd ../..
}

'....'() {
  builtin cd ../../..
}

# ─── Universal Extraction ───

extract() {
  if (( ! $# )); then
    print -u2 "usage: extract <archive-file>..."
    return 1
  fi

  local target
  local success=0

  for target in "$@"; do
    if [[ ! -f "$target" ]]; then
      print -u2 "extract: '$target' is not a valid file"
      success=1
      continue
    fi

    case "${target:l}" in
      *.tar.bz2|*.tbz2)   tar xjf "$target" ;;
      *.tar.gz|*.tgz)     tar xzf "$target" ;;
      *.tar.xz|*.txz)     tar xJf "$target" ;;
      *.tar.zst)          tar --zstd -xf "$target" 2>/dev/null || zstd -dc "$target" | tar xf - ;;
      *.tar)              tar xf "$target" ;;
      *.bz2)              bunzip2 "$target" ;;
      *.rar)              unrar x "$target" ;;
      *.gz)               gunzip "$target" ;;
      *.zip)              unzip -q "$target" ;;
      *.z)                uncompress "$target" ;;
      *.7z)               7z x "$target" ;;
      *.xz)               unxz "$target" ;;
      *.zst)              unzstd "$target" ;;
      *)
        print -u2 "extract: unknown archive format: '$target'"
        success=1
        ;;
    esac
  done

  return $success
}

# ─── Clipboard Integration (Cross-Platform) ───

# Spec 022 M2: clipboard buffer path resolver
_ziro_clipboard_buffer_path() {
  emulate -L zsh
  if [[ -n "${XDG_RUNTIME_DIR:-}" ]] && [[ -d "$XDG_RUNTIME_DIR" ]] && [[ -w "$XDG_RUNTIME_DIR" ]]; then
    print -- "$XDG_RUNTIME_DIR/.ziro-clipboard"
  else
    print -- "/tmp/.ziro_clipboard-${UID}"
  fi
}

# Spec 022 M2: headless detection
_ziro_is_headless() {
  [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]
}

# Spec 022 M2: 24h cleanup precmd hook (only if /tmp fallback buffer exists)
_ziro_cleanup_old_clipboard_buffers() {
  emulate -L zsh
  local buf="/tmp/.ziro_clipboard-${UID}"
  [[ -f "$buf" ]] && find /tmp -maxdepth 1 -name '.ziro_clipboard-*' -mmin +1440 -delete 2>/dev/null
}
autoload -Uz add-zsh-hook 2>/dev/null
if (( $+functions[add-zsh-hook] )); then
  add-zsh-hook precmd _ziro_cleanup_old_clipboard_buffers
fi

# ─── OSC 52 support (spec 023 R1, R2, R9) ───

# Level 1 detection: environment heuristic (zero overhead, no TTY)
_ziro_osc52_env_supported() {
  emulate -L zsh
  [[ -n "${KITTY_WINDOW_ID:-}" ]] && return 0
  [[ -n "${WEZTERM_PANE:-}" ]] && return 0
  [[ -n "${ALACRITTY_WINDOW_ID:-}" ]] && return 0
  [[ -n "${GHOSTTY_RESOURCES_DIR:-}" ]] && return 0
  [[ "${TERM_PROGRAM:-}" == "iTerm.app" ]] && return 0
  [[ "${TERM:-}" == *kitty* || "${TERM:-}" == *alacritty* || "${TERM:-}" == *wezterm* || "${TERM:-}" == *foot* || "${TERM:-}" == rxvt-unicode* ]] && return 0
  # User-overridable term allowlist (space-separated glob patterns)
  if [[ -n "${ZIRO_OSC52_TERM_ALLOWLIST:-}" ]]; then
    local pat
    for pat in ${=ZIRO_OSC52_TERM_ALLOWLIST}; do
      [[ "${TERM:-}" == ${~pat} ]] && return 0
    done
  fi
  return 1
}

# Level 2 detection: DA1 query (read-only, 100ms timeout)
_ziro_osc52_da1_supported() {
  emulate -L zsh
  [[ "${ZIRO_OSC52_DA1_DISABLE:-0}" == "1" ]] && return 1
  [[ -t 1 ]] || return 1
  local response=""
  # Send DA1, read response with 100ms timeout
  { printf '\e[>c' && IFS= read -t 0.1 -r response } 2>/dev/null || return 1
  [[ "$response" == *";52;"* || "$response" == *";52"* ]]
}

# Send OSC 52 escape with base64-encoded stdin
_ziro_osc52_copy() {
  emulate -L zsh
  local payload
  payload=$(base64 | tr -d '\r\n')
  [[ -z "$payload" ]] && return 1
  local seq=$'\e]52;c;'"${payload}"$'\a'
  if [[ "${ZIRO_OSC52_TEST_OUTPUT:-0}" == "1" ]]; then
    # Hermetic test hook (spec 023 R9) — write to stdout for capture
    printf '%s' "$seq"
  else
    # Production: write to /dev/tty
    printf '%s' "$seq" >/dev/tty 2>/dev/null || return 1
  fi
  return 0
}

clipcopy() {
  emulate -L zsh

  # Layer 1: GUI native (zero overhead — return before OSC 52 detection)
  if [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    if (( $+commands[wl-copy] )); then wl-copy "$@"; return 0; fi
    if (( $+commands[xclip] )); then xclip -selection clipboard "$@"; return 0; fi
    if (( $+commands[xsel] )); then xsel --clipboard --input "$@"; return 0; fi
    if (( $+commands[clip.exe] )); then clip.exe "$@"; return 0; fi
  fi

  # Layer 2: macOS native (before OSC 52 because Apple Terminal.app doesn't support it)
  if [[ "$(uname -s)" == "Darwin" ]] && (( $+commands[pbcopy] )); then
    pbcopy "$@"; return 0
  fi

  # Layer 3: OSC 52 (headless only, cached detection)
  if [[ "${_ZIRO_OSC52_CONFIRMED:-}" != "1" && "${_ZIRO_OSC52_CONFIRMED:-}" != "0" ]]; then
    if _ziro_osc52_env_supported || _ziro_osc52_da1_supported; then
      typeset -g _ZIRO_OSC52_CONFIRMED=1
    else
      typeset -g _ZIRO_OSC52_CONFIRMED=0
    fi
  fi
  if [[ "${_ZIRO_OSC52_CONFIRMED}" == "1" ]]; then
    [[ "${ZIRO_CLIPBOARD_VERBOSE:-0}" == "1" ]] && print -u2 "clipcopy: using layer 3 (OSC 52)"
    if [[ $# -gt 0 ]]; then
      print -rn -- "$*" | _ziro_osc52_copy && return 0
    else
      _ziro_osc52_copy && return 0
    fi
    # If OSC 52 fails, fall through to file buffer
  fi

  # Layer 4: file buffer
  local buf="$(_ziro_clipboard_buffer_path)"
  [[ "${ZIRO_CLIPBOARD_VERBOSE:-0}" == "1" ]] && print -u2 "clipcopy: using layer 4 (file buffer: $buf)"
  if (( $+commands[cat] )); then
    if [[ $# -gt 0 ]]; then
      print -r -- "$@" > "$buf" && chmod 600 "$buf" 2>/dev/null
    else
      cat > "$buf" && chmod 600 "$buf" 2>/dev/null
    fi
    return $?
  fi
  print -u2 "clipcopy: no supported clipboard tool found (wl-copy, pbcopy, xclip, xsel, clip.exe)"
  return 1
}

clippaste() {
  emulate -L zsh

  # Layer 1: GUI native
  if [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    if (( $+commands[wl-paste] )); then wl-paste "$@"; return 0; fi
    if (( $+commands[xclip] )); then xclip -selection clipboard -o "$@"; return 0; fi
    if (( $+commands[xsel] )); then xsel --clipboard --output "$@"; return 0; fi
    if (( $+commands[powershell.exe] )); then powershell.exe -NoProfile -Command Get-Clipboard "$@"; return 0; fi
  fi

  # Layer 2: macOS native
  if [[ "$(uname -s)" == "Darwin" ]] && (( $+commands[pbpaste] )); then
    pbpaste "$@"; return 0
  fi

  # Layer 3: OSC 52 read — unsupported (DD1), skip with verbose notice
  [[ "${ZIRO_CLIPBOARD_VERBOSE:-0}" == "1" ]] && print -u2 "clippaste: OSC 52 read not attempted (unsupported by most terminals)"

  # Layer 4: file buffer
  local buf="$(_ziro_clipboard_buffer_path)"
  if [[ -r "$buf" ]]; then
    cat "$buf"
    return 0
  fi
  print -u2 "clippaste: no clipboard content"
  return 1
}

# ─── open/xdg-open wrappers (spec 023 R6) ───

_ziro_open_wrapper() {
  emulate -L zsh
  local cmd="$1"; shift
  if [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    command "$cmd" "$@"
    return $?
  fi
  # Headless path
  local target="$1"
  [[ -z "$target" ]] && { print -u2 "ziro: $cmd: no argument"; return 1; }
  if [[ "$target" == http://* || "$target" == https://* ]]; then
    print -u2 "ziro: cannot open URLs in headless environment"
    return 1
  fi
  if [[ -f "$target" ]] && file "$target" 2>/dev/null | grep -q 'text'; then
    local pager="${PAGER:-less}"
    (( $+commands[$pager] )) || pager="cat"
    "$pager" "$target"
    return $?
  fi
  print -u2 "ziro: cannot open '$target' in headless environment (no DISPLAY/WAYLAND)"
  return 1
}

xdg-open() { _ziro_open_wrapper xdg-open "$@"; }
open() { _ziro_open_wrapper open "$@"; }

# ─── FZF interactive helpers ───
ff() {
  emulate -L zsh
  (( $+commands[fzf] )) || { print -u2 "ff: fzf not found in PATH"; return 1; }
  local editor="${EDITOR:-nvim}"
  (( $+commands[$editor] )) || editor="vim"
  (( $+commands[$editor] )) || editor="vi"

  local preview_cmd='cat {}'
  (( $+commands[bat] )) && preview_cmd='bat --style=numbers --color=always --line-range :500 {} 2>/dev/null || cat {}'

  local file
  file=$(fzf --preview "$preview_cmd" --header 'Enter: Open in Editor | Esc: Cancel' "$@") || return 0
  [[ -n "$file" ]] && "$editor" "$file"
}

fy() {
  emulate -L zsh
  (( $+commands[fzf] )) || { print -u2 "fy: fzf not found in PATH"; return 1; }
  (( $+commands[yazi] )) || { print -u2 "fy: yazi not found in PATH"; return 1; }

  local preview_cmd='ls -la {}'
  (( $+commands[eza] )) && preview_cmd='eza -la --icons --color=always {} 2>/dev/null || ls -la {}'

  local dir
  dir=$( ( (( $+commands[fd] )) && fd -t d --hidden -E .git 2>/dev/null || find . -mindepth 1 -maxdepth 4 -type d 2>/dev/null ) | \
    fzf --preview "$preview_cmd" --header 'Enter: Open in Yazi | Esc: Cancel' "$@") || return 0
  [[ -n "$dir" ]] && yazi "$dir"
}

fb() {
  emulate -L zsh
  (( $+commands[fzf] )) || { print -u2 "fb: fzf not found in PATH"; return 1; }
  local viewer="cat"
  (( $+commands[bat] )) && viewer="bat"

  local preview_cmd='cat {}'
  (( $+commands[bat] )) && preview_cmd='bat --style=numbers --color=always --line-range :500 {} 2>/dev/null || cat {}'

  local file
  file=$(fzf --preview "$preview_cmd" --header 'Enter: View | Esc: Cancel' "$@") || return 0
  [[ -n "$file" ]] && "$viewer" "$file"
}

fl() {
  emulate -L zsh
  (( $+commands[fzf] )) || { print -u2 "fl: fzf not found in PATH"; return 1; }

  local preview_cmd='ls -la {}'
  (( $+commands[eza] )) && preview_cmd='eza -la --icons --color=always {} 2>/dev/null || ls -la {}'

  local dir
  dir=$( ( (( $+commands[fd] )) && fd -t d --hidden -E .git 2>/dev/null || find . -mindepth 1 -maxdepth 4 -type d 2>/dev/null ) | \
    fzf --preview "$preview_cmd" --header 'Enter: cd | Esc: Cancel' "$@") || return 0
  [[ -n "$dir" ]] && cd "$dir"
}

