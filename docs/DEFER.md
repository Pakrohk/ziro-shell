# Ziro-Defer v2.0.0: Runtime Task Scheduler Guide

`ziro-defer` v2.0.0 (Spec 005) is a stage-aware, priority-partitioned runtime task scheduler for Zsh. It supersedes legacy binary deferral mechanisms (which merely delayed execution until after the prompt) by orchestrating shell startup, background tasks, and on-demand proxies across 8 deterministic stages with strict latency budgets.

---

## 1. Multi-Stage Execution Lifecycle (8 Stages)

Execution proceeds across 8 numerical stages. Stages 0–4 constitute the synchronous hot path; Stages 5–7 execute cold-path post-startup tasks.

```
HOT PATH (Startup Phase · Cumulative Budget: < 4.6ms · Zero Subprocess Forks)
┌────────────────────────────────────────────────────────────────────────┐
│ Stage 0 — Pre-Source        (< 0.1ms)   XDG paths, datetime hoist      │
│ Stage 1 — Bootstrap         (< 0.5ms)   package manager, defer core    │
│ Stage 2 — Pre-Compinit      (< 1.0ms)   $fpath injection, completions  │
│ Stage 3 — Compinit          (< 2.0ms)   dump verification, compinit -C │
│ Stage 4 — Post-Compinit     (< 1.0ms)   eval-cache hits, starship      │
└────────────────────────────────────────────────────────────────────────┘
                                   │
                         [ First Prompt Displayed ]
                                   │
COLD PATH (Runtime Phase · Event-Driven · Non-Blocking)
┌────────────────────────────────────────────────────────────────────────┐
│ Stage 5 — Post-Prompt       (Timeout 5s) Highlighters, ghost, aliases  │
│ Stage 6 — Idle Maintenance  (Idle > 5s)  Git updates, log compaction   │
│ Stage 7 — On-Demand         (< 30ms)     Command proxies, key widgets  │
└────────────────────────────────────────────────────────────────────────┘
```

### 1.1 Hot-Path Stages (0 through 4)
- **Stage 0: Pre-Source (`< 0.1ms`)**: Canonicalizes XDG directories (`$ZIRO_DATA`, `$ZIRO_CONFIG`, `$ZIRO_CACHE`), loads native C timing (`zmodload -F zsh/datetime b:EPOCHREALTIME`), and initializes global queue associative arrays.
- **Stage 1: Bootstrap (`< 0.5ms`)**: Loads package manager and scheduler core. Registers the single unified `precmd` dispatcher (`add-zsh-hook precmd _ziro_defer_dispatch_precmd`).
- **Stage 2: Pre-Compinit (`< 1.0ms`)**: Ingests `$fpath` additions and processes eager `#compdef` annotations before completion dump analysis.
- **Stage 3: Compinit (`< 2.0ms`)**: Checks `$ZIRO_CACHE/zcompdump`. If younger than 20 hours, runs `autoload -Uz compinit && compinit -C -d "$ZIRO_CACHE/zcompdump"`, bypassing costly security checks.
- **Stage 4: Post-Compinit (`< 1.0ms` fast-cached)**: Sources pre-compiled prompt scripts (`starship` via eval-cache) and terminal resize traps.

### 1.2 Cold-Path Stages (5 through 7)
- **Stage 5: Post-Prompt**: Triggered on the first interactive `precmd` event after the user cursor is drawn. Executes non-blocking utilities (`fast-syntax-highlighting`, `ziro-ghost`, `fzf-tab`) partitioned by priority slots.
- **Stage 6: Idle Maintenance**: Executes when the shell remains idle without input for `$ZIRO_DEFER_IDLE_SECONDS` (default: 5s). Performs remote repository fetch checks and metrics rotation. Aborts immediately upon incoming keystrokes via `zle-line-init`.
- **Stage 7: On-Demand**: Activated on the first invocation of an intercepted command trigger (e.g., `z`, `wd`), shell helper (`mkcd`), or ZLE key shortcut (`^R`, `^T`, `^G`). Un-stubs the proxy and sources the real tool.

---

## 2. Priority Slots (`a`, `b`, `c`, `d`)

Within any stage (most notably Stage 5), tasks are partitioned into 4 priority queues:

