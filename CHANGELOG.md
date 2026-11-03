# Changelog

All notable changes to ziro-shell are documented here.
This project adheres to a 3-tier versioning discipline (ADR-007):
- **Patch Tier (`X.X.Y`)**: Bug fixes, internal optimizations, UI polish, CLI UX enhancements, and standalone plugin additions.
- **Minor Tier (`X.Y.X`)**: Large new features and full multi-layer subsystem orchestrations.
- **Major Tier (`Y.X.X`)**: Fundamental architecture rewrites or paradigm shifts breaking Core Principles.

## Upcoming

- **v1.4.0** — Release audit, cleanup, and public launch

## [v1.3.0] — 2026-11-03

### Added (Ghost v2.0.1 Integration & AI-Safe MCP Management Layer)
- **Ghost v2.0.1 Integration**:
  - Multi-arch binary automated download with SHA256 verification (`linux-x86_64`, `linux-aarch64`, `darwin-x86_64`, `darwin-arm64`).
  - Declarative tools factory split into `ghost-v2-line` (deferred autosuggestions) and `ghost-v2-focus` (on-demand Tab widget).
  - Doctor observability displays Ghost companion binary version and health.
  - Deprecated `ziro ghost preview` with redirect guidance to `ziro update`.
- **AI-Safe MCP Management Layer (`ziro mcp`)**:
  - Full JSON-RPC 2.0 stdio server providing 16 tools across 5 domain categories.
  - Read-only tools (`ziro.system.*`, `ziro.dir.*`, `ziro.cmd.check`, `ghost.*`, `ziro.*`).
  - Strict safe-mode by default; command execution requires `--allow-execute` plus a two-step 60s ephemeral confirmation token.
  - Comprehensive immutable audit trail logging to `~/.cache/ziro/mcp/audit.jsonl` (mode 0600).
- 47 new tests across server, tools, and integration (total 665+ tests).

### Added (External Tools Observability)
- `ziro stats` — aggregate metrics from any tool at ~/.cache/ziro/<tool>/metrics.jsonl
- `ziro health [tool]` — run health checks (health.json or manifest health_command)
- `ziro doctor` extended with 'external tools' check
- **Protocol v1**: any tool writing metrics.jsonl is auto-discovered, zero integration
- 18+ new tests, 600 → 618 passed

**Note**: ziro-shell v1.2.10 is a small observability release. After this, ziro-shell returns to PAUSE until ghost v2.0.0 released (v1.3.0 = full integration).

**Rollback**: git revert v1.2.10

## [v1.2.9] — 2026-11-02

### Added (Headless & SSH Refinements)
- **OSC 52 clipboard escape** — copy from remote SSH to local terminal clipboard (kitty, WezTerm, Alacritty, Ghostty, iTerm2 with manual enable, tmux with set-clipboard on).
- **4-layer clipboard chain**: GUI native → macOS native → OSC 52 → file buffer.
- **Doctor check**: `headless capabilities` with per-terminal enable guidance (iTerm2, tmux, GNOME Terminal, mintty, Windows Terminal, Apple Terminal.app).
- **open/xdg-open wrappers**: headless text files open via $PAGER; URLs and binaries return clear error.
- **Environment variables**: `ZIRO_CLIPBOARD_VERBOSE`, `ZIRO_OSC52_DA1_DISABLE`, `ZIRO_OSC52_TERM_ALLOWLIST`.

### Preserved
- **GUI user (DISPLAY/WAYLAND): byte-for-byte identical to v1.2.8** (zero overhead).
- All 582 existing tests pass.
- Startup silent for all users.

**Spec**: 023-headless-refinements  
**Tests**: 582 → 603  
**Rollback**: git revert v1.2.9

## [v1.2.8] — 2026-11-02

