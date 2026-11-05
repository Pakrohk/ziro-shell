# SPEC-026: Ziro-Ghost Modularity & Capability Decomposition

- **Status**: Draft / In-Progress
- **Date**: 2026-11-04
- **Version**: 1.0.0
- **Authors**: Ziro Core Team & Community
- **Target Release**: `ziro-ghost v2.1.0` / `ziro-shell v1.4.0`
- **Cross-Spec**: Depends on and fulfills `SPEC-025` (§2.3, §2.4)

---

## 1. Executive Summary & Problem Statement

### 1.1 The Problem

Ziro-Ghost v2.0.1 is architecturally monolithic in its Zsh loading path. Loading `ghost-v2-line` (the intent-bus + history-source module) unconditionally drags in four additional capabilities that are neither needed at first prompt nor related to line suggestion:

| Capability | Currently loaded when | Cost (bench v2.1) | Actually needed when |
|---|---|---|---|
| `ghost-popup-cli` | ghost-line loads | 2.72 ms | User presses Tab with POSTDISPLAY set |
| `ghost-focus` | ghost-line loads (bundled inside ghost-core.zsh) | hidden inside ghost-line cost | User presses Tab |
| `ghost-warmup` | ghost-line loads (unconditional spawn) | 246.53 ms (!!) | Never during boot — it's a background service |
| `ghost-tab-wrapper` | After all stage-5 sources | 0.14 ms | First Tab press |

Evidence from bench v2.1 (see attached run): the `ghost-warmup` cost of 246.53 ms alone exceeds the entire target startup budget (8 ms) by 30x. This warm-up is a **service-shaped capability** that must not appear in the boot path at all.

### 1.2 The User's Diagnosis (verbatim)

> "I think ghost itself should be written modularly and each part should be a very small accessible module. For example, dynamic UI builder or any other part should be separate sub-modules. Its architecture is completely broken — for example when ghost-line loads, why should ghost-popup or ghost-warmup or ghost-focus also load at that moment?"

This spec formalizes that diagnosis into a target architecture.

### 1.3 The Solution

Decompose ghost into N independent capabilities, each with its own loading trigger:

- **ghost-core** (bus + intent vocabulary): eager, minimal (< 1 ms). Only shim definitions.
- **ghost-line** (history source + suggestion engine): deferred S5:b. No side effects on other capabilities.
- **ghost-popup** (Rust binary invocation): on-demand — spawned only when `POSTDISPLAY` set AND Tab pressed.
- **ghost-focus** (Tab widget): on-demand — bound as widget reference, real body lazy-loaded.
- **ghost-warmup** (background prefetch): service — spawned by dedicated daemon, NOT by shell boot. Zero boot cost.
- **ghost-ui** (Rust ratatui builder): compiled binary, zero Zsh load surface.

Each capability has its own manifest entry in `ziro-plugin.toml` (per SPEC-012). Loading one MUST NOT trigger any other.

---

## 2. Target Architecture — Capability-Per-Module

### 2.1 Capability Independence Rule

**Rule G1**: For any two ghost capabilities A and B, loading A MUST NOT cause B's source code to be sourced, evaluated, or spawned.

**Rule G2**: Each capability's loading path must be instrumented with a per-capability marker (`_ZIRO_GHOST_<CAP>_LOADED=1`). `ziro bench --plugin ghost-<cap> --capabilities` must report only the capabilities actually loaded.

**Rule G3**: All shared state between capabilities (bus, cache files, socket paths) must be established by `ghost-core` alone. No capability may assume another capability has initialized shared state.

**Rule G4**: Service capabilities (`ghost-warmup`) must be able to run without any interactive shell present. Cold-path fallback (skip warm-up, load source directly) must be automatic.

### 2.2 Target Capability Map

```toml
[[plugin]]
name = "ziro-ghost"
version = "2.1.0"

[[plugin.capability]]
name = "ghost-core"
type = "bus"
strategy = "eager"
shimmable = false
est_cost_ms = 0.8
reason = "Intent vocabulary + bus skeleton; other capabilities depend on it"

[[plugin.capability]]
name = "ghost-line"
type = "suggestion-source"
strategy = "deferred-s5"
shimmable = true
est_cost_ms = 8.0
reason = "History source + engine; deferred to stage 5, no UI dependency"

[[plugin.capability]]
name = "ghost-popup"
type = "rust-binary-invoke"
strategy = "on-demand"
trigger = "key:^I+POSTDISPLAY"
shimmable = true
est_cost_ms = 0.1
reason = "Only spawned when popup requested; not at load"

[[plugin.capability]]
name = "ghost-focus"
type = "zle-widget"
strategy = "on-demand"
trigger = "key:^I"
shimmable = true
est_cost_ms = 0.05
reason = "Tab widget stub; real body lazy"

[[plugin.capability]]
name = "ghost-warmup"
type = "service"
strategy = "background-service"
service = "ziro-ghost-warmup"
socket = "~/.cache/ziro/ghost/warmup.sock"
shimmable = false
est_cost_ms = 0.0
reason = "Never in boot path; daemon maintains warm state"

[[plugin.capability]]
name = "ghost-ui"
type = "rust-binary"
strategy = "compiled-artifact"
shimmable = false
est_cost_ms = 0.0
reason = "Rust binary; no Zsh load surface"
```

