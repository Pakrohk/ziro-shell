# Ziro Shell — Command Guide & Workflow Cheatsheet

> A practical guide to daily workflows, navigation aliases, the `ziro` CLI suite, and smart directory jumping with real-time history synchronization.

<div align="center">
  <img src="../assets/terminal-demo.svg" alt="Ziro Shell Commands Demo" width="100%" />
</div>

---

## 1. Directory Listing & File Inspection

Ziro upgrades directory navigation with classified indicators, grouped sorting, and automatic fallback between `eza` and native `ls`.

| Command | Tool / Engine | Flags Applied | Description |
|:---|:---|:---|:---|
| `ls` | Native `ls` / `gls` | `-F --group-directories-first --color=auto` | Classified listing: directories sorted first with trailing `/`, executables marked with `*`. |
| `ll` | `eza` *(fallback: `ls -la -F`)* | `-la --icons --group-directories-first` | Detailed listing with file permissions, human-readable sizes, and glyph icons. |
| `la` | `eza` *(fallback: `ls -a -F`)* | `-a --icons --group-directories-first` | Detailed listing including hidden files (`.*`). |
| `lt` | `eza` *(fallback: `ls -R`)* | `--tree --level=2 --icons` | Interactive 2-level hierarchical directory tree view. |

### Visual Indicators in `ls`
- **Directories**: Trailing `/` (e.g. `Projects/`, `Documents/`) and rendered first in alphabetical order.
- **Executables**: Trailing `*` (e.g. `build.sh*`, `deploy*`).
- **Symlinks**: Trailing `@` (pointing to destination).
- **Sockets / FIFOs**: Trailing `=` or `|`.

---

## 2. Fast Directory Navigation & Traversal

Avoid repetitive `cd ../../..` typing. Ziro provides defensive parent shortcuts and automatic directory switching.

| Shortcut | Expanded Command | Purpose |
|:---:|:---|:---|
| `..` | `cd ..` | Navigate 1 level up |
| `...` | `cd ../..` | Navigate 2 levels up |
| `....` | `cd ../../..` | Navigate 3 levels up |
| `dir_name` | `autocd` | Simply typing a directory path changes directly into it (e.g. `Projects` ➔ changes to `Projects/`). |

---

## 3. Smart Jumping with `z` (Zoxide) & History Synchronization

Ziro integrates [zoxide](https://github.com/ajeetdsouza/zoxide) for fast filesystem traversal using a **frecency** (frequency + recency) ranking algorithm.

### Real-Time History Synchronization (`cd` ↔ `z`)
By default in standard shells, `cd` and `z` maintain separate histories until manual initialization. **In Ziro, they are unified in real-time**:
- Every time you change directory via `cd`, `..`, or `autocd`, Ziro's `chpwd` lifecycle hook immediately updates the `zoxide` database.
- Even if you have never typed `z` before in a new project, `z` already knows about every directory you have visited.
- Historical `cd` paths from `~/.zsh_history` are seamlessly recognized.

### Common `z` Workflows

```bash
# Jump directly by keyword (matches best frecency score)
z ziro           # ➔ jumps directly to ~/Projects/ziro-shell
z doc            # ➔ jumps directly to ~/Projects/ziro-shell/docs
z down           # ➔ jumps directly to ~/Downloads

# Multi-keyword matching for deep directory jumping
z proj ziro doc  # ➔ jumps directly to ~/Projects/ziro-shell/docs

# Interactive fuzzy search with fzf preview
zi               # ➔ opens an interactive fzf selector of frequent directories

# Manual database inspection
zoxide query -l  # ➔ lists all indexed directories ranked by frecency score
```

---

## 4. The `ziro` CLI Suite

The `ziro` command dispatcher manages configuration, bytecode compilation, themes, and health audits.

```bash
ziro <command> [arguments...]
```

### Core CLI Commands

| Subcommand | Usage | What It Does |
|:---|:---|:---|
| `doctor` | `ziro doctor` | **Full Health Audit**: Verifies Python 3.11+, Zsh 5.8+, compiled `.zwc` wordcode, path resolution, and scheduler health. |
| `sync` | `ziro sync` | **Build Pipeline**: Compiles eager scripts to `.zwc` bytecode, bakes absolute paths into `~/.config/ziro/boot.zsh`, and regenerates dispatch caches. |
| `update` | `ziro update` | **Non-blocking Update**: Pulls repository updates, rebuilds `.zwc` artifacts, and refreshes vendor plugins. |
| `plugin` | `ziro plugin list [--names]`<br>`ziro plugin add <repo>`<br>`ziro plugin remove <name>` | **Plugin Manager**: Lists all managed plugins and binaries with their lifecycle stage (Eager, Deferred, On-Demand), load method, and descriptions. Installs, audits security trust scores (0–4), and manages ecosystem plugins. |
| `theme` | `ziro theme list`<br>`ziro theme apply <theme>` | **Theme Manager**: Switches between Starship presets and shell prompt themes. |
| `bench` | `ziro bench [--iters 11]` | **Startup Benchmark**: Measures honest microsecond startup latency across multiple iterations with min/median telemetry. |
| `analyze` | `ziro analyze [--full]` | **Static Analyzer**: Inspects plugins for hooks, syntax safety, completion definitions, and auto-generates `load.toml`. |
| `help` | `ziro help [command]` | Displays usage instructions and flag references for any subcommand. |

---

## 5. Modern CLI Tool Upgrades (When Installed)

When modern CLI tools are installed on your machine, Ziro automatically aliases standard utilities to modern, syntax-aware alternatives with **zero startup overhead**:

| Command | Modern Replacement | Enhancements |
|:---|:---|:---|
| `cat` | `bat --style=plain` | Syntax highlighting, line numbering, Git modification gutters. |
| `grep` | `rg` (ripgrep) | Multithreaded search, respects `.gitignore`, regex support. |
| `find` | `fd` | Intuitive colorized filesystem search, respects `.gitignore`. |
| `diff` | `delta` | Side-by-side diffs, word-level change highlighting, themes. |

### Defensive Safety Aliases
To prevent accidental data loss, interactive confirmation is enabled by default:
- `cp` ➔ `cp -i` (prompts before overwriting)
- `mv` ➔ `mv -i` (prompts before overwriting)
- `rm` ➔ `rm -i` (prompts before deleting)

---

## 6. Daily Workflow Example

Here is a typical session leveraging Ziro's unified environment:

```bash
# 1. Open terminal — honest < 20ms prompt with Starship
# 2. Check current workspace with categorized listing
ls
# Output shows: Projects/  Downloads/  Desktop/  notes.txt  setup.sh*

# 3. Hop directly into a deep project without typing the whole path
z ziro

# 4. Explore repo structure 2 levels deep
lt

# 5. Jump back 2 directories
..

# 6. Audit shell health after pulling changes
ziro doctor
```