### Security (Root Profile Hardening)
- **M1 (FZF)**: Root shell blocks execute() bindings in FZF (privilege escalation vector). Override: `ZIRO_ALLOW_ROOT_FZF_EXECUTE=1`.
- **M2 (Clipboard)**: Headless clipboard uses `$XDG_RUNTIME_DIR` (0700/0600) over `/tmp`. 24h cleanup on `/tmp` fallback.
- **M3 (SSH)**: agent-forwarding explicitly off by default. Opt-in: `ZIRO_SSH_FORWARDING=1`.
- **M4 (Starship)**: Root uses isolated `~/.config/ziro/starship-root.toml` (no `[custom]` sections, CVE-2024-41815 mitigation).

### Added
- Doctor check: root profile (Spec 022 R11).
- `tests/test_root_profile.py` (18 unit & integration tests).
- `docs/CONFIGURATION.md`: Root Profile Hardening section.

### Preserved
- **Normal user (EUID!=0) shell behavior: byte-for-byte identical to v1.2.7**.
- All 564 existing tests pass.
- Startup silent for normal user.

**Spec**: 022-root-profile-hardening
**Tests**: 564 → 578+
**Rollback**: git revert v1.2.8

## [v1.2.7] — 2026-11-02

### CI / Infrastructure
- Stabilized GitHub Actions CI matrix across Ubuntu and macOS runners (Spec 021, ADL-035).
- Segmented test suite into 496 hermetic unit tests (`@pytest.mark.unit`) and 68 environment-dependent integration tests (`@pytest.mark.integration`).
- Resolved runner environment discrepancies: user home alignment, XDG env clearing in doctor test fixture, dynamic repository root resolution in build tests, headless Linux display skip for clipboard tests, and resilient zoxide on-demand command proxy function binding.

## [v1.2.6] — 2026-11-01

### Performance
- Zero-lag history architecture: filter on precmd (~0.05ms) instead of on keystroke. Input latency reduced from ~5-10ms → 1-3ms.
- Test suite optimized: 204s → ~90s (55% faster via venv bootstrap skipping and mocked network tests).

### Security
- Ghost history cache sanitization on `ziro sync` (offline batch, ~5ms).
- Doctor check: ghost cache secrets scan (`_check_ghost_cache_secrets`).
- 12 new edge case tests covering Ctrl+C precmd window, `--secret-id`/`--secret-arn`, multi-command lines, and URL-embedded credentials.
- Updated `ziro-ghost` to v1.0.7 for expanded secret options and URL credentials matching.

### Infrastructure
- CI matrix: ubuntu+macos × py3.11-3.13, pip cache, uv, concurrency cancellation.

### Internal
- `test_doctor.py` merged into `test_doctor_comprehensive.py` (legacy module tests).
- `test_zwc_perms.py` made CI-safe (`pytestmark.skipif` when no live cache exists).
- Spec 020 (retroactive) documenting zero-lag architecture.
- ADL-034 registered.

**Spec**: 020-zero-lag-history
**Tests**: 552 → 564+
**Rollback**: git revert v1.2.6

## [v1.2.5] — 2026-11-01

### Security
- **Universal chmod**: All ziro directories (~/.ziro, ~/.config/ziro, ~/.cache/ziro, ~/.local/share/ziro) now created with 700. All files created with 600. Fixes C3 from initial audit where 7+ files created dirs with 755 (spec 018 R1-R7)
- **Boot zwc**: `~/.cache/ziro/ziro-boot.zsh.zwc` now 600 (was 644 — leak since v1.2.0, spec 018 R8)
- **Legacy ghost cache warning**: `ziro doctor` warns if ghost cache predates v1.2.3 (may contain unfiltered secrets). Suggestion to `rm` (spec 018 R10)

### Added
- `_ensure_secure_perms` helper in core/paths.py
- New doctor check: legacy ghost cache (spec 018 R10)
- Extended boot chain check: verifies all dir perms 700, boot zwc 600 (spec 018 R11)
- tests/test_universal_chmod.py (16 tests)

**Spec**: 018-universal-chmod
**Tests**: 533 → 549+
**Rollback**: git revert v1.2.5 (permissions already applied stay applied)