### 2.3 Loading Chain (Target)

```
boot.zsh (7 lines)
  └─> ghost-core (eager, 0.8ms)        ← only shim + intent vocabulary
        ├─ ghost-line deferred S5:b     ← fires on precmd, ~8ms
        ├─ ghost-focus on-demand        ← binds widget, 0.05ms
        ├─ ghost-popup on-demand        ← called by focus widget
        └─ ghost-warmup service          ← connects to socket, 0ms if daemon up

First Tab press:
  ghost-focus → POSTDISPLAY? yes → ghost-popup (spawn binary) → render
  ghost-focus → POSTDISPLAY? no  → fzf-tab fallback
```

---

## 3. Milestones

### Phase 1 — Ghost Repo Refactor (ziro-ghost repo)
- [ ] **M01**: Split `core/ghost-core.zsh` into `core/bus.zsh`, `core/intent.zsh`, `core/cache.zsh` — ghost-core becomes pure definition, no side effects.
- [ ] **M02**: Extract `ghost-line` source to `modules/line/` — history source, suggestion engine, no UI, no popup, no warmup.
- [ ] **M03**: Extract `ghost-popup` invocation to `modules/popup/` — a function `<cap>_invoke` with zero side effects until called.
- [ ] **M04**: Extract `ghost-focus` Tab widget to `modules/focus/` — bind to stub, lazy-load real body on first press.
- [ ] **M05**: Extract `ghost-warmup` to a standalone service binary + systemd unit emitter — never in shell boot path.
- [ ] **M06**: Emit `ziro-plugin.toml` manifest with per-capability entries (SPEC-012 format).

### Phase 2 — ziro-shell Integration (this repo)
- [ ] **M07**: Update `core/tools_factory.toml` — replace single `ghost-v2-line` + `ghost-v2-focus` entries with 6 capability entries.
- [ ] **M08**: Update `core/build.py` — emit each ghost capability as its own tool line with correct strategy.
- [ ] **M09**: Update `ziro mcp` ghost tools — proxy calls resolve capability by name, not by monolithic ghost.
- [ ] **M10**: Update `ziro doctor` — new check `_check_ghost_capabilities` verifies independence.

### Phase 3 — Verification
- [ ] **M11**: `ziro bench --plugin ziro-ghost --capabilities` reports 6 distinct capabilities with per-capability cost. No capability exceeds its declared `est_cost_ms` by > 2x.
- [ ] **M12**: Independence test suite: for each capability pair (A, B), loading A must not set `_ZIRO_GHOST_B_LOADED`.

### Phase 4 — Release
- [ ] **M13**: Version bump ziro-ghost v2.0.1 → v2.1.0.
- [ ] **M14**: Version bump ziro-shell v1.3.2 → v1.4.0 (depends on SPEC-025 completion).
- [ ] **M15**: Release manifest + GitHub Release.

---

## 4. Cross-Repo Contract with SPEC-025

SPEC-025 (Modular Defer Engine & Behavior-Driven Plugin Analyzer) provides the **capability axis** in ziro-shell's analyzer. This spec (SPEC-026) provides the **capability axis** in ziro-ghost's plugin implementation.

### Dependency Chain

SPEC-026 cannot ship without SPEC-025's capability-aware analyzer:
- SPEC-025 §2.3 (capability taxonomy) must recognize all 6 ghost capability types.
- SPEC-025 M08 (behavioral decision tree) must correctly assign each ghost capability to its target strategy.
- SPEC-025 M09 (lazy hook & registration shim generator) must be able to generate shims for ghost-focus and ghost-popup.

SPEC-025 cannot deliver its acceptance criteria without SPEC-026:
- SPEC-025 AC#5 (capability-level verification) requires ghost to expose per-capability boundaries.
- SPEC-025's 'at least 5 eager hotspots decomposed' — ghost-warmup (246.53 ms) is the biggest hotspot and cannot be decomposed without SPEC-026.

### Interface Contract

| SPEC-025 requires | SPEC-026 provides |
|---|---|
| Per-capability cost attribution | Each ghost capability emits `_ZIRO_GHOST_<CAP>_LOADED` + `_ZIRO_GHOST_<CAP>_COST_MS` |
| Shim-ability flag per capability | Manifest declares `shimmable: true/false` per capability |
| Service candidate signals | `ghost-warmup` declares `strategy: background-service` + socket path |
| Independence verification | Per-capability load markers, no cross-trigger |

### Sequencing

