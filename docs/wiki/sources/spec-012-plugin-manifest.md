---
title: Spec 012 — Optional Ziro Plugin Manifest Format
tags: [spec, manifest, plugins, architecture, tools]
sourceRefs: ["/home/ali/.ziro/.specify/specs/012-plugin-manifest/spec.md"]
lastReviewed: 2026-10-16
---

# Spec 012: Optional Ziro Plugin Manifest Format

**Spec ID**: 012  
**Parent Spec**: `000-architecture`  
**Related ADRs**: ADR-007 (versioning), ADR-008 (per-plugin repos), ADR-011 (this manifest)  
**Target Version**: v1.1.4 (or v1.2.0 depending on priority)  

---

## 1. Overview & Purpose

Spec 012 defines a standardized **OPTIONAL** manifest file (`ziro-plugin.toml`) located at the root of a plugin repository. When provided, it unlocks progressive enhancements:
- Single source of truth for plugin version, name, and author metadata.
- Declarative staged loading (e.g. startup, on-first-keystroke, after-prompt, keybindings).
- Compatibility bounds checking (`ziro`, `zsh`, OS platforms).
- Native diagnostic hooks for `ziro doctor`.

**Core Principle**: Ziro MUST NEVER reject a plugin for lacking a manifest. External and standard Zsh plugins (Type B/C) continue to be analyzed dynamically via the static analyzer (Spec 001) without any regression.

---

## 2. Plugin Taxonomy

| Type | Classification | Manifest Status | Resolution Strategy | Examples |
|---|---|:---:|---|---|
| **Type A** | Ziro-native | Present (`ziro-plugin.toml`) | Declarative schema, staged loading, compat check, health checks | `ziro-ghost`, `ziro-pf`, `ziro-helpers` |
| **Type B** | Standard Zsh plugin | Absent | Static Analyzer (Spec 001) signal detection + user tags | `zsh-autosuggestions`, `fast-syntax-highlighting` |
| **Type C** | Local script/plugin | Absent | Static Analyzer + path loader + user tags | User scripts, dotfile helpers |
| **Type D** | External CLI binary | N/A | `tools_factory.toml` configuration entries | `starship`, `fzf`, `zoxide` |

---

## 3. Manifest Schema Summary

All sections and fields in `ziro-plugin.toml` are OPTIONAL:

### `[plugin]` — Identity
Defines plugin name, semver version, description, license, and repository.

```toml
[plugin]
name = "ziro-ghost"
version = "1.0.2"
description = "IDE-like autocomplete for Zsh"
authors = ["Pakrohk"]
license = "MIT"
repository = "https://github.com/Pakrohk/ziro-ghost"
keywords = ["autocomplete", "suggestions", "zsh"]
```

### `[plugin.compat]` — Constraints
```toml
[plugin.compat]
ziro = ">=1.1.0,<2.0.0"
zsh = ">=5.8"
os = ["linux", "macos", "wsl"]
```

### `[load]` — Declarative Staged Loading
Replaces imperative script sourcing with lifecycle phases:

```toml
[load]
main = "ghost.plugin.zsh"

[[load.stages]]
id = 0
name = "startup"
trigger = "startup"
budget_ms = 1
files = []

[[load.stages]]
id = 1
name = "first-keystroke"
trigger = "on-first-keystroke"
budget_ms = 10
files = ["core/ghost-version.zsh", "core/ghost-kinds.zsh"]

[[load.stages]]
id = 2
name = "background"
trigger = "after-prompt"
files = ["sources/history.source.zsh"]

[[load.stages]]
id = 3
name = "popup"
trigger = "on-key:^G"
files = ["ui/popup.ui.zsh"]
```

### `[depends]`, `[provides]`, `[config]`, and `[[health_checks]]`
- `[depends]`: Declares required or optional plugin and CLI dependencies.
- `[provides]`: Declares exposed sources, commands, and keybindings.
- `[config]`: Points to configuration file paths and schemas.
- `[[health_checks]]`: Supplies native assertions for `ziro doctor --plugins`.

---

## 4. Integration Workflow

1. **`ziro plugin add <source>`**:
   - Clones repo into vendor.
   - Probes root for `ziro-plugin.toml`.
   - If found: validates declared sections, checks compat/deps, registers staged loaders.
   - If not found: executes static analyzer (Spec 001) to infer eager vs deferral strategy.
2. **`ziro doctor --plugins`**:
   - For native plugins: checks compat bounds and runs `[[health_checks]]`.
   - For external plugins: displays inferred strategy and hook status.

---

## 5. Non-Functional & Migration Rules

- **Cold-Path Execution**: Manifest parsing and validation occur only during installation, update, or doctor verification.
- **Zero Hot-Path Cost**: At shell startup, only pre-emitted lines in `plugins.gen.zsh` run (< 5ms budget).
- **Opt-in Migration**: Existing plugins do not require changes. Native plugins adopt manifests progressively (e.g., Ghost v1.0.3+, pf v0.1.0+).
