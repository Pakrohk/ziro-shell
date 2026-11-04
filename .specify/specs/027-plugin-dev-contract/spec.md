# SPEC-027: Plugin Development Contract

**Status**: DRAFT  
**Version**: 1.0.0  
**Date**: 2026-11-04  
**Author**: Ziro Architecture Team  
**Supersedes**: Spec 012 (`012-optional-plugin-manifest`, obsolete single-file format)  
**Related Specs**: SPEC-024 (Ghost v2.0.1 Integration), SPEC-025 (Modular Defer Behavior Analyzer), SPEC-026 (Ghost Modularity)

---

## 1. Executive Summary

Ziro Shell optimizes shell startup through rigorous deferred loading, lazy compilation, and deterministic lifecycle execution. Early plugin integration standards (notably Spec 012) treated plugins as monolithic, single-file scripts loaded either eagerly or entirely post-prompt. 

This model is obsolete. Modern shell enhancements—such as `ziro-ghost` v2.0+—exhibit heterogeneous capabilities:
1. Pure Zsh syntax and environment setup (instant, eager-safe).
2. Interactive line autosuggestion buffers (precmd hooks, slot-deferred).
3. Heavy compiled binary invocations (Rust/C popups, on-demand key-triggered).
4. Background initialization routines, index warmup daemons, and socket-driven services.

Spec 012 provided no vocabulary for capability decomposition, forcing entire plugins into binary eager-or-deferred tradeoffs. This resulted in catastrophic boot delays (e.g., inline daemon spawning consuming 246ms) or broken interactive behaviors (missing key widgets or completion state).

SPEC-027 establishes the definitive contract for Ziro plugin development. It standardizes:
- **Capability Axis**: Multi-capability decomposition replacing monolithic single files.
- **Structured File Layout**: Standardized `modules/`, `sources/`, `bin/`, and `service/` directory hierarchies.
- **Declarative Manifest Schema (`plugin.toml`)**: Granular per-capability metadata, dependency graphs, and budgets.
- **7 Load Strategies & Boot Budget Contract**: Strict time budgets and execution boundaries from eager to background service.
- **3-Condition Shim Rule**: Formalized safety invariants for non-destructive lazy proxy generation.
- **Service Contract**: Unix domain socket conventions, background daemons, and reliable cold-path fallbacks.
- **6 Mandatory Anti-Patterns**: Explicitly forbidden practices illustrated with real ecosystem benchmarks.
- **5 Mandatory Verification Tests**: Automated compliance suite every compliant plugin must provide.

The canonical reference consumer of SPEC-027 is `ziro-ghost` v2.1.0 (SPEC-026). SPEC-025's behavior analyzer (M06) and lazy-shim generator (M09) consume this contract to classify and decompose plugins automatically.

---

## 2. Plugin File Structure

A compliant Ziro plugin is structured by discrete capability modules rather than a single monolithic shell file.

```
my-plugin/
├── plugin.toml                 # Declarative capability manifest (MANDATORY)
├── README.md                   # Human documentation
├── LICENSE                     # License file
├── modules/                    # Isolated capability modules
│   ├── core/
│   │   └── init.zsh            # Minimal environment & variable exports (eager)
│   ├── line/
│   │   └── init.zsh            # Autosuggestion & precmd hooks (deferred-s5)
│   └── popup/
│       └── invoke.zsh          # Key widget proxy & launcher (on-demand)
├── bin/                        # Architecture-specific compiled binaries (optional)
│   └── my-plugin-popup
├── service/                    # Background daemon & worker components (optional)
│   ├── server.zsh
│   └── systemd/
│       └── my-plugin.service
└── tests/                      # Automated compliance tests (MANDATORY)
    ├── test_independence.zsh
    ├── test_cost.zsh
    ├── test_shim.zsh
    ├── test_service.zsh
    └── test_analyzer.py
```

