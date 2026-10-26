# Plugin Authoring Guide

This guide details how to build and package plugins for the `ziro-shell` ecosystem. It covers the `ziro-plugin.toml` manifest specification, analyzer classification heuristics, trust scoring systems, local testing workflows, and publication requirements.

---

## Plugin Architecture in Ziro

Ziro supports four categories of plugins:
- **Type A (Ziro-Native)**: Contains a `ziro-plugin.toml` manifest. Unlocks explicit scheduling tiers, dependency constraints, and health verification.
- **Type B (Standard Community Zsh Plugin)**: Standard GitHub repository containing `.plugin.zsh` or `.zsh` files. Analyzed automatically using AST heuristics.
- **Type C (Local Plugin)**: In-tree or personal scripts referenced via filesystem paths.
- **Type D (External Binary)**: Standalone CLI tools managed through `tools_factory.toml` and eval caches.

**Core Invariant**: Ziro never rejects a plugin for omitting a manifest. A manifest simply guarantees optimal scheduling without relying on heuristic inference.

---

## The `ziro-plugin.toml` Manifest Specification

Native Ziro plugins place a `ziro-plugin.toml` manifest at the repository root. All sections and fields are optional, but defining them provides deterministic loading behavior.

### Manifest Schema Reference

```toml
# ziro-plugin.toml — Plugin Manifest Specification

[plugin]
name = "ziro-ghost"
version = "1.0.3"
category = "completion"
description = "High-performance ghost-text autosuggestions for Zsh"
authors = ["Pakrohk"]
license = "MIT"
repository = "https://github.com/Pakrohk/ziro-ghost"
keywords = ["autosuggestions", "completion", "zle"]

[plugin.compat]
ziro = ">=1.2.0"
zsh = ">=5.8"
os = ["linux", "macos"]

[dependencies]
requires = []
conflicts = ["zsh-users/zsh-autosuggestions"]
recommends = ["zdharma-continuum/fast-syntax-highlighting"]

[load]
main = "ziro-ghost.plugin.zsh"
timing = "deferred"
stage = 5
slot = "b"

[[hints]]
type = "bindkey"
target = "^F"
description = "Accept full ghost suggestion"

[[hints]]
type = "zle_widget"
target = "ghost-autosuggest-accept"
description = "Internal ZLE widget"

[[hints]]
type = "precmd"
target = "_ziro_ghost_precmd"
description = "Post-command buffer cleanup"

[health]
check_command = "_ziro_ghost_check_status"
expected_status = 0
```

### Table Definitions

#### 1. `[plugin]` Table
- `name` (string, required): Kebab-case identifier matching the repository or tool name.
- `version` (semver string, required): Semantic version (`MAJOR.MINOR.PATCH`). Single source of truth.
- `category` (string, optional): One of `"prompt"`, `"completion"`, `"highlighting"`, `"tool"`, or `"utility"`.
- `description` (string, required): Concise explanation of functionality.
- `authors` (list[string], optional): Author names or handles.
- `license` (string, required): Valid SPDX license identifier (e.g. `"MIT"`, `"Apache-2.0"`).

#### 2. `[[hints]]` Table
Hints allow plugin authors to explicitly declare shell capabilities without forcing the analyzer to parse raw shell code:
- `type` (enum, required): `"bindkey"`, `"precmd"`, `"compdef"`, `"alias"`, or `"function"`.
- `target` (string, required): The specific key sequence, hook name, completion tag, alias, or function symbol.
- `description` (string, optional): Contextual note for auditing.

#### 3. `[dependencies]` Table
- `requires` (list[string]): Repository slugs or tool names that must load before this plugin.
- `conflicts` (list[string]): Incompatible plugins. Ziro will disable or warn when conflicting entries appear.
- `recommends` (list[string]): Complementary plugins.

#### 4. `[load]` Table
- `main` (string): Entrypoint script relative to repo root.
- `timing` (enum): Default timing strategy (`"eager"`, `"deferred"`, `"on-demand"`).
- `stage` (int): Deferred stage (`1` through `7`). Defaults to `5`.
- `slot` (string): Execution slot (`"a"`, `"b"`, or `"c"`). Defaults to `"b"`.

---

## Analyzer Classification Heuristics

When a plugin does **not** provide a `ziro-plugin.toml` manifest, Ziro's analyzer (`core/analyzer.py`) inspects the source code using regex pattern matching and structural signals:

```
Source Code Inspection -> Signal Extraction -> Tier Assignment
```

### Signal Extraction Rules

1. **Path Modifications (`modifies_path`)**:
   Matches `PATH=...`, `path+=(...)`, `export PATH`.
   *Action*: Promoted to `eager` (Order 1–2).