SPEC-026 (ghost refactor) is a **hard prerequisite** for the 'capability decomposition' part of SPEC-025. Recommended order:
1. Merge SPEC-026 spec (this document)
2. Merge SPEC-025 capability-axis patch
3. Implement ziro-ghost M01-M06
4. Implement ziro-shell SPEC-025 M01-M05 (defer decomposition)
5. Wire ghost capabilities into SPEC-025 analyzer (M06-M10)
6. Release ziro-ghost v2.1.0
7. Release ziro-shell v1.4.0 with both

**SPEC-025 milestone ordering does NOT change** — M01/M02 can still begin (defer decomposition is orthogonal). But M06-M10 (behavior analyzer) block on ghost refactor completing.

---

## 5. Success Criteria

1. **Independence**: Loading any one ghost capability does NOT set `_ZIRO_GHOST_<other>_LOADED` for any other capability. Test matrix: 6×5 = 30 pair checks.
2. **Boot cost**: Total ghost boot cost (all capabilities that load at startup) < 2.0 ms.
3. **Warmup**: `ghost-warmup` appears with cost 0.0 ms in `ziro bench` when service daemon is running; appears as 'not in boot path' when daemon absent.
4. **Popup on-demand**: `ghost-popup` does not appear in `ziro bench` boot cost table at all — it's on-demand.
5. **Focus binding**: `ghost-focus` binds Tab in < 0.1 ms. First Tab press triggers popup path in < 5 ms.
6. **Regression**: All existing ghost tests (ziro-ghost repo) pass. All existing ziro-shell tests pass (675+).
7. **Tab behavior preserved**: ghost popup appears on Tab with POSTDISPLAY set; fzf-tab fallback on empty POSTDISPLAY (per ADL-041).

---

## 6. Out of Scope

- Rewriting Rust ghost-popup binary — capability split happens at Zsh boundary, Rust binary unchanged.
- Changing user-facing CLI — `ghost` commands behave identically.
- Modifying MCP protocol — MCP tools still proxy to ghost capabilities, only resolution changes.
- SPEC-025 implementation — this spec defines dependency, does not implement M01-M05 of SPEC-025.


## 7. Cross-Repo Dependency — SPEC-027

ziro-ghost v2.1.0's capability decomposition MUST follow the contract defined in SPEC-027. Ghost is the canonical first consumer of SPEC-027 — its 6 capabilities (ghost-core, ghost-line, ghost-popup, ghost-focus, ghost-warmup, ghost-ui) serve as the reference implementation.

**Revision history**: 2026-11-04 — Added cross-reference to SPEC-027.


## 8. Ghost UI & Tagging Fixes (from v1.3.2 User Audit)

During the audit of Ghost v2.0.1, the following UI and tagging bugs were identified. These MUST be resolved in Ghost v2.1.0 (SPEC-026) as part of the capability decomposition.

### 8.1. Path-Bearing Command Tagging Bug
- **Symptom**: In the Ghost Cmp popup, bare system commands like `cd`, `z`, and `pushd` are incorrectly tagged as `path` (folder icon).
- **Root Cause**: The `history.source.zsh` and `path.source.zsh` lack command-context awareness. They tokenize the buffer and misclassify bare commands that typically accept paths as the paths themselves.
- **Fix Requirement (Capability: `ghost-tokenizer`)**: Introduce a `ghost-tokenizer` capability that knows the difference between `command` and `path-context`. If the buffer is `cd `, suggest paths. If the buffer is `cd` (no space), suggest the command `cd` with a `command` tag, NOT `path`.

### 8.2. Missing UI Colors (Ratatui Theme)
- **Symptom**: The Rust popup UI is monochromatic. No visual distinction between history items (`hist`), path items (`path`), and the selected item.
- **Root Cause**: `ghost-popup` Rust binary uses `ratatui` but lacks a theme configuration parser. Hardcoded default styles are plain.
- **Fix Requirement (Capability: `ghost-ui`)**: Implement a theme config in `ziro-plugin.toml` (e.g., `[ui.theme]` with color hex codes for `hist`, `path`, `selected`). The Rust binary must parse this and apply colors.

### 8.3. Configurable Display Limits
- **Symptom**: The popup shows a fixed number of items (e.g., `1/5`), with no user control.
- **Root Cause**: Hardcoded limits in the Rust UI.
- **Fix Requirement (Capability: `ghost-ui`)**: Add `ui.max_items` and `ui.page_size` to `ziro-plugin.toml`. Allow `ghost-popup` to respect these settings.

### 8.4. Updated Milestones for SPEC-026
- **M03a (New)**: Add `ghost-tokenizer` capability to correctly classify commands vs paths.
- **M04a (New)**: Implement theme and layout config parsing in `ghost-popup` Rust binary.
- **M06a (New)**: Update `ziro-plugin.toml` schema (per SPEC-027) to include `[ui.theme]` and `[ui.limits]` blocks.