## [v1.2.4] — 2026-11-01

### Added
- **Theme sharing system**: New `ziro theme submit` command shares starship.toml with the ziro community via github.com/Pakrohk/ziro-themes
- Prerequisites check (gh installed, gh auth, starship config exists) before any GitHub operation
- Diff summary vs default config shows what makes your theme unique
- Automatic PR creation with clear title, body, and branch name
- `--dry-run` for preview, `--no-pr` for manual control, `--keep` for debugging
- New doctor check for theme sharing prerequisites (info only, not error)
- Tests: 517 → 533 (16 new in test_theme_submit.py)

### New ecosystem
- github.com/Pakrohk/ziro-themes — community theme gallery with 5 seeded starship presets

**Spec**: 017-theme-sharing
**Rollback**: git revert v1.2.4 (repo ziro-themes remains)

## [v1.2.3] — 2026-10-31

### Security
- **Ghost history cache filter**: `ghost_history_is_sensitive()` filters 10 secret patterns (AWS keys, GitHub/OpenAI/Slack tokens, Bearer/Basic auth headers, MySQL passwords, passphrases, SSH private key headers) before writing to `~/.cache/ziro/ghost/history-cache`. Space-prefixed, >500-char, and 40+ alphanumeric lines are also skipped (spec 016 R1-R4)
- **Cache permissions**: ghost cache file is 600, dir is 700 (spec 016 R5-R6). eval-cache .zwc files are 600, dir is 700 (spec 016 R7-R8). Applied at install, sync, and plugin-add
- **Escape hatch hardening**: `ZIRO_ALLOW_TEST_HOME=1` now only honored when `PYTEST_CURRENT_TEST` is set (spec 016 R9). Prevents accidental production bypass of ZIRO_HOME validation

### Added
- 2 new doctor checks: ghost cache perms, eval-cache perms (25 → 27)
- tests/test_ghost_filter.py (11 tests)
- tests/test_zwc_perms.py (3 tests)
- tests/test_escape_hatch_hardening.py (3 tests)

### Dependencies
- Requires ziro-ghost v1.0.5 (filter + permissions in source)

**Spec**: 016-ghost-filter
**Tests**: 497 → 514+
**Rollback**: git revert to v1.2.2 + `ziro update --checkout v1.0.4` for ghost

## [v1.2.2] — 2026-10-31

### Added
- `_validate_ziro_home()` in core/build.py — rejects temp, nonexistent, and non-ziro paths before baking into boot.zsh (spec 015 R5-R6)
- New doctor check `boot.zsh ZIRO_HOME` verifies consistency (spec 015 R7)
- tests/test_non_interactive_guard.py (~7 tests)
- tests/test_ziro_home_validation.py (~8 tests)

### Fixed
- Interactive-only features (starship, zcolors, precmd/preexec hooks, ZLE keybindings, idle update check) no longer initialize in non-interactive shells like `ssh host 'command'`, cron, and scripts (spec 015 R3, C1)
- Prevents baking temp ZIRO_HOME paths into boot.zsh which would break all future shells (spec 015 R5, N1)

### Preserved
- Interactive shell behavior unchanged — all hooks, starship, zcolors, keybindings work as before
- `ziro` function remains callable in both interactive and non-interactive shells (spec 015 R2)

**Spec**: 015-non-interactive-guard
**Tests**: 481 → 497+ (16 new)

## [v1.2.1] — Spec-Driven Development (SDD) Workflow (2026-10-30)

### Added
- **Spec-Driven Development (SDD) Workflow (`.specify/SDD-WORKFLOW.md`)**:
  - Established formal 9-step lifecycle (Idea ➔ Spec ➔ Review Gate ➔ Implement ➔ Verify ➔ Reality Check ➔ Version Bump ➔ ADL Entry ➔ Tag).
  - Enforced 7 hard invariant rules for all future code modifications (Spec 014, ADR-013).
