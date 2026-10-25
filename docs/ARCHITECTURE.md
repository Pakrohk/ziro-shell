# Ziro System Architecture: Layered Runtime Model

This document specifies the technical architecture of Ziro Shell (`ziro-shell`), defining component boundaries, data contracts, execution lifecycles, and performance invariants.

---

## 1. Architectural Invariants & Execution Boundaries

Ziro enforces a strict separation between cold-path configuration synthesis and hot-path shell initialization:

```
COLD PATH (Build / Sync / Analyze)                 HOT PATH (Interactive Shell Startup)
Budget: ≤ 5.0s (Async / Python 3.12+ stdlib)       Budget: ≤ 5.0ms (Zero-fork pure Zsh)
┌─────────────────────────────────────────┐       ┌──────────────────────────────────────┐
│  Plugin Repositories & External Tools   │       │  User launches terminal emulator     │
└────────────────────┬────────────────────┘       └──────────────────┬───────────────────┘
                     │                                               │
                     ▼                                               ▼
┌─────────────────────────────────────────┐       ┌──────────────────────────────────────┐
│  Layer 1: Static Analyzer (spec 001)    │       │  ~/.zshrc                            │
│  - AST & regex heuristic inspection     │       │  └── source ~/.config/ziro/boot.zsh  │
│  - Security trust engine (ADL-024)      │       └──────────────────┬───────────────────┘
└────────────────────┬────────────────────┘                          │ (7-line shim)
                     │                                               ▼
                     ▼                                    ┌──────────────────────┐
┌─────────────────────────────────────────┐               │ ziro-boot.zsh.zwc    │
│  ~/.config/ziro/load.toml               │               │ (Compiled bytecode)  │
│  - Canonical declarative state          │               └──────────┬───────────┘
│  - Preserves [user] overrides verbatim  │                          │
└────────────────────┬────────────────────┘                          ▼
                     │                            ┌──────────────────────────────────────┐
                     ▼                            │  Layer 2: ziro-defer Runtime         │
┌─────────────────────────────────────────┐       │  - Stage 0-4 eager execution         │
│  Layer 3: Build Pipeline (core/build.py)│       │  - Stage 5 post-prompt dispatch      │
│  - Flattens dependencies                │       │  - Stage 7 on-demand stubbing        │
│  - Synthesizes ~/.cache/ziro/ziro-boot  │       └──────────────────┬───────────────────┘
│  - Compiles eager artifacts to .zwc     │                          │
└─────────────────────────────────────────┘                          ▼
                                                  ┌──────────────────────────────────────┐
                                                  │  Layer 3: UI & Completion Core       │
                                                  │  - ziro-ghost ZLE hooks              │
                                                  │  - Interactive prompt rendered       │
                                                  └──────────────────────────────────────┘
```

### 1.1 Non-Negotiable Performance Budgets
- **Startup Metrics Hierarchy**:
  - `M-1 (Bare interpreter)`: `zsh -f -i -c exit` (~0.95ms baseline).
  - `M-2 (Real interactive shell)`: `zsh -i -c exit`. Target: `< 20.0ms`.
    - Measured live performance: **16.10ms – 16.78ms median** (post-integration architecture, down from 22.14ms baseline).
    - Compinit floor: **6.75ms** (synchronous `compinit -C` represents 67% of startup time).
    - Practical floor for pure Zsh interactive startup with complete completion validation: `~16.0ms`.
  - `M-3 (Full prompt with warm completions)`: ~7.01ms median.
- **Latency & Interactive Responsiveness (zsh-bench Docker isolation)**:
  - `first_prompt_lag`: **19.59ms** (actual fully interactive prompt, avoiding premature fakeouts).
  - `first_command_lag`: **19.93ms** (versus Zinit Turbo: 56.97ms, ~3x faster).
  - `input_lag`: **0.18ms** (versus Zinit Turbo: 14.69ms, ~80x lower input latency).
  - `exit_time`: **20.57ms** (versus Zinit Turbo: 40.12ms, 2x faster).
- **Subprocess Fork Budget**: Exactly **0 forks** permitted across Stages 0 through 4. No `cat`, `sed`, `grep`, `awk`, subshells `(...)`, or command substitutions `$(...)`. All file and environment checks use native Zsh parameter expansions and modules (`zsh/datetime`, `zsh/stat`, `zsh/parameter`).

