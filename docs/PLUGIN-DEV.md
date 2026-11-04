# Writing a Ziro Plugin

Welcome to the Ziro plugin development guide! This document explains how to build fast, lightweight, and reliable plugins for the Ziro shell environment.

Ziro is built around a simple philosophy: **the fastest code at shell startup is code that never runs during startup**. By structuring your plugin into modular capabilities and selecting the right load timing, you can deliver rich interactive features without adding milliseconds to your users' command prompts.

---

## Quick Start

A minimal, high-performance plugin requires only two files: a manifest (`plugin.toml`) and your shell script.

### 1. Create the Manifest (`plugin.toml`)

```toml
[plugin]
name = "my-quick-plugin"
version = "1.0.0"
ziro_min_version = "1.4.0"
description = "A minimal hello-world plugin for Ziro"

[[capability]]
name = "greeting"
type = "core"
strategy = "deferred-s5"
shimmable = true
est_cost_ms = 0.8
files = ["init.zsh"]
```

### 2. Write Your Script (`init.zsh`)

```zsh
# init.zsh — greeting capability
quick_greet() {
  print -P "%F{cyan}Hello from my-quick-plugin!%f"
}

alias qg="quick_greet"
```

Because this plugin declares the `deferred-s5` strategy, it loads immediately after the user's first prompt appears, adding **0.0 ms** to shell startup time.

---

## File Layout

Modern Ziro plugins organize code by capability rather than putting everything into a single large file. Here is the recommended directory structure:

```
my-plugin/
├── plugin.toml                 # Plugin manifest (required)
├── README.md                   # Plugin documentation
├── modules/                    # Isolated capability modules
│   ├── core/
│   │   └── init.zsh            # Environment variables and base setup
│   ├── line/
│   │   └── init.zsh            # Interactive command line integrations
│   └── popup/
│       └── invoke.zsh          # Key bindings and command triggers
├── bin/                        # Pre-compiled executable binaries (optional)
│   └── helper-tool
├── service/                    # Background daemons and workers (optional)
│   └── server.zsh
└── tests/                      # Automated test scripts
    ├── test_independence.zsh
    └── test_cost.zsh
```

### Directory Responsibilities
- `plugin.toml`: The single source of truth describing your plugin and its capabilities.
- `modules/`: Each capability gets its own directory. Modules should be independent and self-contained.
- `bin/`: Platform binaries (e.g. written in Rust or Go) that your shell functions invoke.
- `service/`: Long-running background workers that communicate via Unix domain sockets.
- `tests/`: Automated tests verifying load performance and correctness.

---

## Declaring Capabilities

Ziro plugins declare their components in `plugin.toml` using `[[capability]]` blocks. This allows Ziro to load each piece of your plugin at the ideal moment.

### Complete Manifest Example

```toml
[plugin]
name = "enhanced-git"
version = "1.2.0"
ziro_min_version = "1.4.0"
description = "Lightning-fast Git utilities and interactive menus"
author = "Your Name <you@example.com>"
homepage = "https://github.com/example/enhanced-git"

# 1. Core environment and global exports (loads immediately)
[[capability]]
name = "core"
type = "core"
strategy = "eager"
shimmable = false
est_cost_ms = 0.4
files = ["modules/core/init.zsh"]
env_exports = ["ENHANCED_GIT_CACHE_DIR"]

# 2. Command-line prompt integrations (loads after first prompt)
[[capability]]
name = "prompt-status"
type = "suggestion-source"
strategy = "deferred-s5"
trigger = "precmd"
shimmable = true
est_cost_ms = 3.5
files = ["modules/line/init.zsh"]
depends_on = ["core"]

# 3. Interactive popup menu (loads only when Ctrl-G is pressed)
[[capability]]
name = "menu"
type = "rust-binary-invoke"
strategy = "on-demand"
trigger = "key:^G"
shimmable = true
est_cost_ms = 0.1
files = ["modules/popup/invoke.zsh"]
binary = "bin/git-menu"
depends_on = ["core"]

# 4. Background repository scanner (runs as background worker)
[[capability]]
name = "indexer"
type = "service"
strategy = "background-service"
service_name = "enhanced-git-scanner"
socket = "~/.cache/ziro/enhanced-git/scanner.sock"
cold_path_fallback = "source modules/core/fallback.zsh"
est_cost_ms = 0.0
files = ["service/server.zsh"]
depends_on = ["core"]
```

---

## Choosing Load Strategies

Selecting the right strategy is the most important architectural choice for your plugin. Follow these guidelines:

### Strategy Summary