### Directory Roles
1. `plugin.toml`: The root declaration describing metadata, dependencies, and capability blocks.
2. `modules/`: Each capability resides in its own isolated sub-folder. Files within a module MUST NOT reach across boundaries or assume companion modules have executed unless declared in `depends_on`.
3. `bin/`: Pre-compiled platform binaries (e.g., Rust, Go). Binaries must support `--version` and be relocatable.
4. `service/`: Long-running background processes communicating exclusively over Unix domain sockets or FIFO IPC.
5. `tests/`: Test runners implementing the 5 mandatory contract tests specified in §8.

---

## 3. Manifest Schema (`plugin.toml`)

The manifest defines the plugin identity and an array of granular `[[capability]]` tables.

### Complete Specification Schema

```toml
[plugin]
name = "my-plugin"
version = "1.0.0"
ziro_min_version = "1.4.0"
description = "Comprehensive multi-capability modern shell plugin"
author = "Developer <dev@example.com>"
homepage = "https://github.com/example/my-plugin"

[[capability]]
name = "core"
type = "core"
strategy = "eager"
shimmable = false
est_cost_ms = 0.5
files = ["modules/core/init.zsh"]
env_exports = ["MY_PLUGIN_STATE_DIR", "MY_PLUGIN_COLOR"]

[[capability]]
name = "line"
type = "suggestion-source"
strategy = "deferred-s5"
trigger = "precmd"
shimmable = true
est_cost_ms = 4.0
files = ["modules/line/init.zsh"]
depends_on = ["core"]

[[capability]]
name = "popup"
type = "rust-binary-invoke"
strategy = "on-demand"
trigger = "key:^I"
shimmable = true
est_cost_ms = 0.1
files = ["modules/popup/invoke.zsh"]
binary = "bin/my-plugin-popup"
depends_on = ["core"]

[[capability]]
name = "warmup"
type = "service"
strategy = "background-service"
service_name = "my-plugin-warmup"
socket = "~/.cache/ziro/my-plugin/warmup.sock"
cold_path_fallback = "source modules/line/init.zsh"
est_cost_ms = 0.0
files = ["service/server.zsh"]
depends_on = ["core"]
```

### Manifest Fields Description
- `[plugin]`:
  - `name` (string, required): Unique kebab-case plugin identifier.
  - `version` (string, required): Semantic version (`X.Y.Z`).
  - `ziro_min_version` (string, required): Minimum Ziro framework version supporting this manifest.
- `[[capability]]`:
  - `name` (string, required): Unique name of the capability within the plugin.
  - `type` (string, required): Functional category (`core`, `suggestion-source`, `rust-binary-invoke`, `completion`, `service`, `theme-element`).
  - `strategy` (string, required): One of the 7 supported load strategies (§4).
  - `shimmable` (boolean, required): Whether the capability satisfies the 3-condition shim rule (§5).
  - `est_cost_ms` (float, required): Declared execution cost in milliseconds. Must be verified within 2x by automated benchmark.
  - `files` (list of strings, required): Relative file paths belonging to this capability.
  - `trigger` (string, optional): Required for `on-demand` and event-driven capabilities (`key:<seq>`, `command:<cmd>`, `event:<hook>`).
  - `binary` (string, optional): Relative path to binary executable for `compiled-artifact` or binary invocation.
  - `depends_on` (list of strings, optional): Capabilities inside this plugin or core Ziro modules that must load prior to this capability.
  - `socket` (string, optional): Socket path for `background-service`.
  - `cold_path_fallback` (string, optional): Shell fallback statement when background daemon is offline.

---

## 4. Load Stage Contract

Ziro divides shell startup into deterministic lifecycle stages. Every capability MUST assign itself to one of the 7 official load strategies based on functionality and cost.

### Load Stage Contract Table

