# Migration Guide

This guide details how to migrate to `ziro-shell` from other Zsh frameworks and plugin managers, including Oh My Zsh (OMZ), Prezto, Zinit, Zplug, Zim, and hand-crafted `.zshrc` configurations.

Ziro replaces monolithic framework runtime files with an offline-compiled boot pipeline. By compiling shell logic into wordcode (`.zwc`) and deferring heavy initialization past prompt draw, Ziro reduces interactive startup latency from 150–500ms down to ~16–21ms.

---

## Migration Overview

Legacy managers initialize plugins and completions synchronously on every shell launch, executing hundreds of filesystem stats, directory iterations, and subshell forks. Ziro shifts this work offline:

| Framework | Architecture | Typical Startup | Ziro Equivalent |
| :--- | :--- | :---: | :--- |
| **Oh My Zsh** | Monolithic runtime sourcing + synchronous git checks | 200–600 ms | Declarative `load.toml` + async prompt (`starship`) |
| **Prezto** | Modular multi-file loaders + synchronous modules | 150–350 ms | 4-tier scheduling + `ziro-defer` stages |
| **Zinit / Zplug** | In-shell Turbo mode hooks (`wait`, `lucid`, `load`) | 50–120 ms | Offline-compiled bytecode + `on-demand` triggers |
| **Zim** | Static build script + minimal modules | 40–80 ms | Zero-fork boot chain + automated analyzer |
| **Custom `.zshrc`** | Linear sequential script sourcing | 80–250 ms | Single-source `ziro-boot.zwc` + `~/.zshrc.local` |

---

## Feature Mapping

Legacy frameworks bundle plugins that frequently duplicate functionality or introduce heavy subshell overhead. The table below maps standard community plugins to their modern, high-performance Ziro configurations:

| Legacy Plugin (OMZ / Community) | Purpose | Recommended Ziro Replacement | Timing Tier |
| :--- | :--- | :--- | :--- |
| `zsh-users/zsh-syntax-highlighting` | Syntax highlighting | `fast-syntax-highlighting` | `deferred` (Stage 5) |
| `zsh-users/zsh-autosuggestions` | History autosuggestions | `Pakrohk/ziro-ghost` | `deferred` (Stage 5) |
| `z` / `fasd` / `autojump` | Directory jumping | `zoxide` (eval-cache) | `on-demand` (Command) |
| `junegunn/fzf` | Fuzzy completions & keybindings | `fzf` (eval-cache) | `on-demand` (Key: `^R`, `^T`) |
| `themes/robbyrussell` / `agnoster` | Shell prompt | `starship` | `eager` (Eval-cache) |
| `zsh-users/zsh-completions` | Additional completion specs | `zsh-completions` | `eager` (Pre-compinit) |
| `plugins/git` (OMZ) | Git aliases and helper functions | `ohmyzsh/ohmyzsh` (`subpath = "plugins/git"`) | `eager` |
| `colored-man-pages` (OMZ) | Terminal pager colorization | `ohmyzsh/ohmyzsh` (`subpath = "plugins/colored-man-pages"`) | `deferred` (Stage 5) |
| `MichaelAquilina/zsh-you-should-use`| Alias reminders | `you-should-use` | `deferred` (Stage 5) |
| `Aloxaf/fzf-tab` | Interactive fzf completion menu | `Aloxaf/fzf-tab` | `deferred` (Stage 5) |

---

## Step-by-Step Migration Procedure

### Step 1: Backup Your Existing Configuration

Preserve your current configuration before installing Ziro:

```bash
# Create an archive directory for legacy configuration files
mkdir -p ~/.zsh_migration_backup
cp ~/.zshrc ~/.zsh_migration_backup/zshrc.backup
cp -r ~/.oh-my-zsh ~/.zsh_migration_backup/ 2>/dev/null || true
cp -r ~/.zprezto ~/.zsh_migration_backup/ 2>/dev/null || true
cp -r ~/.local/share/zinit ~/.zsh_migration_backup/ 2>/dev/null || true
```

