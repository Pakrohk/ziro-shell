# Configuration Reference (`load.toml`)

`load.toml` is the declarative load manifest for `ziro-shell`. It defines every tool, plugin, completion engine, and initialization hook that executes when an interactive Zsh session starts.

The configuration lives at:
```
~/.config/ziro/load.toml
```

Ziro enforces a strict separation between **analysis**, **configuration**, and **runtime materialization**:
1. `ziro analyze --full` inspects your installed plugins, environment, and `core/tools_factory.toml` to generate or refresh `load.toml`.
2. You customize `load.toml` directly or through `[user]` overrides.
3. `ziro sync` compiles `load.toml` into flattened bytecode (`~/.cache/ziro/ziro-boot.zsh` and `~/.cache/ziro/ziro-boot.zwc`), ensuring the shell boots with zero dynamic resolution overhead.

---

## File Structure Overview

A standard `load.toml` contains four primary sections:

```toml
[meta]
schema_version = "1.0.0"
generated_by = "ziro analyze"
generated_at = "2026-10-25T12:00:00+00:00"
analyzer_version = "0.2.0"

[boot]
artifact = "~/.cache/ziro/ziro-boot.zsh"
zwc = "~/.cache/ziro/ziro-boot.zwc"
compdump = "~/.cache/ziro/zcompdump"

[defer]
eager_modules = [
  "stages/stage-0-pre-source.zsh",
  "core/version.zsh",
  "core/queue.zsh",
  "core/task-registry.zsh",
  "core/scheduler.zsh",
  "core/hooks.zsh",
  "api/ziro-defer.zsh",
  "api/ziro-defer-bind-widget.zsh",
]
idle_threshold_seconds = 5

[user]
# User overrides preserved across analysis runs (H9 invariant)

[[tool]]
name = "starship"
timing = "eager"
order = 4
method = "eval-cache"
# ... tool configuration
```

---

## `[[tool]]` Schema Reference

Each entry in the `[[tool]]` array declares a single shell enhancement, plugin, or CLI integration.

### Field Definitions

| Field | Type | Required | Description |
| :--- | :--- | :---: | :--- |
| `name` | string | Yes | Unique identifier for the tool or plugin (e.g. `"starship"`, `"zoxide"`). |
| `order` | integer | Yes | Execution sequence in `ziro-boot.zsh`. Lower numbers run earlier. |
| `timing` | enum | Yes | Execution tier: `"eager"`, `"deferred"`, or `"on-demand"`. |
| `method` | enum | Yes | Sourcing mechanism: `"source"`, `"eval-cache"`, `"builtin"`, or `"local-source"`. |
| `enabled` | boolean | No | Toggles loading without deleting the block. Defaults to `true`. |
| `guard` | string | No | Path to binary or file that must exist before execution (e.g. `"starship"`). |
| `binary` | string | No | Alias for executable check when using `eval-cache` or `on-demand`. |
| `path` | string | Conditional | Filesystem path to the script to source. Required for `"source"` and `"local-source"`. |
| `source` | string | No | Upstream repository slug (`author/repo`) for vendor plugins. |
| `eval_command` | string | Conditional | Command executed to generate initialization shell code for `"eval-cache"`. |
| `cache_path` | string | Conditional | Destination cache file for pre-generated eval artifacts. |
| `post_source` | string | No | Shell statements executed immediately after sourcing the tool. |
| `stage` | integer | No | Deferred loading stage (`1` through `7`). Defaults to `5`. |
| `slot` | string | No | Stage execution slot (`"a"`, `"b"`, or `"c"`). Defaults to `"b"`. |
| `trigger` | enum | Conditional | On-demand trigger mechanism: `"key"`, `"command"`, or `"function"`. |
| `trigger_keys` | array[table] | Conditional | Key bindings that trigger on-demand loading (`[{ key = "^R", widget = "..." }]`). |
| `trigger_commands` | array[string] | Conditional | Commands that trigger lazy initialization on first run. |
| `trigger_functions`| array[string] | Conditional | Shell functions that trigger lazy initialization on first call. |
| `conflicts_with` | array[string] | No | Tool names that cannot run concurrently with this tool. |
| `reason` | string | No | Audit explanation surfaced in `ziro doctor` and `ziro plugin show`. |

### Timing Tiers

- **`eager`**: Evaluated synchronously during the cold boot phase (`order` 1–9). Used exclusively for critical path items: `compinit`, PATH setup, terminal color setup (`zcolors`), and prompt rendering (`starship`).
- **`deferred`**: Loaded asynchronously in background idle slots after the prompt displays (`order` 20+). Uses `ziro-defer` stages (1–7). Ideal for heavy plugins like syntax highlighting (`fast-syntax-highlighting`) and autosuggestions (`ziro-ghost`).
- **`on-demand`**: Loaded only when triggered by a keystroke (ZLE widget), an executable wrapper command, or a stubbed shell function. Ideal for interactive CLIs (`fzf`, `zoxide`, `wd`).

