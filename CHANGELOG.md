# Changelog

All notable changes to ziro-shell are documented here.
This project adheres to a 3-tier versioning discipline (ADR-007):
- **Patch Tier (`X.X.Y`)**: Bug fixes, internal optimizations, UI polish, CLI UX enhancements, and standalone plugin additions.
- **Minor Tier (`X.Y.X`)**: Large new features and full multi-layer subsystem orchestrations.
- **Major Tier (`Y.X.X`)**: Fundamental architecture rewrites or paradigm shifts breaking Core Principles.

## Upcoming

- **v1.1.4** — Starship themes ecosystem integration
- **v1.1.5** — Documentation polish & contributor handbook
- **v1.2.0** — Error reporting mechanism (Spec 013) + Rich CLI Progress
- **v1.4.0** — pf (cross-shell package manager) integration

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
