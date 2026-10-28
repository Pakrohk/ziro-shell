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

clipcopy() {
  emulate -L zsh

  if (( $+commands[wl-copy] )); then
    wl-copy "$@"
  elif (( $+commands[pbcopy] )); then
    pbcopy "$@"
  elif (( $+commands[xclip] )); then
    xclip -selection clipboard "$@"
  elif (( $+commands[xsel] )); then
    xsel --clipboard --input "$@"
  elif (( $+commands[clip.exe] )); then
    clip.exe "$@"
  else
    print -u2 "clipcopy: no supported clipboard tool found (wl-copy, pbcopy, xclip, xsel, clip.exe)"
    return 1
  fi
}

clippaste() {
  emulate -L zsh

  if (( $+commands[wl-paste] )); then
    wl-paste "$@"
  elif (( $+commands[pbpaste] )); then
    pbpaste "$@"
  elif (( $+commands[xclip] )); then
    xclip -selection clipboard -o "$@"
  elif (( $+commands[xsel] )); then
    xsel --clipboard --output "$@"
  elif (( $+commands[powershell.exe] )); then
    powershell.exe -NoProfile -Command Get-Clipboard "$@"
  else
    print -u2 "clippaste: no supported clipboard tool found (wl-paste, pbpaste, xclip, xsel, powershell.exe)"
    return 1
  fi
}

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