- **Engineering Conventions (`.specify/CONVENTIONS.md`)**:
  - Documented Python layer 3 standards (typing, dataclasses, Cyclopts CLI, centralized `get_paths()`).
  - Documented Zsh runtime standards (`emulate -L zsh`, zero hot-path subprocesses, compiled-only `.zwc` rule).
  - Documented Conventional Commit standards with mandatory Spec requirement references.
- **Standardized Templates (`.specify/templates/`)**:
  - `SPEC-TEMPLATE.md`: Structured 6-section specification template.
  - `ADR-TEMPLATE.md`: Architectural Decision Record template.
  - `PR-CHECKLIST.md`: Pre-merge review and verification gate checklist.
- **Security & Release Roadmap (`.specify/specs/README.md`)**:
  - Established execution plan for specs 014 through 021 leading to public release readiness.

## [v1.2.0] — Native Zsh Bootstrap & Declarative Engine (2026-10-25)

### Added
- **Zsh-Native Bootstrap (`install.zsh`)**:
  - Pure Zsh, zero-dependency bootstrap installer with stream-truncation protection.
  - Hard prerequisite validation (Zsh >= 5.8, Python >= 3.11, Git).
  - Atomic cloning to staging directory with local EXIT/SIGINT cleanup traps.
  - Strict repository origin verification preventing execution of unverified directories or unknown forks.
- **Unified Path Baking**:
  - `BOOT_SHIM_TEMPLATE` and `write_boot_shim` bake resolved runtime paths (`ZIRO_HOME`, `ZIRO_CONFIG`, `ZIRO_DATA`, `ZIRO_CACHE`) into `~/.config/ziro/boot.zsh`.
  - Guarantees fresh interactive shells gain full access to `ziro` CLI without requiring external environment variable definitions.
- **Idempotent Shell Profile Activation**:
  - `ziro install` automatically configures `${ZDOTDIR:-$HOME}/.zshrc` with timestamped backups (`.zshrc.bak.*`).
  - Added `--no-activate` flag to support developer checkouts and isolated testing.
- **CLI Subcommand Discovery**:
  - Added `--list-commands` flag to `core/__main__.py` for introspection.
  - Added single-source versioning in `core/constants.py`.
- **Background Update Checker**:
  - Implemented `scripts/background-update.zsh` for non-blocking idle checks.
- **Hermetic Test Suite**:
  - Added `tests/test_install_zsh.py` and `tests/test_boot_shim_paths.py`.

### Changed
- Native Zsh Bootstrap: Retired legacy `install.sh` and replaced with native, zero-dependency `install.zsh`.
- `core/install_cli.py`: Integrated build pipeline execution (`build()`) directly into the installation process, eliminating circular post-install sync requirements.
- `core/doctor_cli.py`: Unified all path inspections using shared `core/paths.py`.
- `pyproject.toml`: Compliant PEP 621 structure with `[build-system]`.

## [v1.1.3] — Ghost Integration (2026-10-16)

### Added
- **Pakrohk/ziro-ghost Integration**:
  - Integrated stable `ziro-ghost` v1.0.0 via `tools_factory.toml` (`clone-source`, order 6, `ziro-defer`).
  - Mutual exclusion (`conflicts_with`) configured with `zsh-autosuggestions`.
- **Install Flow Polish**:
  - Added terminal Nerd Font capability detection prompt to `ziro install`.
  - Configures `~/.config/ziro/ghost.conf` idempotently (`nerd_font = true` / `false`).
  - Safe default (`nerd_font = true`) on non-interactive or `--default` installations.

### Removed
- Deprecated local `ghost/` prototype directory in favor of sovereign external plugin.

### Changed
- `core/defaults_template.toml`: `auto_suggest.default` confirmed as `ziro-ghost`.
- Documentation updated in `INSTALL.md` and `ARCHITECTURE.md`.
- Spec 009 updated with R19 (Integration with ziro-shell).

## [v1.1.2] — Repository Transfer to Pakrohk (2026-10-16)