### 1.2 The Compiled-Only Bytecode Invariant (ADL-015)
To eliminate filesystem stat overhead and on-the-fly parsing in the hot path, every eager artifact loaded during boot must exist as compiled Zsh bytecode (`.zwc`):
1. **Boot Shim Guard**: `~/.config/ziro/boot.zsh` checks for `~/.cache/ziro/ziro-boot.zsh.zwc`. If missing, execution halts immediately with `return 1` and a diagnostic message. Fallback to uncompiled `.zsh` is prohibited.
2. **Build Freshness Verification**: `core/build.py` validates that for every eager entry in `load.toml`, `file.zsh.zwc` exists and `mtime(.zwc) > mtime(.zsh)`. Builds fail with exit code 1 if any eager bytecode artifact is missing or stale.
3. **Doctor Verification**: `ziro doctor` validates eager compiled artifact counts (4/4 mandatory core artifacts) and reports uncompiled files as errors.

---

## 2. The 4-Layer Architectural Model

Ziro structures responsibilities across four distinct layers (Spec 000):

```
┌────────────────────────────────────────────────────────────────────────┐
│ Layer 3: Autocompletion & UI Subsystems (ziro-ghost, widgets, popups)  │
├────────────────────────────────────────────────────────────────────────┤
│ Layer 2: Multi-Stage Task Scheduler (ziro-defer runtime engine)        │
├────────────────────────────────────────────────────────────────────────┤
│ Layer 1: Cold-Path Analyzer & Heuristics (Python 3.12+ AST & Security) │
├────────────────────────────────────────────────────────────────────────┤
│ Layer 0: Shell Bootstrap & Minimal Shim (~/.config/ziro/boot.zsh)      │
└────────────────────────────────────────────────────────────────────────┘
```

### Layer 0: Shell Bootstrap
- **Components**: `~/.config/ziro/boot.zsh` (shim), `~/.cache/ziro/ziro-boot.zsh` (synthesized script), `~/.cache/ziro/ziro-boot.zsh.zwc` (compiled bytecode).
- **Responsibility**: Initialize shell execution with minimal instructions, delegate immediately to compiled bytecode, and enforce compiled-only runtime integrity.
- **Constraints**: Hot path. Strictly 7 lines in `boot.zsh`. Zero subshells, zero forks, zero external commands.
- **Implementation**:
  ```zsh
  # Generated by ziro sync — do not edit
  # Rule: everything in ziro must be compiled (.zwc). Run `ziro sync` if .zwc missing.
  if [ ! -f "$HOME/.cache/ziro/ziro-boot.zsh.zwc" ]; then
    echo 'ziro: ziro-boot.zsh.zwc missing (rule: everything compiled). Run: ziro sync' >&2
    return 1
  fi
  source "$HOME/.cache/ziro/ziro-boot.zsh"
  ```

### Layer 1: Cold-Path Analyzer & Security Engine
- **Components**: `core/analyzer.py`, `core/models.py`, `core/analyze_cli.py`.
- **Responsibility**: Inspect plugin source code, parse AST patterns and regular expressions, evaluate performance hooks, run security heuristics, calculate trust scores (0–4), and generate recommendations.
- **Constraints**: Cold path only (`ziro analyze`, `ziro plugin add`). Written in Python 3.12+ standard library (`re`, `subprocess`, `pathlib`, `tomllib`). No PyO3, no non-stdlib dependencies. Never runs during shell startup.
- **Contract Output**: Analysis metadata mapped to `load.toml` schema and `~/.cache/ziro/analysis/<plugin>.json`.

#### Pattern Detection Heuristics
The static analyzer scans `.zsh` and `.sh` files for critical lifecycle hooks without executing them:
- `compdef`: `^\s*#?compdef\b` → Marks plugin as completion provider requiring Stage 2 `$fpath` injection.
- `zle_n`: `^\s*zle\s+-N\s+` → Detects ZLE custom widget definitions.
- `zle_hook`: `add-zle-hook-widget\s+(\w+)` → Identifies interactive hooks (e.g., `zle-line-init`, `zle-line-finish`).
- `zsh_hook`: `^\s*add-zsh-hook\s+([a-z_][a-z0-9_]*)\s` → Flags standard hooks (`precmd`, `preexec`, `chpwd`, `periodic`).
- `bindkey`: `^\s*bindkey\s+` → Triggers on-demand key candidate detection or Stage 4 eager binding requirement.
- `prompt_var`: `^\s*(PROMPT|PS1|RPROMPT|RPS1)\s*=` → Categorizes tool as a prompt engine requiring Stage 4 evaluation.
- `eval_subprocess`: `eval\s+"\$\(([^)]+)\)"` → Detects dynamic initialization commands (e.g., `eval "$(starship init zsh)"`) requiring eval-cache compilation.