| Strategy | When Loaded | Boot Budget | Permitted Operations | Prohibited Operations | Rules & Invariants |
|---|---|---|---|---|---|
| `eager` | Immediate before prompt | ≤ 2.0 ms | Variable assignments, function definitions, aliases | Forking, subshells (`$(...)`), network I/O, heavy disk scans, compdef | Minimal bootstrap only. Exceeding 2ms triggers doctor warning. |
| `eager-shim` | Immediate before prompt | ≤ 0.5 ms | Lightweight proxy stub definitions, key trap registration | Executing heavy bodies, file sourcing, parsing external files | Registers zero-cost shims. Real code loads lazily on first call. |
| `deferred-s5` | Post-first prompt (Stage 5) | 0.0 ms (0ms boot) | File sourcing, subprocess invocation, completions setup | Blocking prompt render, infinite background loops | Executes asynchronously or in idle slots after interactive prompt displays. |
| `on-demand` | On declared trigger | 0.0 ms boot | Source full implementation, swap function/widget, exec | Sourcing before trigger event, undeclared triggers | Trigger MUST be declared (`key:`, `command:`, `event:`). Generator emits lazy stub. |
| `lazy-compinit` | First Tab completion | 0.0 ms boot | Completion script autoloading, fpath manipulation | Executing compdef or compinit in eager path | Tab activates real completion handler. Must not alter existing zle widgets. |
| `background-service` | Out-of-band daemon | 0.0 ms boot | IPC over Unix socket, persistent cache maintenance | Inline fork during shell initialization, blocking IPC calls | Daemon lifecycle managed independently. Must declare socket + cold fallback. |
| `compiled-artifact` | Invocation via binary | 0.0 ms boot | Executing pre-compiled native binary | Interpreting heavy shell scripts, compiling on hot path | Rust/Go/C binary. Must support `--version` and POSIX signal handling. |

### Strict Timing Invariants
1. **The 0ms Boot Principle**: All non-essential capabilities must achieve 0.0ms boot impact by utilizing `deferred-s5`, `on-demand`, or `background-service`.
2. **Eager Budget Enforcement**: Any capability using `eager` that consumes >2.0ms during automated profiling (`ziro bench`) fails CI validation and is rejected by the behavior analyzer.
3. **No Shell Blocking in Background Services**: Background daemons must fork cleanly into session daemons or systemd user units; shell initialization scripts must never wait on socket creation.

---

## 5. Shim Contract

Lazy shims defer parsing and evaluation of shell code until first use. A capability cannot be safely shimmed without formal guarantees.

### The 3-Condition Shim Rule
A capability is shimmable (`shimmable = true`) IF AND ONLY IF all three conditions are satisfied:

1. **Zero Observable Side Effects at Definition Time**:
   - Emitting and defining the proxy stub produces no output (stdout/stderr), no subshell forks, no environment variable mutations, and no modification of Zsh option flags (`setopt`).
2. **Identical Semantics on First Use**:
   - When triggered, the shim sources the full implementation and transparently re-dispatches the exact invocation with identical arguments, flags, standard streams, exit codes, and widget states.
3. **Load Order Independence**:
   - The shim stub can be defined anywhere in the emission sequence regardless of execution order. Sourcing dependencies happens dynamically inside the load stub before primary dispatch.

### Shim Fallback Policy
If ANY of the three conditions cannot be guaranteed (for instance, a plugin that immediately mutates global prompt state or registers non-idempotent hooks upon sourcing), the capability is declared `shimmable = false`. 
The analyzer and generator then fall back to the minimal safe strategy (typically `deferred-s5` or `eager`). Decomposition is strictly opt-in; safety always supersedes deferral.

### Generator Stub Pattern
When `strategy = "on-demand"` or `strategy = "eager-shim"`, the generator emits the following atomic lazy-replacement pattern:

```zsh
# <capability> — lazy shim stub (SPEC-027)
<capability_name>() {
  unfunction <capability_name>
  source "<resolved_module_path>"
  <capability_name> "$@"
}
```

---

## 6. Service Contract

Capabilities classified as `background-service` run external to the interactive shell. They offload continuous, expensive work (e.g., Git status caching, predictive index scanning, history vector search).

### Service Requirements
1. **Unix Domain Socket Interface**:
   - Communication between the shell hook and the daemon MUST occur over a local Unix domain socket under `${XDG_RUNTIME_DIR:-~/.cache}/ziro/<plugin>/<service>.sock`.
2. **Cold-Path Fallback**:
   - If the daemon is dead, restarting, or unresponsive, the client hook MUST NOT hang. It must timeout in ≤10ms and execute the declared `cold_path_fallback` synchronously without disrupting the user prompt.
3. **Standard Lifecycle Control**:
   - Services must respond to standard lifecycle verbs: `start`, `stop`, `status`, `restart`, `health`.
