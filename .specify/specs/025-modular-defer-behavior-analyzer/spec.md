# SPEC-025: Modular Defer Engine & Behavior-Driven Plugin Analyzer

- **Status**: Draft / In-Progress
- **Date**: 2026-11-04
- **Version**: 1.1.0
- **Revision**: 2026-11-04 — Added capability axis (§2.3), service model (§2.4), bench methodology boundary (§2.4.4), expanded milestones, cross-repo dependency link to SPEC-026 (§5).
- **Authors**: Ziro Core Team & Community
- **Target Release**: `v1.4.0`

---

## 1. Executive Summary & Problem Statement

### 1.1 The Problems
1. **Monolithic Inlined Defer Overhead**:
   `ziro-defer` is currently inlined into `ziro-boot.zsh` as a monolithic 1050+ line script containing 25 complex Zsh functions (DAG validation, cycle detection, timeouts, and state machines). Sourcing and parsing this in every shell startup incurs **~29ms of pure Zsh interpreter overhead**, ironically becoming the single largest startup bottleneck.
2. **Blind Static Heuristic Analyzer**:
   `analyzer.py` classifies plugins based on static keyword mappings (`category=git -> eager`, `compinit -> eager`, etc.) without introspecting actual runtime behavior. Plugins like `ohmyzsh-git` (which defines completions and aliases never used at first prompt) and `compinit` consume **~24ms** during boot, blocking prompt readiness.
3. **Lack of Background & Resident Memory Loading**:
   No daemon, background worker, or shared memory (RAM hot cache) exists to warm caches, compile artifacts, or inspect plugins off the interactive UI thread.
4. **Atomic Plugin Loading Model (Missing Capability Axis)**:
   Current analyzer assigns a single load strategy per plugin, treating each plugin as a monolithic unit. In reality most plugins bundle multiple independent *capabilities* with distinct cost, dependency, and side-effect profiles:

   | Capability Type | Example | Natural Load Strategy |
   |---|---|---|
   | `alias` definition | `alias ll='eza -al'` | Deferred — shim-able |
   | `function` definition | `foo() { ... }` | Deferred — shim-able |
   | `bindkey` registration | `bindkey '^I' widget` | Deferred — shim-able |
   | `add-zsh-hook` registration | `precmd`/`preexec` | Eager-shim — hook must fire on first prompt |
   | `compdef`/`compinit` call | `compdef _git git` | Lazy-Compinit — defer to first `<Tab>` |
   | ZLE widget binding | `zle -N widget fn` | On-Demand — bind cheap, body deferred |
   | Daemon/server spawn | zoxide init, LSP, fuzzy backend | Background Service — persistent across shells |
   | Static completion list | `.zsh-completions` | Eager (cheap) or Deferred (per-capability choice) |

   Evidence from `ziro bench v2.1`: `ohmyzsh-git` = 27.6ms is not a monolith — its aliases are ~0.2ms, its `compdef` calls ~9ms, its prompt-hook registration ~18ms. Co-locating them under one Eager strategy forces paying the full price at every boot.

5. **No Part-by-Part Execution Path**:
   The build pipeline emits a plugin's source as a single blob. It cannot split a plugin into independently-loadable capability units, cannot keep a subset in a persistent service, and cannot mix strategies within one plugin.

6. **No Persistent Service Model for Long-Lived Components**:
   Plugins that maintain cross-shell state (indexers, watchers, fuzzy backends, history predictors, project markers) re-initialize per shell. The analyzer has no vocabulary for 'this capability should live in a background service, not in the boot path'.

### 1.2 The Solution
1. **Micro-Component Defer Architecture**:
   Split `ziro-defer` into modular micro-components:
   - **Boot Fast-Path (< 0.5ms)**: A 10-line ultra-minimal queue shim injected into `ziro-boot.zsh` that appends commands to an in-memory array. Zero parsing overhead.
   - **Deferred Runtime Modules**: Execution stages, timeouts, and progress reporters are lazy-loaded only when Stage 5 fires.
   - **Rust/Python Defer Core**: Compile DAG dependency resolution, cycle checks, and telemetry into a compiled Rust utility (`ziro-defer-core`).
2. **Behavior-Driven Plugin Analyzer (AST & Execution Introspection)**:
   Instead of keyword matching, the analyzer executes plugins in an isolated sandbox with `zsh -x` trace interception to observe:
   - Does the plugin register ZLE widgets?
   - Does it modify `PROMPT` or `RPROMPT`?
   - Does it call `compdef` or require `compinit`?
   - Does it define aliases or external hooks?
   - Based on observed runtime behavior, assign the plugin to the optimal stage: `Eager`, `Deferred (S5:b)`, `On-Demand (Key/Command)`, or `Background Daemon`.