2. **Prompts & Themes (`is_prompt`)**:
   Matches `PROMPT=`, `RPROMPT=`, `starship init`, `p10k`.
   *Action*: Promoted to `eager` (Order 4, eval-cache).
3. **Completions (`compdef`)**:
   Matches `compdef `, `compctl`, `_arguments`.
   *Action*: Promoted to `eager` (Pre-compinit stage 2).
4. **Keybindings & Interactive Widgets (`zle_widgets`, `bindkey`)**:
   Matches `zle -N`, `bindkey -M`.
   *Action*: Assigned to `on-demand` triggered by key (`trigger = "key"`).
5. **CLI Wrapper Functions**:
   Matches exported functions matching binary names.
   *Action*: Assigned to `on-demand` triggered by command (`trigger = "command"`).
6. **Shell Lifecycle Hooks (`precmd`, `preexec`, `chpwd`)**:
   Matches `add-zsh-hook precmd`, `preexec_functions+=`.
   *Action*: Assigned to `deferred` (Stage 5, slot `b`).
7. **Safe Default**:
   Any plugin with unclassified behavior defaults safely to `deferred` Stage 5, slot `b`.

Providing a `ziro-plugin.toml` bypasses heuristic guessing and eliminates cold analysis overhead.

---

## Trust Scoring & Security Verification

Ziro implements an automated security scoring matrix (`core/analyzer.py`) to guard against unvetted or malicious shell extensions.

### Trust Score Signals (0 to 4 Scale)

Each positive signal adds 1 point to the trust score:
1. **`known_org`**: Repository resides in an approved organization or verified namespace (e.g. `zsh-users`, `zdharma-continuum`, `Pakrohk`, `ohmyzsh`).
2. **`has_release_tag`**: Repository contains structured git semver release tags (`vX.Y.Z`) rather than floating on untagged commit SHAs.
3. **`recent_activity`**: Upstream repository has recorded commit activity within the past 24 months.
4. **`source_clean`**: Source inspection confirms absence of obfuscated strings, dynamic base64 decoders (`base64 -d`), hidden curl pipelines (`curl | sh`), or unquoted `eval` on network variables.

### Trust Levels & Scheduling Decisions

| Trust Score | Trust Level | Scheduling Impact |
| :---: | :---: | :--- |
| **3 – 4** | `high` | Executes as recommended by performance heuristics (eager or deferred). |
| **2** | `medium` | Permitted, but generates warning in `ziro doctor`. |
| **0 – 1** | `low` | Downgraded to `deferred`. Eager execution blocked unless explicitly overridden. |
| **N/A** | `unknown` | If suspicious patterns are present, execution is blocked until approved in `[user]`. |

---

## Local Testing Workflow

Test your plugin locally inside Ziro before publishing:

### 1. Link or Add Local Directory

Add your local working copy using `--path`:

```bash
# Add your local repository directory
ziro plugin add --path ~/Projects/my-ziro-plugin

# Or specify custom lazy triggers during development
ziro plugin add --path ~/Projects/my-ziro-plugin --lazy=command:mycmd
```

### 2. Inspect Manifest and Heuristics

Verify how Ziro classifies your plugin:

```bash
# Show analysis, signals, and security trust score
ziro plugin show my-ziro-plugin

# Check environment health
ziro doctor
```

### 3. Synchronize and Test In-Shell

Compile artifacts and verify startup performance:

```bash
# Rebuild ziro-boot.zwc
ziro sync

# Launch a clean shell and verify command execution
zsh -i -c "mycmd --version"
```

---

## Publishing Checklist

Before tagging and publishing your plugin for the Ziro ecosystem:

- [ ] **Manifest Valid**: `ziro-plugin.toml` placed at repository root and validates with `tomllib`.
- [ ] **Plugin Sovereignty**: Plugin must remain functional if sourced in pure Zsh without Ziro present (Constitution Principle XIV). Never assume `ziro` binary exists at runtime.
- [ ] **No Shell Forks**: No `$(...)` subshells executed during the top-level script body. Store state via Zsh parameter expansion.
- [ ] **Zsh Idioms**: Follow idiom-first guidelines:
  - Guard paths: `[[ -f "$file" ]] || return 0`
  - Fallbacks: `${VAR:-default}` instead of multi-line `if` checks.
  - Suffix/prefix removal via native parameter expansion (`${var#prefix}`).
- [ ] **Semver Git Tag**: Git tag applied matching `version` declared in `ziro-plugin.toml` (e.g. `git tag -a v1.0.0 -m "Release v1.0.0"`).
- [ ] **Clean Code**: Zero obfuscated strings, zero dynamic curl executions.