### Sourcing Methods

- **`source`**: Standard Zsh script sourcing (`source "$path"`). Compiled automatically to `.zwc` by `ziro sync`.
- **`eval-cache`**: Runs the binary initialization command once offline during `ziro sync` (or first boot) and saves the generated code to `cache_path`. Boots by sourcing the cached file directly, eliminating binary subprocess forks.
- **`builtin`**: Inlines core shell primitives (e.g. `compinit`, shell options).
- **`local-source`**: Sources personal shell functions or scripts from local files (e.g. `~/.ziro/lib/aliases.zsh`).

---

## The `[user]` Section and the H9 Invariant

`load.toml` contains a dedicated `[user]` section located at the root of the file or above the tool declarations.

### The H9 Preservation Invariant
In Ziro Shell, `ziro analyze --full` regenerates all `[meta]`, `[boot]`, `[defer]`, and `[[tool]]` blocks using updated heuristics and installed plugins. However, **`ziro analyze` strictly preserves the `[user]` table verbatim across all runs**. 

Your manual configuration overrides, custom hooks, and local preferences are never overwritten, lost, or reformatted by the automated analyzer.

### Structure of `[user]`

```toml
[user]
# Global user configurations
shell_theme = "custom"

[[user.override]]
name = "fzf"
timing = "on-demand"
trigger = "key"
keys = ["^R", "^T", "^[c"]
reason = "Force key-trigger loading on interactive search"

[[user.override]]
name = "fast-syntax-highlighting"
timing = "deferred"
stage = 6
slot = "a"
reason = "Delay syntax highlighting until completions settle"
```

---

## External Overrides (`overrides.toml`)

For teams sharing configurations, dotfile managers with templating, or users who prefer keeping manual tweaks in a separate file, Ziro supports an external override file:

```
~/.config/ziro/overrides.toml
```

Alternatively, set the `$ZIRO_OVERRIDES_FILE` environment variable to point to any arbitrary file path.

### Precedence Hierarchy (Highest to Lowest)

When resolving how a tool should load, Ziro resolves configuration according to the following strict order:

1. **External override file** (`~/.config/ziro/overrides.toml` or `$ZIRO_OVERRIDES_FILE`)
2. **`[user]` table** inside `~/.config/ziro/load.toml`
3. **Tag-based overrides** (`~/.config/ziro/tags/plugins/*.toml`)
4. **Analyzer recommendation** (`core/analyzer.py` heuristics)
5. **Safe default** (deferred stage 5, slot `b`)

---

## Configuration Examples

### 1. Promoting a Deferred Plugin to Eager (or Vice Versa)

If you require git status information inside an eager prompt, ensure `ohmyzsh-git` runs eagerly:

```toml
[[tool]]
name = "ohmyzsh-git"
source = "ohmyzsh/ohmyzsh"
subpath = "plugins/git"
timing = "eager"
order = 2
method = "source"
path = "~/.ziro/ohmyzsh/ohmyzsh/plugins/git/git.plugin.zsh"
```

To demote a tool that defaults to eager into a deferred background slot, add an override in `[user]`:

```toml
[[user.override]]
name = "zcolors"
timing = "deferred"
stage = 5
slot = "c"
reason = "Colors not needed on initial line draw"
```

### 2. Disabling Specific Tools

To disable a tool without removing its configuration from `load.toml`, set `enabled = false`:

```toml
[[tool]]
name = "colored-man-pages"
source = "ohmyzsh/ohmyzsh"
subpath = "plugins/colored-man-pages"
timing = "deferred"
order = 22
method = "source"
enabled = false
path = "~/.ziro/ohmyzsh/ohmyzsh/plugins/colored-man-pages/colored-man-pages.plugin.zsh"
```

Alternatively, disable via the `[user]` section:

```toml
[[user.override]]
name = "you-should-use"
enabled = false
reason = "Temporarily disabled during automated pairing sessions"
```

### 3. Adding Custom Local Scripts and Plugins

To load a personal script or local module, configure it with `method = "local-source"`:

```toml
[[tool]]
name = "work-aliases"
timing = "deferred"
order = 30
method = "local-source"
stage = 5
slot = "b"
path = "~/Projects/dotfiles/zsh/work_aliases.zsh"
```

To create an on-demand function wrapper for custom utility functions:

```toml
[[tool]]
name = "dev-helpers"
timing = "on-demand"
order = 31
method = "local-source"
trigger = "function"
trigger_functions = ["docker_clean", "k8s_ctx", "aws_assume"]
path = "~/.config/ziro/helpers/dev.zsh"
```

### 4. Configuring Shell Options and Environment Variables