3. **Shared RAM Hot-Cache & Background Service**:
   Pre-warm plugin state in RAM using background job spawns and shared memory IPC so new terminals open instantly in **< 5ms**.

---

## 2. Technical Architecture

### 2.1 Micro-Defer Topology
```
[Shell Startup: boot.zsh]
       │
       ▼
┌───────────────────────────────────────────────┐
│ Ultra-Minimal Queue Shim (Pure Zsh Array)     │  < 0.3 ms
│ typeset -ga _ZIRO_DEFER_QUEUE=()             │
│ ziro-defer() { _ZIRO_DEFER_QUEUE+=("$*") }   │
└───────────────────────────────────────────────┘
       │
       ▼ (Prompt Displays Instantly)
       │
┌──────┴────────────────────────────────────────┐
│ Stage 5 Precmd Trigger                        │  Deferred Background
│ Lazy-loads full runner / Rust worker          │
└───────────────────────────────────────────────┘
```

### 2.2 Behavior-Driven Analyzer Engine
```
Target Plugin (.plugin.zsh)
       │
       ▼
┌───────────────────────────────────────────────┐
│ Behavioral Sandbox (Introspection VM)         │
│ - Trace function calls (compdef, add-zsh-hook)│
│ - Inspect environment mutations (PROMPT, etc.)│
│ - Measure latency & fork counts               │
└───────────────────────────────────────────────┘
       │
       ▼
┌───────────────────────────────────────────────┐
│ Behavioral Classifier Matrix                  │
│ • Mutates PROMPT/Theme     ──► Eager (Prompt) │
│ • Defines compdef only     ──► Deferred / S5  │
│ • Aliases & CLI helpers    ──► Deferred / S5  │
│ • Standalone CLI commands  ──► On-Demand      │
└───────────────────────────────────────────────┘
```

### 2.3 Plugin Capability Decomposition (Capability Axis)

The analyzer output is no longer a per-plugin label but a **capability map**: for each plugin, a list of `(capability, strategy, confidence, evidence)` tuples.

#### 2.3.1 Capability Taxonomy

| Capability | Detection Signal (sandbox trace) | Shim-able? | Default Strategy |
|---|---|---|---|
| `alias` | `alias name=...` | Yes — alias points to command name | Deferred S5 |
| `function` | `name() { ... }` | Yes — body runs on invocation | Deferred S5 |
| `bindkey` | `bindkey '^X' widget` | Yes — widget can be lazy | On-Demand (key) |
| `zle-widget` | `zle -N widget fn` | Yes — bind cheap, body lazy | On-Demand (key) |
| `compdef` | `compdef fn cmd` | Conditional — needs compinit | Lazy-Compinit |
| `precmd-hook` | `add-zsh-hook precmd fn` | Partial — registration eager, body lazy | Eager-Shim |
| `preexec-hook` | `add-zsh-hook preexec fn` | Partial — same | Eager-Shim |
| `chpwd-hook` | `add-zsh-hook chpwd fn` | Partial — same | Eager-Shim |
| `prompt-mutation` | `PROMPT=...`, `RPROMPT=...` | No — must run before first prompt | Eager |
| `env-mutation` | `export VAR=...`, `path+=...` | No — child processes depend | Eager |
| `daemon-spawn` | `nohup ... &`, socket bind | — | Background Service |
| `binary-fetch` | `curl|tar`, `git clone` | — | Background Service (prefetch) |
| `completion-load` | `source .zsh-completions/...` | Yes — dump load lazy | Deferred S5 or Lazy-Compinit |

#### 2.3.2 Shim-ability Definition

A capability is **shim-able** if and only if:
1. Emitting a lazy shim at definition time produces **zero observable side effects** (no stdout, no env mutation, no fork, no `compdef` side effect).
2. The real implementation can be loaded on first use with identical semantics.
3. Loading order does not matter (shim can be placed before its dependencies without breaking others).

If any condition fails → minimal safe strategy (usually Eager). **Decomposition is opt-in, never mandatory** — a plugin with no shimmable boundary remains single-capability.

#### 2.3.3 Capability-Level Decision Tree (extends M08)

Classifier emits a **strategy vector** per plugin, not a strategy label. Example TOML:

```toml
[[plugin]]
name = "ohmyzsh-git"

[[plugin.capability]]
name = "aliases"
type = "alias"
strategy = "deferred-s5"
shimmable = true
est_cost_ms = 0.2

[[plugin.capability]]
name = "git-completions"
type = "compdef"
strategy = "lazy-compinit"
shimmable = true
est_cost_ms = 9.1

[[plugin.capability]]
name = "prompt-integration"
type = "precmd-hook"
strategy = "eager-shim"
shimmable = true
est_cost_ms = 18.3
```