#### Schema A Data Contract (Wire Format)
Stored at `~/.cache/ziro/analysis/<plugin>.json`:
```json
{
  "plugin": "fast-syntax-highlighting",
  "source": "zdharma-continuum/fast-syntax-highlighting",
  "detected": {
    "hooks": ["precmd", "chpwd"],
    "zle_widgets": true,
    "compdef": false,
    "bindkey": false,
    "eval_commands": [],
    "is_prompt": false
  },
  "recommended": {
    "stage": 5,
    "slot": "b",
    "name": "fast-syntax-highlighting",
    "depends": [],
    "condition": null,
    "on_key": null,
    "cache_type": "compiled_zwc",
    "timeout_ms": 5000,
    "strategy": "lazy",
    "compile": true,
    "eval_cache": false,
    "confidence": 0.95
  },
  "security": {
    "trust_score": 4,
    "trust_level": "high",
    "signals": {
      "known_org": true,
      "has_release_tag": true,
      "recent_activity": true,
      "source_clean": true
    },
    "notes": []
  },
  "analyzed_at": "2026-10-23T12:00:00Z",
  "analyzer_version": "2.0.0"
}
```

### Layer 2: Multi-Stage Task Scheduler
- **Components**: `ziro-defer` runtime (`stages/*`, `core/*`, `api/*`, `cache/*`).
- **Responsibility**: Enforce the 8-stage execution lifecycle, dispatch tasks according to 4 priority slots (`a`, `b`, `c`, `d`), manage 6 cache categories, evaluate conditional flags, and resolve prerequisite graphs with cycle protection.
- **Constraints**: Zero forks on Stages 0–4. Single dispatcher hooks into `precmd` and ZLE. Module-level lazy loading (`_ziro_defer_need`) ensures uncalled defer subsystems (idle, batch, stats) consume 0ms at boot.

### Layer 3: Autocompletion & UI Subsystems
- **Components**: `ziro-ghost` (ghost-text suggestions, popup widgets, menu navigation), `ziro-pf` (package manager fuzzy search).
- **Responsibility**: Interactive typing assistance, ghost text rendering via ZLE post-redisplay hooks, and asynchronous fuzzy UI interfaces.
- **Constraints**: Plugin Sovereignty (Principle XIV). Must function as an independent `.zsh` plugin outside of Ziro Shell. Consumes Layer 2 scheduling contracts for non-blocking initialization.

---

## 3. 4-Tier Load Timing Model

Ziro replaces binary load choices (eager vs. post-prompt) with a deterministic 4-tier loading model (ADL-004, ADL-025):

| Tier | Lifecycle Point | Defer Stage | Typical Components | Execution Budget | Trigger / Mechanism |
|---|---|:---:|---|---|---|
| **Eager (Pre-Compinit)** | Before `compinit` parses namespace | Stage 2 | `zsh-completions`, core git completion paths | `< 1.0ms` | `$fpath` injection, `#compdef` queue |
| **Eager (Pre-Prompt)** | Immediately before interactive prompt | Stage 4 | `starship` (eval-cache), `zcolors`, `ziro-aliases-core`, `ziro-keybindings`, `ohmyzsh-ssh-agent`, `ziro-ssh-config` | `< 1.0ms` (cached) `< 10ms` (uncached) | Direct `.zwc` source, eval-cache hits |
| **Deferred** | Immediately after primary prompt | Stage 5 | `fast-syntax-highlighting`, `ziro-ghost`, `fzf-tab`, `aliases.zsh` (extended safety aliases) | `< 5000ms` per task | Single `precmd` dispatcher, priority slots `a`–`d` |
| **On-Demand** | User invokes command, function, or key | Stage 7 | `fzf` (`^R`, `^T`, `^[c`), `zoxide` (`z`, `zi`), `wd`, helpers (`mkcd`, `take`, `extract`, `clipcopy`, `clippaste`) | `< 30ms` perceived latency | Dynamic un-stubbing proxy functions |

