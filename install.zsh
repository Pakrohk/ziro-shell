#!/usr/bin/env zsh
# ziro-shell — bootstrap installer (Layer: 0)
# Guarantees a verified Ziro checkout at ZIRO_HOME and delegates to the declarative Python engine.

_ziro_bootstrap() {
  emulate -L zsh
  setopt err_return no_unset pipe_fail local_options local_traps

  # Auto-allow root in container environments
  if [[ -f /.dockerenv || -f /run/.containerenv || -n "${container:-}" || "${CI:-}" == "true" ]]; then
    ZIRO_ALLOW_ROOT=1
  fi

  # 1. Platform & User Check
  local kernel="$(uname -s 2>/dev/null || echo "Unknown")"
  if [[ "$kernel" != "Linux" && "$kernel" != "Darwin" ]]; then
    print -u2 "ziro: unsupported operating system: $kernel (Linux or macOS required)"
    return 15
  fi

  if (( EUID == 0 )) && [[ "${ZIRO_ALLOW_ROOT:-0}" != "1" ]]; then
    print -u2 "ziro: running as root is not recommended. Set ZIRO_ALLOW_ROOT=1 to override."
    return 16
  fi

  # Helper: Automatic package installation using system package manager
  _ziro_pkg_install() {
    local pkgs=("$@")
    local sudo_cmd=""
    if (( EUID != 0 )); then
      if (( $+commands[sudo] )); then
        sudo_cmd="sudo"
      elif (( $+commands[doas] )); then
        sudo_cmd="doas"
      else
        return 1
      fi
    fi

    if (( $+commands[apt-get] )); then
      DEBIAN_FRONTEND=noninteractive $sudo_cmd apt-get update -qq >/dev/null 2>&1 || true
      DEBIAN_FRONTEND=noninteractive $sudo_cmd apt-get install -y -qq --no-install-recommends "${pkgs[@]}" >/dev/null 2>&1
    elif (( $+commands[pacman] )); then
      $sudo_cmd pacman -Sy --noconfirm "${pkgs[@]}" >/dev/null 2>&1
    elif (( $+commands[dnf] )); then
      $sudo_cmd dnf install -y "${pkgs[@]}" >/dev/null 2>&1
    elif (( $+commands[apk] )); then
      $sudo_cmd apk add "${pkgs[@]}" >/dev/null 2>&1
    elif (( $+commands[brew] )); then
      brew install "${pkgs[@]}" >/dev/null 2>&1
    elif (( $+commands[zypper] )); then
      $sudo_cmd zypper install -y "${pkgs[@]}" >/dev/null 2>&1
    else
      return 1
    fi
    rehash 2>/dev/null || true
  }

  # 2. Zsh Version Check (>= 5.8)
  autoload -Uz is-at-least
  if ! is-at-least 5.8 "${ZSH_VERSION:-0}"; then
    print -u2 "ziro: zsh 5.8 or newer is required (detected ${ZSH_VERSION:-unknown})"
    return 10
  fi

  # 3. Prerequisites & Modern CLI Companions Check
  local -a missing_desc=()
  local -a missing_pkgs=()

  # Check Python 3.11+
  local py=""
  for cand in python3 python python3.13 python3.12 python3.11; do
    if (( $+commands[$cand] )) && "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
      py="$cand"
      break
    fi
  done
  if [[ -z "$py" ]]; then
    missing_desc+=("python3     (Python >= 3.11 runtime — required)")
    if (( $+commands[apt-get] )); then
      missing_pkgs+=(python3.11 python3.11-venv python3 python3-venv ca-certificates)
    elif (( $+commands[brew] )); then
      missing_pkgs+=(python@3.11)
    else
      missing_pkgs+=(python3)
    fi
  fi

  # Check Git
  if ! command -v git >/dev/null 2>&1 && ! (( $+commands[git] )); then
    missing_desc+=("git         (Version control & repo management — required)")
    missing_pkgs+=(git)
  fi

  # Check Starship
  if ! (( $+commands[starship] )) && ! [[ -x "$HOME/.local/bin/starship" || -x "/usr/local/bin/starship" ]]; then
    missing_desc+=("starship    (Prompt engine with icons & status — required)")
    missing_pkgs+=(starship)
  fi

  # Check zoxide (for 'z')
  if ! (( $+commands[zoxide] )) && ! [[ -x "$HOME/.local/bin/zoxide" || -x "/usr/local/bin/zoxide" ]]; then
    missing_desc+=("zoxide      (Smart directory jump 'z' — recommended)")
    missing_pkgs+=(zoxide)
  fi

  # Check eza (for 'lt' and 'll')
  if ! (( $+commands[eza] )) && ! [[ -x "$HOME/.local/bin/eza" || -x "/usr/local/bin/eza" ]]; then
    missing_desc+=("eza         (Modern tree and directory listing with icons — recommended)")
    missing_pkgs+=(eza tree)
  fi

  # Check fzf
  if ! (( $+commands[fzf] )) && ! [[ -x "$HOME/.local/bin/fzf" || -x "/usr/local/bin/fzf" ]]; then
    missing_desc+=("fzf         (Fuzzy interactive search for history & files — recommended)")
    missing_pkgs+=(fzf)
  fi

  if (( ${#missing_desc} > 0 )); then
    print ""
    print "┌────────────────────────────────────────────────────────────┐"
    print "│         Ziro Shell Dependency & Prerequisite Check         │"
    print "└────────────────────────────────────────────────────────────┘"
    print "The following prerequisite(s) and recommended tool(s) were not found:"
    for m in "${missing_desc[@]}"; do
      print "  • $m"
    done
    print ""
    print "You can install them manually yourself, or let Ziro install them for you."

    local auto_install="y"
    if [[ -r /dev/tty && -w /dev/tty ]] && [[ "${ZIRO_NONINTERACTIVE:-0}" != "1" ]]; then
      print -n "Would you like Ziro to install them for you automatically? [Y/n]: " > /dev/tty
      local user_ans=""
      read -r user_ans < /dev/tty
      if [[ -n "$user_ans" ]]; then
        auto_install="$user_ans"
      fi
    fi

    if [[ "$auto_install" =~ ^[Yy]$ || "$auto_install" == "" ]]; then
      print "[*] Installing missing dependencies via system package manager..."
      _ziro_pkg_install "${missing_pkgs[@]}" || true

      # Fallback binary installer for Starship if still missing
      if ! (( $+commands[starship] )) && ! [[ -x "$HOME/.local/bin/starship" ]]; then
        mkdir -p "$HOME/.local/bin"
        if (( $+commands[curl] )); then
          curl -fsSL https://starship.rs/install.sh | sh -s -- -y -b "$HOME/.local/bin" >/dev/null 2>&1 || true
        elif (( $+commands[wget] )); then
          wget -qO- https://starship.rs/install.sh | sh -s -- -y -b "$HOME/.local/bin" >/dev/null 2>&1 || true
        fi
      fi

      # Fallback binary installer for zoxide if still missing
      if ! (( $+commands[zoxide] )) && ! [[ -x "$HOME/.local/bin/zoxide" ]]; then
        mkdir -p "$HOME/.local/bin"
        if (( $+commands[curl] )); then
          curl -sSfL https://raw.githubusercontent.com/ajeetdsouza/zoxide/main/install.sh | sh -s -- --bin-dir "$HOME/.local/bin" >/dev/null 2>&1 || true
        fi
      fi
      rehash 2>/dev/null || true
    else
      print ""
      print "[!] Automatic installation skipped by user."
      print "Please install the missing tools manually using your package manager:"
      if (( $+commands[pacman] )); then
        print "  sudo pacman -S --needed python git starship zoxide eza fzf"
      elif (( $+commands[apt-get] )); then
        print "  sudo apt install -y python3 python3-venv git zoxide fzf eza"
      elif (( $+commands[dnf] )); then
        print "  sudo dnf install -y python3 git starship zoxide eza fzf"
      elif (( $+commands[brew] )); then
        print "  brew install python@3.11 git starship zoxide eza fzf"
      else
        print "  (Install: python >= 3.11, git, starship, zoxide, eza, fzf)"
      fi
      print ""
    fi
  fi

  # Post-check Python 3.11+
  for cand in python3 python python3.13 python3.12 python3.11; do
    if (command -v "$cand" >/dev/null 2>&1 || (( $+commands[$cand] ))) && "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
      py="$cand"
      break
    fi
  done
  if [[ -z "$py" ]]; then
    print -u2 "ziro: Python 3.11 or newer is required to continue. Please install it and re-run."
    return 11
  fi

  # Post-check Git
  if ! command -v git >/dev/null 2>&1 && ! (( $+commands[git] )); then
    print -u2 "ziro: git is required to clone and update repository. Please install it and re-run."
    return 12
  fi

  # Ensure ~/.local/bin is exported in PATH if starship or zoxide installed locally
  if [[ -x "$HOME/.local/bin/starship" && ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    export PATH="$HOME/.local/bin:$PATH"
  fi
  if [[ -x "$HOME/.local/bin/zoxide" && ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    export PATH="$HOME/.local/bin:$PATH"
  fi

  # 4. Resolve ZIRO_HOME (env > XDG > default ~/.ziro)
  local zhome="${ZIRO_HOME:-}"
  if [[ -z "$zhome" ]]; then
    if [[ -n "${XDG_DATA_HOME:-}" ]]; then
      zhome="${XDG_DATA_HOME}/ziro"
    else
      zhome="${HOME}/.ziro"
    fi
  fi

  # 5. Helper: Verify valid Ziro source tree
  _ziro_verify_tree() {
    local dir="$1"
    [[ -d "$dir" && -f "$dir/core/__main__.py" ]] || return 1
    [[ -f "$dir/.ziro-root" || -f "$dir/pyproject.toml" ]] || return 1
    if [[ -f "$dir/pyproject.toml" ]] && ! grep -q 'name = "ziro-shell"' "$dir/pyproject.toml" 2>/dev/null; then
      return 1
    fi
    if [[ -d "$dir/.git" ]] && (( $+commands[git] )); then
      local remote="$(git -C "$dir" config --get remote.origin.url 2>/dev/null || echo "")"
      if [[ -n "$remote" && "$remote" != *Pakrohk/ziro-shell* && "${ZIRO_ALLOW_FORK:-0}" != "1" ]]; then
        print -u2 "ziro: unverified repository origin: $remote (set ZIRO_ALLOW_FORK=1 to allow)"
        return 14
      fi
    fi
    return 0
  }

  # 6. Check existing or local checkout
  local script_dir=""
  local self_src="${(%):-%x}"
  if [[ -n "$self_src" && -f "$self_src" ]]; then
    script_dir="${self_src:A:h}"
  fi

  local target_home="$zhome"
  local skip_clone=0

  if [[ -e "$target_home" ]]; then
    if _ziro_verify_tree "$target_home"; then
      skip_clone=1
      if [[ -d "$target_home/.git" ]] && (( $+commands[git] )); then
        print "[*] Existing Ziro Shell installation detected. Fetching latest updates..."
        git -C "$target_home" fetch -q origin main 2>/dev/null || git -C "$target_home" fetch -q origin 2>/dev/null || true
        git -C "$target_home" pull --ff-only origin main 2>/dev/null || git -C "$target_home" pull --ff-only 2>/dev/null || true
      fi
    else
      print -u2 "ziro: existing target directory $target_home is not a valid Ziro repository"
      return 14
    fi
  elif [[ -n "$script_dir" ]] && _ziro_verify_tree "$script_dir"; then
    if [[ "$script_dir" != "$target_home" ]]; then
      mkdir -p "${target_home:h}"
      ln -sfn "$script_dir" "$target_home"
    fi
    skip_clone=1
  fi

  # 7. Clone if needed (atomic staging via $target_home.tmp.$$)
  if (( skip_clone == 0 )); then
    if ! command -v git >/dev/null 2>&1 && ! (( $+commands[git] )); then
      print -u2 "ziro: git is required to clone repository"
      return 12
    fi

    local repo_url="${ZIRO_REPO_URL:-https://github.com/Pakrohk/ziro-shell.git}"
    if [[ "$repo_url" != *Pakrohk/ziro-shell* && "${ZIRO_ALLOW_FORK:-0}" != "1" ]]; then
      print -u2 "ziro: unverified clone URL: $repo_url (set ZIRO_ALLOW_FORK=1 to allow)"
      return 14
    fi

    local tmp_dir="${target_home}.tmp.$$"
    trap '[[ -d "$tmp_dir" ]] && rm -rf "$tmp_dir"' EXIT INT TERM

    print "[*] Cloning Ziro to $target_home ..."
    local git_args=(clone --depth 1)
    if [[ -n "${ZIRO_REF:-}" ]]; then
      git_args+=(--branch "$ZIRO_REF")
    fi
    git_args+=("$repo_url" "$tmp_dir")

    if ! git "${git_args[@]}" 2>/dev/null; then
      print -u2 "ziro: git clone failed for $repo_url"
      return 13
    fi

    if ! _ziro_verify_tree "$tmp_dir"; then
      print -u2 "ziro: cloned repository failed verification"
      return 14
    fi

    mkdir -p "${target_home:h}"
    mv "$tmp_dir" "$target_home"
    trap - EXIT INT TERM
  fi

  # 8. Prepare arguments and execute engine
  local args=("$@")
  if [[ $# -eq 0 || ("${1:-}" == -* && "${1:-}" != "--help" && "${1:-}" != "-h" && "${1:-}" != "--version" && "${1:-}" != "-v") ]]; then
    args=(install "$@")
  fi
  if [[ "${ZIRO_CLEAN:-0}" == "1" ]]; then
    args+=(--clean)
  fi
  if [[ "${ZIRO_NO_CLEAN:-0}" == "1" ]]; then
    args+=(--no-clean)
  fi

  # TTY handling: if piped, attach /dev/tty if actually openable
  local ret=0
  local can_tty=0
  if [[ -r /dev/tty && -w /dev/tty ]] && (: < /dev/tty) 2>/dev/null; then
    can_tty=1
  fi

  if [[ ! -t 0 ]]; then
    if (( can_tty )); then
      (cd "$target_home" && ZIRO_HOME="$target_home" PYTHONDONTWRITEBYTECODE=1 "$py" -m core "${args[@]}" < /dev/tty)
      ret=$?
    else
      (cd "$target_home" && ZIRO_HOME="$target_home" ZIRO_NONINTERACTIVE=1 PYTHONDONTWRITEBYTECODE=1 "$py" -m core "${args[@]}")
      ret=$?
    fi
  else
    (cd "$target_home" && ZIRO_HOME="$target_home" PYTHONDONTWRITEBYTECODE=1 "$py" -m core "${args[@]}")
    ret=$?
  fi

  return $ret
}

_ziro_bootstrap "$@"