### 2.4 Persistent Service Model (Background Daemon Axis)

Some capabilities are **fundamentally service-shaped**: heavy init, cross-shell shared state, long-lived caches, or indexers. The analyzer must detect these and propose **service extraction** instead of per-shell loading.

#### 2.4.1 Service Candidate Signals

| Signal | Threshold | Meaning |
|---|---|---|
| Init cost | > 10ms per shell | Warm-up amortizable across shells |
| Cross-shell shared state | Detected (file, socket, mmap) | State survives shell exit |
| Native daemon support | Manifest declares `socket=`, `service=` | Plugin designed for daemon |
| Long-running work | Watcher, indexer, LSP | Per-shell re-init is wasteful |
| Non-interactive dependency | No — only interactive needs it | Safe to defer to daemon |
| Failure recovery | Non-fatal if unavailable | Shims can retry / cold-path |

#### 2.4.2 Service Lifecycle

Managed by Ziro-owned supervisor. Two modes:
- **Systemd user units** (`systemctl --user`): preferred on Linux; survives logout with `enable-linger`. Ziro emits the `.service` file.
- **Ziro-managed daemon pool** (`~/.cache/ziro/daemon/supervisor.sock`): cross-platform fallback (macOS, WSL). Ziro starts it on first shell, stops on idle (configurable TTL).

Boot path always emits a **thin client shim** (`ziro-svc-call <service>` connects to socket, falls back to cold path if daemon unavailable).

#### 2.4.3 Service Interaction Matrix

| Capability | IPC Pattern | Cold-Path Fallback |
|---|---|---|\n| History predictor | Request/response (JSON over socket) | Read from cache file |
| Fuzzy-finder backend | Client passes buffer, backend returns ranked list | Spawn one-off backend |
| LSP / language index | Subscribe (server pushes updates) | Use stale index; show warning |
| Project markers | Request/response (cached) | Scan filesystem sync |
| Binary fetch / prefetch | Fire-and-forget (warm cache) | Block on download |

#### 2.4.4 Two-Tier Bench Methodology & Real Baseline Telemetry

Empirical diagnosis of `ziro bench v2.1` with native `metrics.jsonl` telemetry separates startup into two distinct physical tiers:

1. **Tier 1: Blocking Eager Boot (Time-to-First-Prompt)**
   - Measured by `zsh -c "source ~/.config/ziro/boot.zsh; exit"`.
   - **Current Baseline**: Median **20.29 ms** (Fastest: **18.89 ms**).
   - **Eager Breakdown**:
     * `compinit-dump`: **13.43 ms** (Eager Hotspot)
     * `starship` (eval cache): **8.62 ms** (Eager Moderate)
     * `ziro-defer-core` (parsing Section 1): **7.89 ms** (Eager Moderate)
     * `ziro-aliases` / core: **4.24 ms**
     * `zcolors` / completions / core: **5.33 ms**
   - **Target with SPEC-025**:
     * Minimal Queue Shim (<25 lines) reduces `ziro-defer-core` from 7.89ms to **< 0.3 ms**.
     * Lazy Compinit eliminates `compinit-dump` from boot path (**0 ms** at boot, loaded on first `<Tab>`).
     * Expected Eager Boot Latency: **< 4.0 ms** (meeting the < 5.0ms budget).

2. **Tier 2: Deferred Background Drain (Post-Prompt Stage 5)**
   - Measured via real session execution metrics in `~/.cache/ziro/defer/metrics.jsonl`.
   - Fires during first `precmd` hook after the user already sees the prompt.
   - **Current Baseline**: Total **~215 ms** cumulative background work:
     * `ghost-v2-line`: **62.26 ms**
     * `ghost-warmup`: **60.47 ms**
     * `fast-syntax-highlighting`: **38.05 ms**
     * `ohmyzsh-git`: **19.03 ms**
     * `zsh-you-should-use`: **15.20 ms**
     * `fzf-tab`: **12.83 ms**
     * `ghost-popup-cli` & wrapper: **3.37 ms**
     * `ohmyzsh-colored-man-pages`: **0.17 ms**
   - **Target with SPEC-025**:
     * Persistent Background Daemon offloads `ghost-warmup` (60.5ms) and `ghost-v2-line` (62.3ms) to a long-lived resident service.
     * Capability decomposition shims `ohmyzsh-git` (19.0ms) into instant alias shims (0.2ms) and deferred compdef.
     * Expected Stage 5 Drain: **< 35 ms**.