### Changed
- Repository namespace migrated from `Pakrohk-DotFiles` to `Pakrohk` (`https://github.com/Pakrohk/ziro-shell`)
- Centralized repository constants in `core/constants.py` (`GITHUB_USER`, `REPO_NAME`, `REPO_URL`)
- Updated clone URLs, installation guides, documentation, and author metadata
- Added automatic origin healing for `Pakrohk-DotFiles/ziro-shell` in `ziro/gitops.py`

## [v1.1.1] — Plugin List Update (2026-10-16)

### Added
- Core helpers: `mkcd`, `take`, `extract`, `..` navigation, `clipcopy`/`clippaste` (`lib/helpers.zsh`)
- Auto-detect aliases: `eza`, `bat`, `rg`, `fd`, `delta` (`lib/aliases.zsh`, active only when binary present)
- New default plugins: `zsh-you-should-use`, `fzf-tab`
- New optional plugin: `forgit` (enable via config)
- New `[git]` category in `defaults.toml` with `none` option

### Changed
- `wd` moved to alternatives (`zoxide` is the default navigation)
- Load order updated to accommodate `fzf-tab` after `fzf`

### No Breaking Changes
- Existing users keep their current plugin set
- New defaults apply only on fresh install or via `ziro config reset`

## [v1.1.0] — Declarative Architecture (2026-10-16)

### Changed (Architecture)
- Tools registry migrated to declarative `core/tools_factory.toml` (single source of truth)
- `core/generator.py` rewritten as generic reader/emitter (no hardcoded tool names)
- Load order derived from TOML `load_order` field (was hardcoded)
- Adding a new tool now requires TOML-only edit — no Python changes

### Added
- `core/tools_factory.toml` — declarative schema (name, type, category, load_method, load_timing, load_order, guard)
- 25 new tests covering schema validation, generic emission, declarative acceptance
- `docs/wiki/sources/spec-006-declarative-registry.md` — public docs

### Removed
- All hardcoded `if name == ...` branches in generator
- `LOAD_ORDER` constant
- `__getattr__` compatibility shim (TECH-DEBT-001 resolved)

### Behavioral Guarantee
- Generated `plugins.gen.zsh` is byte-identical to v1.0.2 output — no user-facing change

## [1.0.0] — Foundation Release (2026-10-13)

### Added

- **Layer 0**: Shell bootstrap (`integration.zsh`, `ziro.zsh` dispatcher)
- **Layer 1**: Plugin analyzer with regex signal detection (compdef, ZLE, hooks, bindkey, eval, PATH)
- **Layer 2**: Tag system (7 built-in tags, conflict detection, TOML-based user overrides)
- **Layer 3**: `ziro_load` frozen interface + plugins.gen.zsh generator
- **T1/T2/T3**: Prompt abstraction (starship, p10k, pure, none) + theme provider + resolver
- **CLI**: `install`, `plugin`, `tag`, `config`, `suggest`, `theme`, `prompt`, `doctor`, `bench`
- **Analyzer cache**: hash-based invalidation in `~/.cache/ziro/analysis/`
- **Async analysis**: `analyze_many` with asyncio parallel execution
- **Hook re-registration**: compensating registration for `wd`, `alias-tips`
- **--raw escape hatch**: verbatim injection for power users
- **Parity test suite**: deferred vs eager behavior equivalence
- **CI**: GitHub Actions test workflow (Python 3.11, 3.12)

### Benchmarks

- Hot-path: `< 5ms` Ziro contribution (target met)
- 229 tests (unit and integration)

### Architecture

- See `ARCHITECTURE.md` for layer model and frozen interfaces
- State management: config/cache/derived separation (XDG-compliant)

### Documentation

- `README.md` — quick start
- `INSTALL.md` — installation guide
- `ARCHITECTURE.md` — layer model
- `docs/wiki/sources/` — architecture decision records (ADRs)

## Pre-release history

See git log for Phase 0 through Phase 6d commits.