Environment variables, shell options, and exports belong in your `~/.zshrc.local` or declared in `post_source` hooks on relevant tools.

To ensure `setopt promptsubst` executes immediately after prompt initialization:

```toml
[[tool]]
name = "starship"
timing = "eager"
order = 4
method = "eval-cache"
binary = "starship"
init_command = "starship init zsh --print-full-init"
cache_path = "~/.cache/ziro/eval-cache/starship.zsh"
post_source = "setopt promptsubst"
```

For persistent user variables, place them directly in `~/.zshrc.local`. Ziro's bootstrap sources `~/.zshrc.local` before compiling and launching runtime stages, guaranteeing environment availability across all child processes.

---

## Environment Variables

Ziro respects standard XDG and custom environment variables across both its native Zsh hot-path and offline Python engine:

| Variable | Default Value | Description |
|---|---|---|
| `ZIRO_HOME` | `~/.ziro` | Root directory containing the Ziro repository source tree. |
| `ZIRO_CONFIG` | `${XDG_CONFIG_HOME:-~/.config}/ziro` | Location of user configuration files (`load.toml`, `defaults.toml`). |
| `ZIRO_DATA` | `${XDG_DATA_HOME:-~/.local/share}/ziro` | Storage for completions, plugin checkouts, and runtime venv. |
| `ZIRO_CACHE` | `${XDG_CACHE_HOME:-~/.cache}/ziro` | Location for compiled `.zwc` wordcode, `zcompdump`, and caches. |
| `ZIRO_REF` | Latest release tag | Git ref, branch, or tag targeted during installation or update. |
| `ZIRO_REPO_URL` | Canonical GitHub URL | Git clone URL for Ziro repository (requires `ZIRO_ALLOW_FORK=1` if non-canonical). |
| `ZIRO_ALLOW_FORK` | `0` | Set to `1` to permit bootstrapping from third-party forks. |
| `ZIRO_ALLOW_ROOT` | `0` | Set to `1` to permit installer execution as `root` (e.g. inside Docker containers). |
| `ZIRO_NONINTERACTIVE`| Auto-detected | Set to `1` to suppress all interactive prompts during install/sync. |
| `ZIRO_SKIP_VENV_BOOTSTRAP` | `0` | Set to `1` to prevent automatic creation of the optional `rich` venv. |
| `ZIRO_OVERRIDES_FILE` | `${ZIRO_CONFIG}/overrides.toml` | Path to an external TOML file containing tool overrides. |

---

## Applying Changes

Edits to `load.toml` do not take effect in the active shell until synchronized:

```bash
# 1. Validate and compile load.toml into ziro-boot.zwc
ziro sync

# 2. Verify configuration health and cache validity
ziro doctor
```

---

## History Cache Security & Credential Hygiene

Starting in `v1.2.3` (Spec 016), `ziro-shell` and `ziro-ghost` enforce proactive secret redaction and strict filesystem permissions for terminal history:

### Filtered Secret Patterns
Before any command line is persisted to `~/.cache/ziro/ghost/history-cache`, `ghost_history_is_sensitive()` inspects its content against 10 credential patterns:
- Cloud access keys: AWS (`AKIA*`), OpenAI (`sk-*`), Slack (`xoxb-*`, `xoxp-*`).
- Personal access tokens: GitHub (`ghp_*`, `gho_*`, `ghu_*`, `ghs_*`, `ghr_*`).
- Authentication headers: `Authorization: Bearer <token>`, `Authorization: Basic <token>`.
- Command-line password flags: `--password=<val>`, `--token=<val>`, `--secret=<val>`, `-p<password>`.
- Cryptographic private keys: `BEGIN PRIVATE KEY`, `BEGIN OPENSSH PRIVATE KEY`, `id_rsa`, `id_ed25519`.
- Commands beginning with leading whitespace (honoring `HIST_IGNORE_SPACE`).
- Excessively long lines (> 500 characters) or continuous 40+ alphanumeric character blobs (likely base64 or hex serialized secrets).

### Filesystem Permissions
- **History cache file**: `~/.cache/ziro/ghost/history-cache` is created and maintained with `0600` (`-rw-------`).
- **History cache directory**: `~/.cache/ziro/ghost/` is restricted to `0700` (`drwx------`).
- **Compiled bytecode**: All `.zwc` files in `~/.cache/ziro/eval-cache/` are enforced with `0600`, and `eval-cache/` itself with `0700`.

### Manual Cache Purge
To discard legacy plaintext history cached prior to `v1.2.3`:
```bash
rm -f ~/.cache/ziro/ghost/history-cache
```
A fresh, filtered cache file will automatically be created on your next interactive shell session. Opting out of secret filtering is not supported by design.

---

## File permissions