| Slot | Semantic Name | Scheduling Behavior | Typical Workloads |
|:---:|:---:|:---|:---|
| **`a`** | **Critical** | Runs first; blocks subsequent slots | Core ZLE keybindings, essential prompt visual fixups |
| **`b`** | **Normal** | Default slot; standard plugins | Syntax highlighting, autosuggestions, ghost text |
| **`c`** | **Lazy** | Deferred until critical systems settle | Git decorations, status monitors, safety aliases |
| **`d`** | **Background**| Lowest priority; runs when idle | Telemetry sync, index warming, cache cleanup |

Tasks within the same slot execute in strict First-In, First-Out (FIFO) registration order:
```zsh
# Priority promotion API: promotes task to slot a for immediate dispatch
ziro-defer-reorder --task="plugin_ghost" --slot=a
```

---

## 3. Dependency Ordering & Tarjan Cycle Protection

Tasks declare prerequisite or successor constraints via `--after` and `--before`:
```zsh
ziro-defer --name="fsh" --after="zcolors" source ~/.ziro/vendor/fsh/fast-syntax-highlighting.plugin.zsh
ziro-defer --name="theme" --before="render-prompt" source ~/.ziro/theme.zsh
```

### Tarjan Cycle Protection Algorithm
Circular dependencies ($A \rightarrow B \rightarrow A$) are intercepted at task registration time using a fast path-tracing cycle detection heuristic:
1. When `--after="target"` is registered, the scheduler traces `_ziro_defer_task_after[$target]` recursively.
2. If the current task ID appears in the ancestor chain, a circular dependency is detected.
3. The scheduler emits a non-fatal warning, unlinks the circular dependency, and schedules both tasks independently in their respective priority slots. Telemetry records `"status": "dependency_cycle_broken"`.

---

## 4. Conditional Deferral Predicates

Tasks support declarative runtime conditions evaluated in `< 0.05ms` before execution:

| Flag | Evaluated Expression | Action on False |
|:---|:---|:---|
| `--if-var=NAME` | `[[ -n ${(P)NAME} ]]` | Skip if variable is unset or empty |
| `--if-cmd=CMD` | `(( $+commands[CMD] ))` | Skip if binary does not exist in `$path` |
| `--if-ssh` | `[[ -n "$SSH_CONNECTION" \|\| -n "$SSH_TTY" ]]` | Skip on local interactive sessions |
| `--if-not-root`| `(( EUID != 0 ))` | Skip when executing as superuser (root) |
| `--if-dir=PATH`| `[[ -d "$PATH" ]]` | Skip if directory does not exist |

Skipped tasks record `"status": "skipped"` in telemetry and never throw errors.

### 4.1 Unified Dispatcher Loop & ZLE Keypress Yielding
Instead of attaching individual shell hooks per plugin, `ziro-defer` uses a single dispatcher loop attached to `precmd`:
```zsh
_ziro_defer_dispatch_precmd() {
  local active_stage=5
  for slot in a b c d; do
    local q_var="_ziro_defer_q_${active_stage}_${slot}"
    for task_id in "${(@P)q_var}"; do
      # Yield immediately if the user has begun typing in ZLE
      if [[ -o zle && $PENDING -gt 0 ]]; then
        return 0
      fi
      _ziro_defer_execute_task "$task_id"
    done
    eval "${q_var}=()"  # Reset executed queue slot
  done
  # Unregister precmd dispatcher once Stage 5 queues are empty
  add-zsh-hook -d precmd _ziro_defer_dispatch_precmd
}
```
This loop architecture bounds hook scheduling from $O(N)$ shell hooks to $O(1)$, preserving typing responsiveness.

---

## 5. Cache Architecture & Invalidation Policies

`ziro-defer` defines 6 discrete cache types with explicit invalidation triggers:

| Cache Type | Storage Location | Default TTL | Invalidation Condition | Write Method |
|:---|:---|:---:|:---|:---:|
| **`eval_output`** | `~/.cache/ziro/eval/` | Permanent | Binary sha256 or version string change | Atomic rename |
| **`compiled_zwc`** | Alongside `.zsh` source | Permanent | `source.zsh.zwc` mtime `<` `source.zsh` mtime | Direct zcompile |
| **`analysis_json`**| `~/.cache/ziro/analysis/` | 7 Days | Plugin commit hash or directory mtime change | Atomic rename |
| **`tag_resolution`**| In-memory associative array | Session | Any modification in `~/.config/ziro/tags/` | Memory reset |
| **`project_markers`**| `~/.cache/ziro/markers/` | 1 Hour | Directory change (`chpwd`) or 3600s elapsed | Atomic rename |
| **`ghost_candidates`**| In-memory LRU (1000 items) | Session | Directory change (`chpwd`) or `SIGUSR1` | Memory reset |

