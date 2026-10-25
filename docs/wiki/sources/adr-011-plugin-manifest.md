---
title: ADR-011 — Optional Plugin Manifest Format
tags: [adr, manifest, plugins, architecture]
sourceRefs: ["/home/ali/.ziro/.specify/decisions/ADR-011-plugin-manifest.md"]
lastReviewed: 2026-10-16
---

# ADR-011: Optional Plugin Manifest Format

**Status**: Adopted
**Date**: 2026-10-16
**Deciders**: Project maintainer
**Relates to**: ADR-007 (versioning), ADR-008 (per-plugin repos), spec 001 (analyzer), spec 011 (zsh optimization), spec 012 (this manifest)

## Context

Currently, ziro plugins (ghost, future pf, helpers) have:
- Version duplicated in every file header (bug: stale versions)
- No declarative way to express load staging
- No standard for ziro-native plugins

Python has `pyproject.toml` for packages. Zsh plugins lack a
standardized equivalent. However, ziro MUST remain compatible
with the vast ecosystem of standard zsh plugins
(zsh-autosuggestions, ohmyzsh, fast-syntax-highlighting, ...) —
none of which have any manifest.

## Decision

Adopt an **OPTIONAL** plugin manifest format: **`ziro-plugin.toml`**
at the plugin repository root.

### Key principles

1. **Manifest is OPTIONAL** — ziro never rejects a plugin for missing manifest
2. **Progressive enhancement** — plugins with manifest get more features
3. **Analyzer fallback** — plugins without manifest work via analyzer (spec 001)
4. **Single source of truth** — version, name, description live here only (when present)
5. **Declarative staged loading** — no more hardcoded source() in .zsh (when present)

### Plugin taxonomy

- **Type A — Ziro-native**: has `ziro-plugin.toml` → full features
- **Type B — Standard zsh plugin**: no manifest → analyzer determines strategy
- **Type C — Local plugin**: no manifest (user-defined) → analyzer + user tags
- **Type D — External binary**: not a zsh plugin → tools_factory entries (existing)

**All four types work in ziro.** The manifest only matters for Type A.

### Optional sections

All manifest sections are OPTIONAL:

- `[plugin]` — identity (strongly recommended for ziro-native)
- `[plugin.compat]` — ziro/zsh/os requirements
- `[load]` — entry point + staged loading
- `[depends]` — dependencies
- `[provides]` — exposed resources
- `[config]` — config file location
- `[[health_checks]]` — doctor integration

## Consequences

### Positive
- Version single source of truth (when manifest present)
- Staged loading is declarative (when manifest present)
- `ziro doctor` can validate ziro-native plugins
- `ziro plugin add` can check compat automatically (when declared)
- **Zero impact on external plugins** — they work as before
- **Zero impact on standard zsh ecosystem** — zsh-autosuggestions, ohmyzsh all work

### Negative
- Need to define schema carefully
- Need to support both modes (manifest / analyzer)
- Documentation must clearly state "optional"

### Migration
- **Never forced** — external plugins continue unchanged
- **Opt-in for ziro-native** — ghost v1.0.3 can add manifest; pf from v0.1.0

## References
- Python: `pyproject.toml` (PEP 621)
- Rust: `Cargo.toml`
- Zsh plugins: currently no standard
- Ziro analyzer: spec 001 (fallback for no-manifest plugins)