Starting in `v1.2.5` (Spec 018), `ziro-shell` enforces a universal secure permissions model across all core subsystems:
- **Directories (`0700` / `drwx------`)**: All Ziro directories (`~/.ziro`, `~/.config/ziro`, `~/.cache/ziro`, `~/.local/share/ziro`, and all internal subdirectories including `eval-cache/`, `vendor/`, `analysis/`, and `completions/`) are created and maintained with mode `0700`. Only the owning user has read, write, and execute permissions.
- **Files (`0600` / `-rw-------`)**: All generated configuration files, cache files, runtime scripts, and compiled bytecode artifacts (such as `~/.cache/ziro/ziro-boot.zsh.zwc`, `eval-cache/*.zwc`, `load.toml`, `defaults.toml`, and `ghost/history-cache`) are restricted to mode `0600`. Only the owning user can read and write them.

### Multi-User Security
On shared multi-user systems, default umask settings (`0022` or `0002`) can expose shell configurations, custom token variables, cloned plugin repositories, and compiled shell logic to other local users. The universal `0700`/`0600` policy eliminates this attack surface across installation, synchronization, plugin management, and updates.

### Remediation & Auditing
If directory or file permissions are ever modified or downgraded by external tools:
1. Re-apply secure permissions automatically:
   ```bash
   ziro sync
   ```
2. Audit directory and bytecode permissions via health diagnostics:
   ```bash
   ziro doctor
   ```
   `ziro doctor` verifies that all core directories are `0700`, `ziro-boot.zsh.zwc` is `0600`, and warns if any legacy ghost cache files predate secret filtering.

---

## Sharing themes

Starting in `v1.2.4` (Spec 017), `ziro-shell` includes automated theme sharing with the community repository [Pakrohk/ziro-themes](https://github.com/Pakrohk/ziro-themes).

### Prerequisites
- GitHub CLI (`gh`) installed and in `$PATH` (`https://cli.github.com/`).
- GitHub account authenticated via `gh auth login`.
- Active Starship prompt configuration at `~/.config/starship.toml`.

### Submitting Your Theme
To submit your active prompt configuration:
```bash
ziro theme submit
```

This interactive workflow:
1. Validates prerequisites (`gh`, auth status, valid TOML).
2. Computes a diff summary of your custom configuration vs baseline defaults.
3. Prompts for a kebab-case theme name (e.g. `cyber-neon`, `pastel-waves`).
4. Clones `Pakrohk/ziro-themes` to an isolated workspace, creates a feature branch `submit/<username>/<theme-name>`, writes `themes/<username>/<theme-name>.toml`, and opens a pull request.

### Options
- `--name <name>`: Provide theme name directly without prompting.
- `--dry-run`: Preview diff analysis, target path, and planned PR title without creating files or network calls.
- `--no-pr`: Push branch to origin but skip opening pull request.
- `--keep`: Retain temporary workspace clone for inspection and debugging.

### Examples
```bash
# Preview submission
ziro theme submit --dry-run

# Submit with custom name
ziro theme submit --name my-minimalist-prompt

# Verify prerequisites via doctor
ziro doctor
```

---

## Root Profile Hardening

When running Ziro as root (`EUID == 0`), additional security measures activate automatically (Spec 022, M1–M4):

### M1: FZF Execute Blocking
- `FZF_DEFAULT_OPTS` is overridden to safe defaults (`--no-mouse --height=40% --layout=reverse`, no `execute` or `execute-silent` bindings).
- A wrapper function `fzf` inspects arguments and blocks any invocation containing `--bind=...:execute(...)` or `execute-silent`.
- **Bypass**: Set `ZIRO_ALLOW_ROOT_FZF_EXECUTE=1` to override (not recommended).

### M2: Clipboard Buffer Isolation
- Headless environments (no `DISPLAY` or `WAYLAND_DISPLAY`): file buffer stored at `$XDG_RUNTIME_DIR/.ziro-clipboard` (permissions `0600`).
- Fallback: `/tmp/.ziro_clipboard-$UID` (permissions `0600`, with automatic 24-hour cleanup precmd hook).
- GUI sessions: unchanged native clipboard tool behavior (`wl-copy`, `pbcopy`, `xclip`, `xsel`).

### M3: SSH Agent Forwarding
- `agent-forwarding no` is enforced explicitly by default (even in remote SSH sessions).
- **Opt-in**: Set `ZIRO_SSH_FORWARDING=1` to allow agent forwarding.

### M4: Isolated Starship Root Prompt
- Root shells automatically use `~/.config/ziro/starship-root.toml`.
- Guaranteed to contain zero `[custom.*]` and zero `[env_var.*]` sections, mitigating prompt injection risks (CVE-2024-41815).
- Standard user Starship configuration (`~/.config/starship.toml`) remains completely unaffected.

Run `ziro doctor` as root to verify that all hardening controls are active.


