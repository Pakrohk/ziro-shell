# Declarative Architecture: Plugin Manifests & Build Synthesis

This document specifies Ziro Shell's declarative plugin architecture (Spec 012), its conceptual heritage from Intent-Oriented Programming (IOP), and the mechanisms used to eliminate runtime discovery overhead through build-time synthesis.

---

## 1. Intent-Oriented Programming & EVOID Heritage

Ziro's architectural foundation is permanently inspired by [EVOID](https://github.com/EvolveBeyond/EVOID), the reference runtime for Intent-Oriented Programming (IOP).

> **Core Motto**: *"Data declares what, runtime decides how."*

Traditional shell configurations are imperative: users and plugins write procedural shell commands (`source`, `eval`, `export`, `bindkey`) directly in `.zshrc`. This forces the shell interpreter to discover dependencies, parse files, and evaluate environment conditions on every terminal launch.

Under Intent-Oriented Programming, Ziro inverts this relationship:
1. **Plugins and configurations declare *what*** capabilities they offer, what dependencies they require, and what lifecycle hooks they touch.
2. **The Ziro runtime decides *how* and *when*** to load, compile, defer, or trigger those components based on performance budgets and security trust.

### Immutable Principles Derived from EVOID
- **Declarative over Imperative**: Configuration declares intent; runtime engine compiles execution.
- **Runtime over Framework**: Compose modular adapters and pipelines rather than inheriting monolithic wrappers.
- **Levels over Flags**: Structured priority slots (`a`, `b`, `c`, `d`) replace ad-hoc boolean conditionals.
- **Pipeline over Conditional**: Deterministic scheduler stages replace nested `if/else` shell checks.
- **Adapter over Monolith**: Separate tool definitions from runtime execution mechanics.

---

## 2. Universal Plugin Classification (Types A–D)

Ziro never rejects an external plugin for lacking a declarative manifest. All four plugin types are supported:

```
                  ┌─────────────────────────────────────────┐
                  │    Plugin Installation (ziro plugin)    │
                  └────────────────────┬────────────────────┘
                                       │
                         Has ziro-plugin.toml on disk?
                                       │
                      ┌────────────────┴────────────────┐
                      ▼                                 ▼
              [ YES: Type A ]                    [ NO: Type B/C ]
              Native Manifest                   Static Analyzer
              Full metadata                     Heuristic inference
                      │                                 │
                      └────────────────┬────────────────┘
                                       │
                                       ▼
                       Synthesized into load.toml
                                       │
                                       ▼
                   Pre-Compiled into ziro-boot.zsh.zwc
```

- **Type A (Ziro-Native)**: Contains `ziro-plugin.toml` at repository root. Declares exact lifecycle stages, version constraints, health checks, and exposed resources.
- **Type B (Standard Zsh Plugin)**: Community plugins (e.g., `zsh-users/zsh-autosuggestions`, `romkatv/powerlevel10k`). Layer 1 static analyzer extracts capabilities via regex/AST heuristics.
- **Type C (Local Plugin)**: User scripts or internal dotfiles. Analyzed and managed identically to Type B.
- **Type D (External Binary)**: Standalone executables managed via `tools_factory.toml` (e.g., `starship`, `fzf`, `zoxide`, `eza`).

---

## 3. The `ziro-plugin.toml` Manifest Specification

When present, `ziro-plugin.toml` provides authoritative metadata:

```toml
[plugin]
name = "ziro-ghost"
version = "1.0.3"
description = "IDE-like asynchronous autocompletion for Zsh"
authors = ["Pakrohk"]
license = "MIT"
repository = "https://github.com/Pakrohk/ziro-ghost"

[plugin.compat]
ziro = ">=1.1.0,<2.0.0"
zsh = ">=5.8"
os = ["linux", "macos", "wsl"]

[load]
main = "ghost.plugin.zsh"

[[load.stages]]
id = 0
name = "bootstrap"
trigger = "startup"
budget_ms = 1
files = ["core/bootstrap.zsh"]

[[load.stages]]
id = 5
name = "post-prompt"
trigger = "after-prompt"
budget_ms = 10
files = ["core/ghost-core.zsh", "sources/history.zsh"]

[[load.stages]]
id = 7
name = "popup-widget"
trigger = "on-key:^G"
budget_ms = 30
files = ["ui/popup.zsh"]

[depends]
plugins = [
  { name = "ziro-defer", version = ">=2.0.0", required = true }
]
external = [
  { name = "fzf", required = false, purpose = "fuzzy menu selection" }
]

[provides]
sources = ["history", "zoxide", "typo"]
keybindings = { popup = "^G" }

[[health_checks]]
name = "ghost-zle-active"
command = "(( $+functions[_ghost_init] ))"
description = "Ghost ZLE interceptor is loaded"
required = true
```

---

## 4. Static Analysis: Extracting Metadata Without Execution

For Type B and C plugins lacking a manifest, Layer 1 parses source files statically without executing code:

| Pattern | Detection Regular Expression | Inferred Intent | Scheduled Tier |
|---|---|---|:---:|
| `#compdef` | `^\s*#?compdef\b` | Injects completions into `$fpath` | Stage 2 (Eager) |
| Prompt | `^\s*(PROMPT\|PS1\|RPROMPT)\s*=` | Defines prompt visuals | Stage 4 (Eager) |
| Custom ZLE | `^\s*zle\s+-N\s+` | Registers interactive line editor widgets | Stage 5 (Deferred) |
| Hooks | `add-zsh-hook\s+([a-z_]+)` | Hooks into `precmd`, `chpwd`, or `preexec` | Stage 5 (Deferred) |
| Aliases | `^\s*alias\s+` | Defines command aliases | Stage 5 (Slot `c`) |
| Commands | Dynamic binary wrapper detection | On-demand proxy interception | Stage 7 (On-Demand) |

Static extraction guarantees that untrusted plugins cannot execute arbitrary code during installation or analysis.

---

## 5. Build-Time Synthesis: Eliminating Runtime Discovery

Traditional plugin managers discover plugin files on every interactive shell launch via directory globs, string searches, and repeated `source` commands.

Ziro eliminates all runtime discovery through build-time synthesis (`ziro sync`):

1. **Manifest Consolidation**: `ziro analyze` resolves Type A manifests and Type B heuristic outputs into the single declarative state file `~/.config/ziro/load.toml`.
2. **Flattening Pipeline**: `core/build.py` resolves all file paths, inlines the 10 eager `ziro-defer` modules, renders on-demand un-stubbing proxies, and outputs a single flattened shell script: `~/.cache/ziro/ziro-boot.zsh`.
3. **Bytecode Compilation**: The synthesized script and eager dependencies are compiled to `.zwc` bytecode via `zcompile -U -M`.
4. **Runtime Zero-Discovery**: When the shell launches, Layer 0 sources the pre-compiled file directly. The shell performs **0 directory scans, 0 file searches, and 0 forks**. All lifecycle decisions have already been resolved at build time.