| Strategy | When It Runs | Shell Boot Budget | When to Use It |
|---|---|---|---|
| `eager` | Before the prompt is drawn | ≤ 2.0 ms | Setting environment variables and aliases that other tools require immediately. |
| `eager-shim` | Before prompt, but creates lazy stubs | ≤ 0.5 ms | Defining function stubs that load their full code only when executed. |
| `deferred-s5` | Immediately after the first prompt | 0.0 ms | Hook functions (`precmd`), autosuggestions, and non-blocking setup. |
| `on-demand` | When triggered by key, command, or event | 0.0 ms | Interactive tools, popups, and commands that users run occasionally. |
| `lazy-compinit` | When the user presses Tab | 0.0 ms | Shell completions and complex argument parsers. |
| `background-service` | Out-of-band background process | 0.0 ms | Heavy indexing, cache warming, and status monitoring. |
| `compiled-artifact` | Directly executed native binary | 0.0 ms | High-performance native binaries written in Rust, Go, or C. |

### Rules of Thumb
- If a function is only used when the user types a command, use `on-demand`.
- If code sets up command-line decorations or suggestions, use `deferred-s5`.
- If an operation takes more than 2 ms, **never** place it in `eager`. Move it to `deferred-s5` or `background-service`.

---

## Writing Shim-Safe Code

A "shim" is a tiny placeholder function that stands in for your real implementation until the user actually calls it. Shims allow Ziro to avoid parsing hundreds of lines of shell script until they are needed.

To ensure your code can be safely shimmed, follow **The Three Rules**:

1. **Rule 1: Zero Side Effects at Definition Time**  
   Defining your placeholder must produce no terminal output, no subshells, and no modifications to global shell settings (`setopt`).
2. **Rule 2: Identical Semantics on Execution**  
   When the user runs the command, the shim loads the real script and executes the command with the exact same arguments, return code, and standard input/output.
3. **Rule 3: Order Independence**  
   The placeholder must be safe to define at any point during shell initialization, even before its companion modules are sourced.

### How to Write a Self-Shimming Function

```zsh
# modules/popup/invoke.zsh
my_tool() {
  # 1. Remove the placeholder so this loader only runs once
  unfunction my_tool

  # 2. Source the real, complete implementation
  source "${0:A:h}/real_implementation.zsh"

  # 3. Forward the user's call with all original arguments
  my_tool "$@"
}
```

---

## Writing a Service

Services handle long-running, continuous tasks (like scanning Git repositories or watching files) without freezing the interactive shell.

### Service Checklist
1. **Unix Domain Socket**: All client-server communication must occur via a Unix domain socket located under `${XDG_RUNTIME_DIR:-~/.cache}/ziro/<plugin-name>/service.sock`.
2. **Fast Timeout & Cold Fallback**: When the shell communicates with your service, it must use a strict timeout (10 ms or less). If the service is not running, execute your `cold_path_fallback` immediately.
3. **Never Spawn From Shell Boot**: Never start your daemon using `&` or background subshells inside shell startup scripts. Use systemd user services or external supervisors.

### Client Hook Example

```zsh
# Querying a background service from a precmd hook
_my_plugin_query_service() {
  local sock="${XDG_RUNTIME_DIR:-$HOME/.cache}/ziro/my-plugin/worker.sock"

  if [[ -S "$sock" ]]; then
    # Query the daemon using a non-blocking socket tool with a strict timeout
    nc -U -w 1 "$sock" 2>/dev/null && return 0
  fi

  # Fallback: execute synchronous lightweight logic if daemon is offline
  _my_plugin_synchronous_fallback
}
```

---

## Anti-Patterns to Avoid

Avoid these 6 common mistakes that cause latency and unexpected bugs:

### 1. Monolithic Single-File Plugins
Putting environment setup, key bindings, and heavy functions in a single `plugin.zsh` file makes it impossible to optimize loading. Break features into separate files under `modules/`.

### 2. Sourcing Side Effects (The Warmup Trap)
Never run background initialization loops or network calls when a file is sourced. In one real-world plugin, an inline cache warmup routine added **246 ms** of startup lag before it was moved to a background service!

### 3. Inline Daemon Spawning
Never use `(my_daemon &)` or `coproc` in eager scripts. This leads to terminal corruption, frozen prompts, and process leaks.

### 4. Running `eval` on Hot Paths
Avoid `eval "$(/path/to/binary init zsh)"` during startup. Subprocess forks and runtime parsing add 15–40 ms of delay per tool. Use cached files or compiled `.zwc` scripts.

### 5. Hidden Shared State
Do not rely on global variables set by other modules unless you explicitly declare `depends_on = ["core"]` in your manifest.