4. **Daemon Supervision**:
   - On Linux systems with systemd, a user service template (`systemd/my-plugin.service`) must be provided. On macOS, WSL, or non-systemd environments, a self-supervising supervisor daemon fallback is used.
5. **No Forking in Boot**:
   - Shell boot scripts must NEVER launch the service directly using `&` or `coproc`. Daemon spawning is handled out-of-band via systemd user services or on-demand socket activation.

---

## 7. Anti-Patterns

Any plugin containing one or more of the following 6 anti-patterns will be flagged as **REJECTED** by `ziro analyze` and denied certification:

### Anti-Pattern 1: Monolithic Single-File Without Boundaries
- **Description**: Bundling environment setup, completion definitions, key bindings, and heavy functions in a single `plugin.zsh` file.
- **Why Forbidden**: Prevents the behavior analyzer from isolating cheap setup from heavy runtime code, forcing the entire payload into eager loading.
- **Ecosystem Example**: Pre-v2.0 `ziro-ghost` monolithic script (loaded 19 internal scripts synchronously on boot).

### Anti-Pattern 2: Side Effects at Sourcing Time
- **Description**: Spawning background subshells, performing network requests, or executing synchronous file system scans during script evaluation.
- **Why Forbidden**: Completely blocks prompt display.
- **Ecosystem Example**: `_ghost_warmup` in early Ghost releases, which spawned background coprocs and warmed cache synchronously, incurring a **246.3ms** cold boot penalty.

### Anti-Pattern 3: Inline Daemon Spawning in Eager Path
- **Description**: Launching daemons via `coproc`, `eval`, or background subshells (`(daemon &)`) during shell startup.
- **Why Forbidden**: Leads to process contention, broken tty modes, file descriptor leaks, and hangs in subshells.
- **Resolution**: Use `background-service` with Unix sockets and external process supervision.

### Anti-Pattern 4: Hot-Path `eval` Expressions
- **Description**: Calling `eval "$(<binary> init zsh)"` directly in the eager boot sequence.
- **Why Forbidden**: Spawns an external subprocess and forces the Zsh parser to interpret generated text on every startup, adding 15–40ms of latency per tool.
- **Resolution**: Cache evaluation output using compiled `.zwc` caches (`znap eval` or Ziro compiled cache artifacts).

### Anti-Pattern 5: Shared Mutable State Across Capabilities
- **Description**: Modules mutating global variables or associative arrays owned by companion modules without declaring an explicit `core` dependency.
- **Why Forbidden**: Causes race conditions and nondeterministic behavior when capabilities load asynchronously across stage 5 slots or on-demand triggers.
- **Resolution**: Encapsulate all shared state in a declared `core` capability loaded eagerly.

### Anti-Pattern 6: Missing Trigger on On-Demand Capabilities
- **Description**: Declaring `strategy = "on-demand"` without providing an explicit `trigger` (`key:`, `command:`, or `event:`).
- **Why Forbidden**: The generator cannot infer how to wire the lazy stub, causing undefined function lookups when the user enters commands.
- **Resolution**: Explicitly declare triggers in `plugin.toml`.

---

## 8. Mandatory Tests

Every plugin author must supply 5 automated verification tests located in the `tests/` directory:

1. **Independence Test (`test_independence.zsh`)**:
   - Verifies that loading capability A does not implicitly load capability B or set internal guard flags (e.g., loading `modules/core/init.zsh` must not set `_MY_PLUGIN_LINE_LOADED`).
2. **Cost Verification Test (`test_cost.zsh`)**:
   - Profiles execution time under isolated Zsh sessions (`zsh -f`). Measured startup cost must not exceed 2x the declared `est_cost_ms` in `plugin.toml`.
3. **Shim Zero-Side-Effect Test (`test_shim.zsh`)**:
   - Validates that defining the capability shim produces empty stdout/stderr, zero subprocess forks, and no unexpected global variable mutations.
4. **Service Cold-Fallback Test (`test_service.zsh`)**:
   - Terminates the background daemon (`kill -9 <daemon_pid>`), triggers the shell integration, and asserts that the shell remains responsive, executes the fallback path, and returns exit code 0.