Cross-tier sums (adding Tier 1 boot time to Tier 2 background tasks) are physically invalid and flagged by `ziro bench`. Every benchmark output must explicitly separate Tier 1 (Prompt Blocking) from Tier 2 (Background Deferred).

---

## 3. Implementation Plan: 17 Milestones

### Phase 1: Architecture & Modular Defer Decomposition (M1 – M5)
- [ ] **M01**: Audit and decompose `ziro-defer` into isolated micro-files: `core/queue.zsh`, `core/registry.zsh`, `core/dag.zsh`, `stages/runner.zsh`.
- [ ] **M02**: Implement the Ultra-Minimal Queue Shim in `core/build.py` (reducing `ziro-boot.zsh` Section 1 from 1050 lines to < 25 lines).
- [ ] **M03**: Implement Lazy Module Loader for Stage 2–6 defer workers (load only when stage is triggered).
- [ ] **M04**: Develop Rust micro-module `ziro-defer-core` for O(1) task DAG cycle validation and topological reordering.
- [ ] **M05**: Verify shell boot startup latency drops below **10.0 ms** with decomposed defer shim.

### Phase 2: Behavior-Driven Plugin Analyzer (M6 – M10)
- [ ] **M06**: Create `core/behavior_sandbox.py`: execute plugin in ephemeral subshell with hook monitors to capture stdout, env mutations, and function definitions:
      - Function/alias definitions
      - `bindkey` / `zle -N` registrations
      - `add-zsh-hook` registrations (per-hook-type)
      - `compdef` calls
      - `export` / `path+=` mutations
      - `PROMPT` / `RPROMPT` writes
      - Daemon spawns (background forks, socket binds)
- [ ] **M06a**: Implement `core/capability_decomposer.py`: parse sandbox trace into capability tuple list; classify each capability by type (taxonomy §2.3.1); compute per-capability estimated cost (fraction of plugin total via trace timing).
- [ ] **M06b**: Implement `core/shimability.py`: for each shimmable candidate, execute two-pass sandbox test: (a) emit shim only → assert zero side effects; (b) emit shim + lazy load on first simulated use → assert identical semantics. Emit `shimmable: true/false` with reason.
- [ ] **M07**: Implement AST & trace parser to detect `compdef`, `add-zsh-hook`, `bindkey`, and widget definitions.
- [ ] **M08**: Build Behavioral Decision Tree: auto-classify plugins based on real runtime signatures rather than static category strings:
      - Input: capability tuple list (from M06a)
      - Output: per-capability strategy vector (not per-plugin label)
      - Rules per capability type:
        * alias → deferred-s5
        * function → deferred-s5 if shimmable, else eager-shim
        * bindkey/widget → on-demand (key/command)
        * compdef → lazy-compinit (integrates M09)
        * precmd/preexec/chpwd hook → eager-shim if shimmable, else eager
        * prompt-mutation → eager (non-negotiable)
        * env-mutation → eager (non-negotiable)
        * daemon-spawn → background-service (integrates M10a/M13b)
      - Confidence score per capability (trace completeness × shimability)
      - Ambiguous capabilities (confidence < 0.7) → safe-default eager + warning
- [ ] **M09**: Implement Lazy Compinit architecture (`compdef` queuing before `compinit`, loading full compdump only on first Tab press) & Lazy Hook & Registration Shim Generator (generalizes lazy compinit):
      - Generate lazy shims for `compdef` calls → queue, replay on first `<Tab>`
      - Generate lazy shims for `bindkey` → bind to proxy, load real widget on first press
      - Generate lazy shims for `add-zsh-hook` → register proxy, load real body on first fire
      - Verify hook fires correctly even if real body never loads (fallback if load fails)
      - Lazy-compinit becomes one specific application, not a special case
- [ ] **M10**: Integrate Behavioral Analyzer into `ziro analyze --full` and update `load.toml` generation with behavioral proofs:
      - `load.toml` gains `[[plugin.capability]]` sub-sections
      - `[user]` overrides supported per-capability (e.g., `[user.override.myplugin.aliases] strategy = "deferred-s5"`)
      - Preserve `[user]` verbatim on re-analyze
      - Emit capability map to `ziro analyze --explain <plugin>`
- [ ] **M10a**: Service Candidate Detector (`core/service_detector.py`): heuristic rules per §2.4.1; emit `[[plugin.capability]] type = "service-candidate"` with proposed IPC pattern + cold-path fallback. Propose only — extraction is opt-in per plugin.
- [ ] **M10b**: Capability-Map Reporting in `ziro doctor`: new check `_check_capability_maps()`. Per plugin: N capabilities, M eager, K deferred, J on-demand, L service. Warn if eager capabilities exceed 5ms AND have shimmable variants.