### 6. Missing Trigger Declarations
If you set `strategy = "on-demand"`, you must provide a trigger (such as `trigger = "key:^X"` or `trigger = "command:mycmd"`). Without a trigger, Ziro cannot know when to activate your tool.

---

## Testing Your Plugin

Ziro provides 5 standard tests to verify that your plugin meets performance and safety standards:

1. **Independence Test**: Verifies that loading one capability does not accidentally pull in or execute another.
2. **Cost Verification Test**: Runs your plugin in an isolated shell (`zsh -f`) and measures its startup duration to ensure it stays within declared limits.
3. **Shim Safety Test**: Checks that defining function shims produces zero terminal output and zero background subprocesses.
4. **Service Fallback Test**: Simulates a daemon crash (`kill -9`) and confirms that your shell functions continue to operate gracefully via the fallback path.
5. **Analyzer Check**: Runs the Ziro analyzer on your plugin directory to confirm that all capabilities are properly categorized.

---

## Debugging

Ziro includes built-in commands to help inspect and debug your plugin:

### Inspect Plugin Behavior
Run the behavior analyzer on your plugin source directory:

```bash
ziro analyze --explain ./my-plugin
```

This command parses your `plugin.toml`, inspects your shell scripts, and prints a detailed breakdown of each capability's classification, estimated cost, and potential anti-patterns.

### Profile Execution Times
Measure the real-world execution cost of your plugin:

```bash
ziro bench --plugin my-plugin --iters 10
```

This runs isolated execution cycles and reports median startup times down to fractional milliseconds.

### System Health
Check overall integration health across all installed plugins:

```bash
ziro doctor
```

---

## Examples

### Example 1: Single-Capability Utility

A simple plugin providing handy directory aliases.

`plugin.toml`:
```toml
[plugin]
name = "dir-shortcuts"
version = "1.0.0"
ziro_min_version = "1.4.0"

[[capability]]
name = "shortcuts"
type = "core"
strategy = "deferred-s5"
shimmable = true
est_cost_ms = 0.5
files = ["shortcuts.zsh"]
```

`shortcuts.zsh`:
```zsh
alias proj="$HOME/Projects"
alias docs="$HOME/Documents"
alias dl="$HOME/Downloads"
```

### Example 2: Multi-Capability Interactive Tool

A Git tool with an instant prompt indicator and an on-demand popup.

`plugin.toml`:
```toml
[plugin]
name = "git-toolkit"
version = "2.0.0"
ziro_min_version = "1.4.0"

[[capability]]
name = "core"
type = "core"
strategy = "eager"
shimmable = false
est_cost_ms = 0.3
files = ["modules/core/init.zsh"]

[[capability]]
name = "status"
type = "suggestion-source"
strategy = "deferred-s5"
trigger = "precmd"
shimmable = true
est_cost_ms = 2.0
files = ["modules/status/init.zsh"]
depends_on = ["core"]

[[capability]]
name = "branch-switch"
type = "rust-binary-invoke"
strategy = "on-demand"
trigger = "key:^B"
shimmable = true
est_cost_ms = 0.1
files = ["modules/branch/invoke.zsh"]
binary = "bin/branch-selector"
depends_on = ["core"]
```

### Example 3: Background Service Plugin

A plugin with a persistent cache worker.

`plugin.toml`:
```toml
[plugin]
name = "smart-history"
version = "1.0.0"
ziro_min_version = "1.4.0"

[[capability]]
name = "core"
type = "core"
strategy = "eager"
shimmable = false
est_cost_ms = 0.4
files = ["modules/core/init.zsh"]

[[capability]]
name = "daemon"
type = "service"
strategy = "background-service"
service_name = "smart-history-indexer"
socket = "~/.cache/ziro/smart-history/indexer.sock"
cold_path_fallback = "source modules/core/fallback.zsh"
est_cost_ms = 0.0
files = ["service/server.zsh"]
depends_on = ["core"]
```

---

## Migration from Legacy Single-File Format

If you have an existing single-file plugin written for older Ziro standards, you do not need to rewrite your entire project.

1. **Add `plugin.toml`**: Place a manifest file in your repository root declaring your single script as a capability.
2. **Choose a Safe Strategy**: If your script defines interactive functions or aliases, set `strategy = "deferred-s5"`.
3. **Decompose Gradually**: When you are ready to optimize further, separate your core variables into an `eager` module and move heavy interactive menus into an `on-demand` module.

Decomposition is always opt-in. A properly declared single-capability plugin is fully supported and celebrated in the Ziro ecosystem!