5. **Analyzer Compliance Test (`test_analyzer.py`)**:
   - Runs `ziro analyze --explain <plugin_path>` and asserts that the analyzer correctly categorizes all declared capabilities with zero security warnings.

---

## 9. Migration from Spec 012

Spec 012 supported only single-file plugins mapped to a single loading strategy. Migration to SPEC-027 is straightforward and non-breaking for existing single-capability plugins.

### Single-File Compatibility
Single-capability plugins remain fully valid under SPEC-027. An existing single-file plugin can be migrated by adding a minimal `plugin.toml` manifest:

```toml
# Legacy Spec 012 translation
[plugin]
name = "simple-plugin"
version = "1.0.0"
ziro_min_version = "1.4.0"

[[capability]]
name = "main"
type = "core"
strategy = "deferred-s5"
shimmable = true
est_cost_ms = 3.0
files = ["simple-plugin.plugin.zsh"]
```

### Multi-Capability Refactoring Strategy
1. **Identify the Core**: Move variable exports, paths, and minimal state variables into `modules/core/init.zsh` (`strategy = "eager"`).
2. **Isolate Widgets & Prompts**: Move autosuggestion and syntax highlighting hooks into `modules/line/init.zsh` (`strategy = "deferred-s5"`).
3. **Extract Heavy Commands**: Wrap interactive menus, popups, and utility commands in `modules/<cmd>/invoke.zsh` (`strategy = "on-demand"`).
4. **Offload Continuous Tasks**: Move caches, warmups, and indexers into `service/server.zsh` (`strategy = "background-service"`).

---

## 10. Cross-Repo Contract with SPEC-025 and SPEC-026

1. **SPEC-025 Interaction (Modular Defer Behavior Analyzer)**:
   - SPEC-025 introduces the automated analyzer (M06) and lazy-shim generator (M09). SPEC-027 provides the AST taxonomy, manifest parser schema, and shim emission rules that SPEC-025 requires. Third-party plugins adhering to SPEC-027 are automatically classified with 100% confidence.
2. **SPEC-026 Interaction (Ghost Modularity)**:
   - `ziro-ghost` v2.1.0 serves as the reference implementation of SPEC-027. Its 6 discrete capabilities (`ghost-core`, `ghost-line`, `ghost-popup`, `ghost-focus`, `ghost-warmup`, `ghost-ui`) are mapped directly to SPEC-027 strategies:
     - `ghost-core`: `eager` (≤0.5ms)
     - `ghost-line`: `deferred-s5` (precmd autosuggestions)
     - `ghost-popup`: `on-demand` (Tab key trigger, Rust binary)
     - `ghost-focus`: `on-demand` (CLI / hotkey invocation)
     - `ghost-warmup`: `background-service` (Unix socket daemon, eliminating the 246ms bug)
     - `ghost-ui`: `deferred-s5` (ANSI/terminal preview helpers)

---

## 11. Success Criteria (Testable Acceptance Criteria)

- [ ] **AC-1**: Manifest parsing validates against `plugin.toml` schema and rejects missing required fields.
- [ ] **AC-2**: Generator recognizes all 7 strategies without syntax errors or unhandled branches.
- [ ] **AC-3**: Shim generator creates atomic lazy stubs satisfying the 3-condition shim rule.
- [ ] **AC-4**: Zero plugins adhering to SPEC-027 exceed a 2.0ms boot cost for eager capabilities.
- [ ] **AC-5**: Any plugin exhibiting one of the 6 anti-patterns is flagged with an explicit rejection error by `ziro analyze`.
- [ ] **AC-6**: Automated compliance suite passes all 5 mandatory test classes.

---

## 12. Out of Scope

- Implementing the SPEC-025 AST analyzer engine (covered in SPEC-025 M06–M10).
- Refactoring `ziro-ghost` repository source code (covered in SPEC-026 M01–M06).
- Deprecating or deleting Spec 012 files from `.specify/specs/` (deferred to subsequent implementation phase).
- Dynamic package manager download or dependency resolution (managed by existing Ziro core tools).