### Step 2: Extract Personal Aliases, Functions, and Environment Variables

Split your legacy configuration into two categories:
1. **Tool / Plugin definitions**: Handled declaratively in `~/.config/ziro/load.toml`.
2. **Personal environment variables, exports, and custom aliases**: Moved to `~/.zshrc.local`.

Create your local overrides file:

```bash
touch ~/.zshrc.local
```

Extract non-framework configurations from your old `.zshrc` (such as `export PATH`, `export EDITOR`, personal aliases, and custom functions) and append them directly to `~/.zshrc.local`.

### Step 3: Install Ziro Shell

Clone the repository and run the setup script:

```bash
git clone https://github.com/Pakrohk/ziro-shell.git ~/.ziro
cd ~/.ziro
./install.sh
```

The installer establishes:
- `~/.config/ziro/` (configuration files, `load.toml`)
- `~/.cache/ziro/` (compiled artifacts, `ziro-boot.zwc`, completion cache)
- A clean, 7-line `~/.zshrc` that points to Ziro's bootloader.

### Step 4: Add Desired Plugins

Add your required plugins using the `ziro plugin add` command:

```bash
# Eager completions
ziro plugin add zsh-users/zsh-completions --eager

# OMZ Git aliases
ziro plugin add ohmyzsh/ohmyzsh --subpath=plugins/git --eager

# Syntax highlighting & ghost suggestions
ziro plugin add zdharma-continuum/fast-syntax-highlighting --defer=slot:b
ziro plugin add Pakrohk/ziro-ghost --defer=slot:b

# Interactive tab completion
ziro plugin add Aloxaf/fzf-tab --defer=slot:b
```

### Step 5: Run Analyzer and Compile Boot Artifacts

Analyze plugin dependencies, check trust heuristics, and build the initial bytecode image:

```bash
# Run full analysis to generate load.toml
ziro analyze --full

# Compile artifacts into ~/.cache/ziro/ziro-boot.zwc
ziro sync

# Verify environment integrity
ziro doctor
```

---

## Before & After Comparisons

### Case 1: Oh My Zsh (OMZ)

#### Before: Monolithic `.zshrc` (100+ lines)

```zsh
export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME="robbyrussell"

# Synchronous updates and updates check on boot
zstyle ':omz:update' mode reminder

# OMZ plugin array loaded synchronously during boot
plugins=(
  git
  docker
  fzf
  z
  colored-man-pages
  zsh-autosuggestions
  zsh-syntax-highlighting
)

source $ZSH/oh-my-zsh.sh

# User environment variables
export PATH="$HOME/.local/bin:$PATH"
export EDITOR="nvim"

# Hand-rolled aliases
alias ll="ls -lah"
alias g="git"
```

*Problems*: Sourcing `oh-my-zsh.sh` executes dozens of subshell forks, parses theme files synchronously, runs `compinit` without bytecode optimization, and blocks prompt rendering. Average boot time: ~220ms.

#### After: Clean Ziro Setup

**`~/.zshrc` (Managed 7-line entry point):**
```zsh
# ~/.zshrc — Managed by Ziro Shell.
export ZIRO_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/ziro"
export ZIRO_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/ziro"

[[ -f "$HOME/.zshrc.local" ]] && source "$HOME/.zshrc.local"
[[ -f "$ZIRO_CACHE/ziro-boot.zwc" ]] && source "$ZIRO_CACHE/ziro-boot.zwc" || source "$ZIRO_CONFIG/boot.zsh"
```

**`~/.zshrc.local` (User environment & custom aliases):**
```zsh
export PATH="$HOME/.local/bin:$PATH"
export EDITOR="nvim"

alias ll="ls -lah"
alias g="git"
```

