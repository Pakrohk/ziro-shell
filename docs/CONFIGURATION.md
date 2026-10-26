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