### 3.1 Tier Details & Mechanics

1. **Eager Stage 2 (Pre-Compinit)**:
   - Augments `$fpath` with plugin function directories before Zsh's completion system runs.
   - Stubs `compdef` calls via `_ziro_compdef_queue` if invoked prior to completion activation.
   - Prevents completion definitions from being omitted during initial `.zcompdump` analysis.

2. **Eager Stage 4 (Pre-Prompt)**:
   - Evaluates terminal visuals required on the very first frame.
   - Sources `starship` via version-keyed eval cache (`~/.cache/ziro/eval-cache/starship_<hash>.zsh.zwc`).
   - Loads core navigation shortcuts (`aliases-core.zsh`), shell options (`setopt autocd`), standard keybindings (Home, End, Del, PgUp, PgDn), and OpenSSH agent configuration without prompt blocking.

3. **Deferred Stage 5 (Post-First-Prompt)**:
   - Fires during the first `precmd` event after the cursor appears.
   - Partitioned across 4 priority slots (`a` critical -> `b` normal -> `c` lazy -> `d` background).
   - Loads terminal decoration, syntax highlighting engines, and ghost text completion without impacting initial keystroke latency.

4. **On-Demand Stage 7 (Triggers & Proxies)**:
   - Completely omits heavy utilities from initial shell memory.
   - Proxies un-stub dynamically upon first execution, source underlying scripts, and pass arguments cleanly.

---

## 4. Cold Path vs. Hot Path Architecture

### 4.1 Cold Path: Manifest Generation & Artifact Synthesis
The cold path executes explicitly via CLI commands or automated package operations:

```
[ tools_factory.toml ] + [ Installed Plugins ]
                     │
                     ▼
             ziro analyze [--full]
                     │  (Reads disk, parses regex patterns, runs security engine)
                     ▼
            [ ~/.config/ziro/load.toml ]
                     │  (Sections: [meta], [boot], [defer], [[tool]], [user.override])
                     ▼
                 ziro sync
                     │  (Merges overrides, inlines Defer core, resolves paths)
                     ▼
        [ ~/.cache/ziro/ziro-boot.zsh ]
                     │
                     ▼
           zcompile -U -M <artifacts>
                     │
                     ▼
        [ ~/.cache/ziro/ziro-boot.zsh.zwc ] + Eager .zwc Artifacts
```

- **`ziro analyze`**: Audits installed plugins and registered tools. Operates in read-only audit mode by default. When invoked with `--full`, regenerates `load.toml` while strictly preserving the `[user]` table verbatim.
- **`ziro sync`**: Reads `load.toml`, processes active overrides, inlines the 10 eager `ziro-defer` modules, renders on-demand proxy definitions, writes `~/.cache/ziro/ziro-boot.zsh`, and compiles all eager scripts into `.zwc`.

#### Canonical `load.toml` Structure
The `load.toml` file represents the declared configuration state:
```toml
[meta]
version = "1.2.0"
generated_at = "2026-10-23T12:00:00Z"
compiled_only = true

[boot]
shim = "~/.config/ziro/boot.zsh"
artifact = "~/.cache/ziro/ziro-boot.zsh"
bytecode = "~/.cache/ziro/ziro-boot.zsh.zwc"

[defer]
root = "~/.ziro/vendor/ziro-defer"
eager_modules = [
  "stages/stage-0-pre-source.zsh",
  "core/version.zsh",
  "config/defaults.zsh",
  "core/queue.zsh",
  "core/task-registry.zsh",
  "core/scheduler.zsh",
  "core/hooks.zsh",
  "api/ziro-defer.zsh",
  "api/ziro-defer-bind-widget.zsh",
  "api/ziro-defer-dispatch.zsh",
]

[[tool]]
name = "starship"
enabled = true
timing = "eager"
order = 10
method = "eval-cache"
command = "starship init zsh --print-full-init"
cache_path = "~/.cache/ziro/eval-cache/starship_init.zsh"
reason = "prompt engine required for initial frame"

[[tool]]
name = "fast-syntax-highlighting"
enabled = true
timing = "deferred"
order = 20
method = "source"
stage = 5
slot = "b"
path = "~/.local/share/ziro/vendor/fast-syntax-highlighting/fast-syntax-highlighting.plugin.zsh"
reason = "syntax highlighter deferred to post-prompt"

[[tool]]
name = "zoxide"
enabled = true
timing = "on-demand"
order = 30
method = "eval-cache"
trigger = "command"
trigger_commands = ["z", "zi"]
cache_path = "~/.cache/ziro/eval-cache/zoxide_init.zsh"
reason = "directory jumper un-stubbed on command invocation"

[user.override]
# User overrides are preserved verbatim across all `ziro analyze` runs
[[user.override]]
name = "fast-syntax-highlighting"
timing = "deferred"
slot = "a"
reason = "user requested priority promotion"
```