### Phase 3: Background Service, Daemon & RAM Hot-Cache (M11 – M14)
- [ ] **M11**: Design IPC protocol (FIFO / domain socket) for `ziro-daemon` resident memory coordinator.
- [ ] **M12**: Implement RAM cache provider for pre-compiled ZWC snippets and sanitized history buffers.
- [ ] **M13**: Implement background async worker for plugin warm-up and filesystem updates off the main Zsh thread:
- [ ] **M13a**: Transient warm-up worker: spawns on shell start, compiles ZWC, warms caches, exits. Cross-shell TTL not preserved.
- [ ] **M13b**: Persistent service supervisor: manages registered services from M10a, restarts on crash, exposes health via `~/.cache/ziro/daemon/supervisor.sock`. Boot path emits thin client shims (`ziro-svc-call <svc> <args>`).
- [ ] **M14**: Add lifecycle management commands: `ziro daemon status`, `ziro daemon restart`, `ziro daemon stop`:
      - `ziro daemon status` — list registered services, PIDs, uptime, health
      - `ziro daemon restart <svc>` — graceful restart
      - `ziro daemon stop <svc>` — graceful stop
      - `ziro daemon logs <svc>` — tail logs
      - `ziro daemon service install <svc> --user` — emit systemd unit

### Phase 4: Benchmarking v2.2, Verification & Multi-Arch Build (M15 – M17)
- [ ] **M15**: Upgrade `ziro bench` to v2.2 with Behavioral Profiler integration and Stage-by-Stage Gantt telemetry:
      - Capability-level breakdown: `ziro bench --plugin X --capabilities`
      - Gantt timeline of stage-by-stage + capability-by-capability cost
      - Comparison baseline: 'before decomposition' vs 'after'
      - Explicit methodology label per metric (min/median/worst)
      - Verify claim: 'plugin X now costs 0.3ms at boot (was 27.6ms)' with proof
- [ ] **M16**: Comprehensive end-to-end integration tests (Tab popup, defer execution, zero-lag typing, cold vs hot boot).
- [ ] **M17**: Multi-architecture compilation for Rust binaries (`x86_64`, `aarch64`, `armv7`) and user manual verification gate.

---

## 4. Verification & Success Criteria
1. `ziro bench` Startup (Fastest Min-of-N): strictly **< 8.0 ms** (approaching the 5.0ms target).
2. Zero interactive typing lag (**< 3.0 ms** p95).
3. 100% backward compatibility with existing Zsh plugins and configurations.
4. No automated git push without explicit user approval.
5. **Capability-Level Verification**:
   - `ziro bench --plugin ohmyzsh-git --capabilities` reports ≥ 3 distinct capabilities with per-capability cost (aliases, compdef, prompt-hook)
   - At least 5 eager hotspots from bench v2.1 are decomposed into ≥ 2 capabilities each
   - Missed-shim warnings surface in `ziro doctor` for any plugin where a shimmable capability is loaded eagerly
6. **Service Extraction Verification**:
   - At least 1 service candidate detected (e.g., fuzzy-finder backend, history predictor) and extractable via opt-in
   - `ziro daemon status` reports service state
   - Cold-path fallback verified: killing the service does not break the shell
7. **Safety**:
   - Decomposition failure (opaque plugin, side-effect at load) falls back to monolithic strategy with warning — never breaks plugin semantics
   - `[user]` overrides supported per-capability, preserving backward compat
   - All bench metrics carry explicit methodology label; cross-methodology sums are flagged

---

## 5. Cross-Repo Dependency — SPEC-026

This spec's capability axis (§2.3) requires ziro-ghost to expose independent capabilities. See `.specify/specs/026-ghost-modularity/spec.md` for the ghost-side contract.

**Hard block**: SPEC-025 milestones M06-M10 (behavioral analyzer) cannot ship acceptance until SPEC-026 ships ghost capability decomposition. Milestones M01-M05 (defer decomposition) are orthogonal and can proceed in parallel.

**Revision history**: 2026-11-04 — Added cross-repo dependency link to SPEC-026.


## 6. Cross-Repo Dependency — SPEC-027

SPEC-027 defines the plugin capability contract that SPEC-025's behavior analyzer (M06) and lazy-shim generator (M09) consume. Without SPEC-027, SPEC-025 has no vocabulary to classify third-party plugins. M06-M10 in SPEC-025 depend on SPEC-027 being finalized.

**Revision history**: 2026-11-04 — Added cross-reference to SPEC-027.