**`~/.config/ziro/load.toml` (Declarative load manifest):**
```toml
[[tool]]
name = "ohmyzsh-git"
source = "ohmyzsh/ohmyzsh"
subpath = "plugins/git"
timing = "eager"
order = 2
method = "source"
path = "~/.ziro/ohmyzsh/ohmyzsh/plugins/git/git.plugin.zsh"

[[tool]]
name = "compinit"
timing = "eager"
order = 3
method = "builtin"

[[tool]]
name = "starship"
timing = "eager"
order = 4
method = "eval-cache"
binary = "starship"
init_command = "starship init zsh --print-full-init"
cache_path = "~/.cache/ziro/eval-cache/starship.zsh"

[[tool]]
name = "zoxide"
timing = "on-demand"
order = 11
method = "eval-cache"
binary = "zoxide"
trigger = "command"
trigger_commands = ["z", "zi"]
cache_path = "~/.cache/ziro/eval-cache/zoxide.zsh"

[[tool]]
name = "ziro-ghost"
source = "Pakrohk/ziro-ghost"
timing = "deferred"
order = 20
method = "source"
stage = 5
slot = "b"
path = "~/.ziro/Pakrohk/ziro-ghost/ziro-ghost.plugin.zsh"

[[tool]]
name = "fast-syntax-highlighting"
source = "zdharma-continuum/fast-syntax-highlighting"
timing = "deferred"
order = 21
method = "source"
stage = 5
slot = "b"
path = "~/.ziro/zdharma-continuum/fast-syntax-highlighting/fast-syntax-highlighting.plugin.zsh"
```

*Results*: Clean separation of concerns. Cold shell boot drops to ~16–19ms.

---

### Case 2: Zinit Turbo

#### Before: Complex Turbo-Mode `.zshrc`

```zsh
source "$HOME/.local/share/zinit/zinit.git/zinit.zsh"

# Turbo mode with complex wait/lucid/atload syntax
zinit ice wait"0" lucid
zinit light zsh-users/zsh-completions

zinit ice wait"1" lucid atload"_zsh_autosuggest_start"
zinit light zsh-users/zsh-autosuggestions

zinit ice wait"2" lucid
zinit light zdharma-continuum/fast-syntax-highlighting

zinit ice from"gh-r" as"program"
zinit light junegunn/fzf
```

*Problems*: Turbo mode introduces `first_command_lag` and high `input_lag` (~14.7ms) while deferred hooks compete with the first user command. Dynamic hooks frequently collide or swallow typed characters.

#### After: Ziro Declarative Scheduling

Ziro separates runtime execution into deterministic slots via `load.toml`. Keystroke bindings (`fzf`) trigger on demand; heavy syntax highlighting loads during terminal idle loops with 0.18ms input lag.

---

## Common Pitfalls & Troubleshooting

### 1. `compinit` Executed Multiple Times
- **Symptom**: Startup time increases by 20–40ms, or `compdef: unknown command` errors appear.
- **Cause**: Legacy scripts or plugins manually call `autoload -Uz compinit && compinit` inside `~/.zshrc.local`.
- **Fix**: Remove all manual `compinit` calls from `~/.zshrc.local`. Ziro handles `compinit` natively as an eager builtin (order 3) using an optimized `.zcompdump` cache.

### 2. Missing PATH Additions for On-Demand Tools
- **Symptom**: `ziro sync` fails with binary not found, or on-demand commands fail.
- **Cause**: `$PATH` modifications were placed at the end of the legacy file or not exported in `~/.zshrc.local`.
- **Fix**: Ensure all `$PATH` exports appear at the very beginning of `~/.zshrc.local` so that Ziro's pre-flight checks locate all binaries.

### 3. Ghost Text / Autosuggestion Collisions
- **Symptom**: Double suggestion lines appear or terminal cursor jumps unexpectedly.
- **Cause**: Both `zsh-autosuggestions` and `ziro-ghost` are active simultaneously.
- **Fix**: Disable or remove `zsh-autosuggestions`. Ziro's analyzer enforces `conflicts_with = ["zsh-autosuggestions"]` on `ziro-ghost`. Run `ziro sync` to recompile.

### 4. Outdated Boot Cache
- **Symptom**: Changes to `load.toml` do not appear in a new terminal session.
- **Cause**: `load.toml` was edited manually without running `ziro sync`.
- **Fix**: Always execute `ziro sync` after editing configuration files.