#### Bytecode Compilation Protocol (`_run_zcompile`)
During `ziro sync`, compilation occurs in a single subshell invocation to eliminate fork penalties:
```zsh
for f in $files; do zcompile -U -M "$f" || zcompile "$f"; done
```
Flags utilized:
- `-U`: Disables alias expansion during compilation, preventing existing environment aliases from mutating compiled definitions.
- `-M`: Maps the compiled `.zwc` file directly into memory with `mmap()`, allowing multiple concurrent Zsh processes to share pages and reducing startup memory footprint.

### 4.2 Hot Path: Zero-Fork Bytecode Sourcing
When a new Zsh session begins:
1. `~/.zshrc` executes a single statement: `source ~/.config/ziro/boot.zsh`.
2. `boot.zsh` verifies the existence of `ziro-boot.zsh.zwc` and sources `~/.cache/ziro/ziro-boot.zsh` (Zsh automatically executes the `.zwc` sibling when mtime is fresh).
3. The flat, pre-compiled file loads:
   - Inlined Defer v2 core modules.
   - Stage 0 environment variables and high-resolution timing (`zsh/datetime`).
   - Section 2 eager tools (compiled `.zwc` paths).
   - Section 3 deferred tool task registrations into memory arrays.
   - Section 4 on-demand proxy stubs.
   - Section 5 CLI lazy loader wrapper (`ziro() { ... }`).
   - Section 6 precmd dispatcher hook registration.

### 4.3 On-Demand Proxy Un-Stubbing Mechanics (ADL-022)
Early proxy implementations relied on Zsh `$0` dynamic evaluation inside aliased functions, triggering infinite recursion loops (`FUNCNEST` limit exceeded) due to `FUNCTION_ARGZERO` behavior. Ziro implements Candidate A (Explicit Stub Injection + Self-Unfunction):

```zsh
# Generated proxy for command 'wd'
_ziro_proxy_wd() {
  local _target_cmd="$1"; shift
  unfunction _ziro_proxy_wd wd 2>/dev/null
  source "$HOME/.local/share/ziro/vendor/wd/wd.plugin.zsh"
  "$_target_cmd" "$@"
}
wd() { _ziro_proxy_wd "$0" "$@"; }
```

Execution flow:
1. User types `wd list`.
2. The stub function `wd` executes, passing its own name (`"$0"`) as `$1`, followed by all arguments (`"$@"`).
3. `_ziro_proxy_wd` captures the command name, shifts arguments, and executes `unfunction` on both the proxy and the command stub.
4. The target implementation script is sourced into the current shell process.
5. The real target command is invoked directly with original parameters.
6. Subsequent calls run the loaded tool directly with zero proxy overhead.

---

## 5. Security Engine Architecture (ADL-024)

Ziro incorporates an automated security heuristic within Layer 1 to evaluate plugin provenance, repository stability, and source safety before granting eager execution privileges.

```
                      ┌────────────────────────────────────────┐
                      │        Plugin Source / Git Repo        │
                      └───────────────────┬────────────────────┘
                                          │
            ┌─────────────────────────────┼────────────────────────────┐
            ▼                             ▼                            ▼
   [ Signal 1: Org ]             [ Signal 2: Tag ]           [ Signal 3: Activity ]
   10 Allowlisted Orgs           git describe / tag          Commit < 365 days
            │                             │                            │
            └─────────────────────────────┼────────────────────────────┘
                                          ▼
                             [ Signal 4: Source Clean ]
                             9 Dangerous Regex Patterns
                                          │
                                          ▼
                             [ Trust Score: 0 to 4 ]
                             Trust Level: high | medium | low | unknown
                                          │
                                          ▼
                         ┌─────────────────────────────────┐
                         │   8-Row Decision Matrix Engine  │
                         │   (Reconcile Perf with Trust)   │
                         └────────────────┬────────────────┘
                                          │
                     ┌────────────────────┴────────────────────┐
                     ▼                                         ▼
            [ Standard State ]                         [ Conflict State ]
            - eager (agree)                            - CONFLICT: perf=eager, security=defer
            - lazy (agree)                             - BLOCKED: dangerous patterns detected
```