### 5.1 Atomic Writing & Corruption Recovery
- **Atomic Writes**: Writes output to an ephemeral sibling file `${target}.tmp.$$` then issues an atomic filesystem `mv -f "$tmp" "$target"`. Direct truncation on active cache paths is forbidden.
- **Fault Recovery**: Corrupted cache payloads trigger immediate removal (`rm -f "$cache"`), fallback to un-cached generation, and logging of `"status": "cache_corruption_recovered"`.

---

## 6. Observability & Structured JSONL Telemetry

Every task execution appends a newline-delimited JSON record to `$XDG_CACHE_HOME/ziro/defer/metrics.jsonl`:

```json
{
  "ts": 1729091234.567,
  "task": "source ~/.ziro/vendor/fast-syntax-highlighting/fast-syntax-highlighting.plugin.zsh",
  "name": "fast-syntax-highlighting",
  "stage": 5,
  "slot": "b",
  "elapsed_ms": 8.42,
  "status": "success",
  "cached": true,
  "retries": 0
}
```

- **Field Semantics**:
  - `ts`: UNIX epoch timestamp in milliseconds (from `EPOCHREALTIME`).
  - `task`: Executed command string (truncated to 200 characters).
  - `name`: Unique task slug for dependency targeting.
  - `stage` / `slot`: Numerical stage (0–7) and priority slot (`a`–`d`).
  - `elapsed_ms`: Wall-clock execution duration in milliseconds.
  - `status`: Outcome code (`success`, `failure`, `timeout`, `skipped`).
  - `cached`: Boolean indicating if computation was bypassed via cache hit.
  - `retries`: Count of retry attempts executed.
- **Log Rotation**: Logs rotate to `metrics.jsonl.1` when size exceeds 1024 KB or 2000 lines.

---

## 7. Resilient 4-Tier Fallback Chain

When task execution fails or times out (default timeout: 5000ms), `ziro-defer` executes an automated fallback chain:
1. **Transient Retry**: Re-evaluates command once if failure indicates resource contention (`retry_on_failure = false` by default for permanent errors).
2. **Eager Fallback**: If a deferred plugin fails to load asynchronously, falls back to direct synchronous source mode on next shell boot.
3. **Isolated Skip**: If repeated failures occur, marks the task skipped, unblocks dependent tasks, and logs a diagnostic warning to `ziro doctor`.
4. **Rescue Shell Prompt**: Shell initialization never crashes due to a failed deferred task.

---

## 8. CLI Reference & `ziro-boot.zsh` Integration

### 8.1 Scheduler CLI Commands
```zsh
# Schedule a deferred task with dependency and timeout
ziro-defer --stage=5 --slot=b --name="fsh" --after="zcolors" --timeout=3000 <command...>

# Batch register multiple plugins
ziro-defer-batch --stage=5 --slot=b repo/plugin1 repo/plugin2

# Synchronously dispatch all tasks in a stage (used during boot Stages 2-4)
ziro-defer-dispatch 2

# Bind a one-shot on-demand key trigger
ziro-defer-bind-widget '^G' source ~/.ziro/ghost/bin/focus.sh

# Inspect runtime performance telemetry
ziro defer stats
```

### 8.2 Module-Level Lazy Loading in `ziro-boot.zsh`
To avoid paying a ~2.5ms startup penalty for all 33 scheduler source files (ADL-008, ADL-011), `ziro sync` inlines 10 core eager modules into `ziro-boot.zsh` and stubs 22 lazy modules behind `_ziro_defer_need`:
```zsh
# Core eager modules (inlined):
# stage-0, version, defaults, queue, task-registry, scheduler, hooks, ziro-defer, bind-widget, dispatch

# Stubs for on-demand lazy modules:
ziro-defer-stats()   { _ziro_defer_need stats && ziro-defer-stats "$@"; }
ziro-defer-reorder() { _ziro_defer_need reorder && ziro-defer-reorder "$@"; }
ziro-defer-batch()   { _ziro_defer_need batch && ziro-defer-batch "$@"; }
```
This architecture preserves full v2 scheduler functionality while keeping eager scheduler overhead below **1.1ms** at shell startup.
