# Spec 009: Ziro Ghost — Standalone Autosuggest & Autocomplete Plugin

**Status**: Draft (Approved for v1.1.3 Implementation)  
**Date**: 2026-10-16  
**Spec ID**: 009  
**Parent Spec**: `000-architecture` (Layer 3 Plugin)  
**Target Version**: `v1.1.3` (Phase 8)  
**Repository**: `https://github.com/Pakrohk/ziro-ghost`  
**Relates to**: Constitution Principle XIV (Plugin Sovereignty), ADR-006, ADR-008, ADR-009 (Adopted)  

---

## 1. Overview & Vision

Ziro Ghost is a sovereign, high-performance Zsh autosuggestion and autocomplete plugin providing an IDE-like developer experience in the terminal.

Ghost delivers two complementary interaction layers:
1. **Inline Ghost Text (`POSTDISPLAY`)**: Zero-latency ghost completions rendered directly inline from history, project context, and fuzzy matching.
2. **Interactive Popup Menu (Tab Navigation)**: Floating candidate browser modeled after modern IDE completion systems (nvim-cmp, VS Code) with semantic icons, documentation previews, and multi-source ranking.

---

## 2. Core Clarifications (v0.2.0 Specifications)

### R11 — IDE-like Autocomplete
- Inline ghost text (`POSTDISPLAY`).
- Popup candidate menu with Tab navigation.
- Semantic item kinds and icons (`git`, `cmd`, `var`, `path`, `alias`).
- Preview pane showing usage frequency, origin source, and descriptions.
- Documentation preview window for man pages and help summaries.
- Customizable borders, layout, and theme highlight groups.

### R12 — Project-Aware Suggestions
Contextual command injection based on root repository markers:
- `pyproject.toml` → `uv sync`, `uv add`, `pytest`, `ruff check`, `mypy`
- `package.json` → `pnpm`, `npm`, `yarn` script targets
- `Cargo.toml` → `cargo build`, `cargo test`, `cargo clippy`
- `go.mod` → `go build`, `go test ./...`
- `Makefile` / `justfile` → Target recipes
- `docker-compose.yml` / `Dockerfile` → Container lifecycles
- `.git/` → Version control workflows
- Extensible via custom markers in `ghost.conf`.

### R13 — Popup Menu with Tab Navigation
- `Tab` / `S-Tab`: Bidirectional navigation through candidates.
- `Enter`: Confirm selection.
- `C-e`: Cancel popup menu without modifying buffer.
- `C-d` / `C-u`: Scroll documentation window.
- `Right` / `C-Right`: Partial or full completion acceptance.
- Fully remappable keybindings.

### R14 — Multi-Source Suggestion Engine
Aggregated candidate ranking based on weighted origins:
- `history` (weight 40): Shell history
- `project` (weight 30): Active project targets
- `tags` (weight 20): Tagged commands catalog
- `zsh-completions` (weight 10): Standard compdef candidates
- `aliases` (weight 5): Shell alias table
- `files` (weight 5, optional): Local filesystem paths
- `env-vars` (weight 3, optional): Environment variables

### R15 — Subcommand Support
Deep hierarchical subcommand suggestions (e.g. `git <Tab>`, `docker <Tab>`, `uv <Tab>`) parsed and cached from system completion definitions.

### R16 — zsh-completions Integration
Seamless coexistence with standard Zsh completion without collision or double-wrapping.

### R17 — Custom Source API
Public configuration (`[[sources]]` in `ghost.conf`) and shell hook (`_ghost_register_source`) for user-defined suggestion scripts.

### R18 — Typo Correction
Intelligent correction of mistyped commands (`sdu` → `sudo`, `gti` → `git`, `pythno` → `python`) powered by Levenshtein distance ($\le 2$), transposition checks, and keyboard layout scoring.