### 5.1 The 4 Authoritative Signals
Trust evaluation produces a composite score from four binary checks:

1. **`known_org`**: The plugin author or GitHub organization matches the curated allowlist:
   - `zsh-users`, `ohmyzsh`, `romkatv`, `Pakrohk`, `sobolevn`, `Aloxaf`, `zdharma-continuum`, `mfaerevaag`, `MichaelAquilina`, `marlonrichert`.
2. **`has_release_tag`**: Repository contains valid Git release tags (`git describe --tags` or `git tag`).
3. **`recent_activity`**: Repository has at least one Git commit timestamp within the preceding 365 days.
4. **`source_clean`**: Plugin source files (`**/*.zsh`, `**/*.sh`) are free of dangerous patterns. Scanned with comments stripped against 9 regular expressions:
   - `sudo\s`
   - `curl[^\n]*\|\s*(sh|bash|zsh)`
   - `wget[^\n]*\|\s*(sh|bash|zsh)`
   - `eval\s+["'$]+\(?curl`
   - `eval\s+["'$]+\(?wget`
   - `source\s+https?://`
   - `\.\s+/dev/tcp/`
   - `nc\s+-e`
   - `base64\s+-d[^\n]*\|\s*(sh|bash)`

### 5.2 Trust Scoring and Levels
Scores are calculated via `_trust_score()`:
- **`high`**: Score `3` or `4` (requires source readability on disk).
- **`medium`**: Score `2`.
- **`low`**: Score `0` or `1`.
- **`unknown`**: Source code unreadable on disk (disk path missing or inaccessible).
- **`internal`**: Local tools bundled within the Ziro distribution (automatically trusted).

### 5.3 The 8-Row Decision Matrix
The decision matrix (`_apply_decision_matrix()`) reconciles performance recommendations with security posture:

| Row | Trust Level | Performance Recommendation | Dangerous Patterns | Final Strategy | Security Report Status | Blocked | Override Required |
|:---:|:---|:---:|:---:|:---:|:---|:---:|:---:|
| 1 | `high` / `internal` | `eager` | No | `eager` | `agree` | No | No |
| 2 | `high` / `internal` | `lazy` | No | `lazy` | `agree` | No | No |
| 3 | `medium` | `eager` | No | `eager` | `warning — medium trust` | No | No |
| 4 | `medium` | `lazy` | No | `lazy` | `warning — medium trust` | No | No |
| 5 | `low` | `eager` | No | `deferred` | `CONFLICT — perf=eager, security=deferred (low trust)` | No | No |
| 6 | `low` | `lazy` | No | `lazy` | `agree (low trust)` | No | No |
| 7 | `unknown` | *any* | Yes | `BLOCKED` | `BLOCKER — refuse unless --force` | **Yes** | **Yes** |
| 8 | `unknown` | *any* | No | `deferred` | `warning — unknown trust, deferring` | No | No |

### 5.4 Reconciling Security Downgrades with User Intent
1. **No Silent Downgrades**: If a plugin's technical characteristics demand eager initialization (e.g., keybindings or completion hooks) but its trust level is `low`, Ziro never silently forces eager execution or silently breaks functionality. It downgrades the plugin to `deferred` and generates an explicit `CONFLICT` notice.
2. **Blocker Protection**: Unknown plugins containing dangerous shell constructs (such as piping curl output directly into a shell interpreter) are marked `BLOCKED`. Installation halts immediately.
3. **Explicit Escape Hatch**: Users retain sovereign control over their configuration. Blocked installations or security downgrades can be explicitly overridden using the `--force` flag during `ziro plugin add`:
   ```bash
   ziro plugin add untrusted-author/custom-tool --force --eager
   ```
   Forced configurations are recorded within the `[user.override]` section of `load.toml`, guaranteeing that subsequent automated analysis runs do not overwrite user intent.
