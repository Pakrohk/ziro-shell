# Changelog

All notable changes to ziro-shell are documented in this file.
This project adheres to [Semantic Versioning](https://semver.org/) and a structured release governance process.

---

## [v1.3.2] — 2026-11-04

### Fixed
- Generator now recognizes `on-demand` load_method (37 tests unblocked)
- Bench v2.1 tests aligned with new output structure (2 tests)
- TTY fallback test — lazy import of rich.console in bench_cli (1 test)

### Added
- Generator dispatch for future strategies: eager-shim, lazy-compinit, background-service, compiled-artifact (raises NotImplementedError with SPEC-027 reference until implemented)

### Notes
- Ghost Tab binding fix (ADL-041) now included in v1.3.2 release
- Test suite: 671 passing (631+37+2+1)

---

## [v1.3.1] — 2026-11-03

### Added
- **Release Manifests System**: 12 complete, user-facing release manifests covering v1.2.1 through v1.3.1 in `.specify/releases/`.
- **System Evolution Guide**: Created `docs/JOURNEY.md` documenting the technical background, design problems, and solutions for each release since v1.2.0.
- **Workflow Governance**: Mandated user-facing release manifests before tagging any new release.

---

## [v1.3.0] — 2026-11-03

### Added
- **Ghost v2.0.1 Integration**:
  - Automatic multi-architecture binary downloading with SHA256 checksum verification (`linux-x86_64`, `linux-aarch64`, `darwin-x86_64`, `darwin-arm64`).
  - Modular tool splitting into deferred inline suggestion line (`ghost-v2-line`) and on-demand Rust Focus Mode popup (`ghost-v2-focus`).
  - Runtime health monitoring and binary version reporting integrated into `ziro doctor`.
- **AI-Safe System Management Layer (`ziro mcp`)**:
  - JSON-RPC 2.0 stdio Model Context Protocol server exposing 16 structured tools across 5 domains.
  - Read-only inspection tools covering host system info, package managers, CLI binaries, sanitized environment variables, and directory semantics.
  - Safe-mode enabled by default; mutating commands require an explicit `--allow-execute` flag.
  - Deliberative two-step confirmation for command execution using single-use 60-second time-limited tokens.
  - Immutable audit logging to `~/.cache/ziro/mcp/audit.jsonl` with restricted file permissions (mode 0600).

### Deprecated
- `ziro ghost preview` is deprecated in favor of `ziro update` and scheduled for removal in v1.4.0.

---

## [v1.2.10] — 2026-11-03

### Added
- **External Tools Observability**:
  - `ziro stats`: Aggregate metrics, call counts, and error telemetry from external companions.
  - `ziro health`: Inspect diagnostic readiness and self-test reports.
  - `ziro doctor` extended with automated external tool health auditing.
  - Open telemetry protocol: automatic discovery for any tool recording metrics to standardized paths.

---

## [v1.2.9] — 2026-11-02

### Added
- **Remote Clipboard over SSH (OSC 52)**:
  - Native terminal escape sequences allowing remote SSH sessions to copy directly to your local workstation clipboard.
  - 4-layer fallback chain: Native desktop GUI → macOS native → OSC 52 → local secure file buffer.
- **Headless Server Adaptations**:
  - Pager fallbacks for text files viewed on headless servers; clear notices for web links without hanging terminal sessions.
  - Terminal capability auditing in `ziro doctor` with per-terminal setup guides.

---

## [v1.2.8] — 2026-11-02

### Security
- **Root Shell Hardening**:
  - Restricted execution options in fuzzy finder widgets when running under root.
  - Isolated temporary clipboard buffers to user-restricted runtime directories.
  - Disabled automatic SSH agent forwarding in root administrative sessions.
  - Dedicated root prompt profile excluding unvetted custom script modules.

---

## [v1.2.7] — 2026-11-02

### Changed
- **Continuous Integration Architecture**:
  - Split automated test suites into distinct unit and integration stages.
  - Cleaned and isolated runner environments, achieving 100% green builds across Linux and macOS matrix targets.
  - Stabilized fallback stubs when third-party utilities are missing on minimal systems.

---

## [v1.2.6] — 2026-11-01

### Performance
- **Zero Input Lag**:
  - Moved autosuggestion history filtering out of interactive keystroke handling into background precmd hooks, reducing typing latency to under 2ms.
- **Optimized Test Suite**:
  - Reduced complete test suite execution time by 50% through improved test harness isolation.

---

## [v1.2.5] — 2026-11-01

### Security
- **Universal Secure Permissions**:
  - Enforced strict POSIX permissions across all created directories (mode 700) and files (mode 600).
  - Protected configuration, compiled bytecode, and caches against unauthorized access by other local users on shared systems.
  - Added automated permission auditing to system health diagnostics.

---

## [v1.2.4] — 2026-11-01

### Added
- **Community Theme Sharing**:
  - New `ziro theme submit` command to share custom Starship prompt designs with the community via automated pull requests.
  - Included 5 starter theme presets with instant switching.
  - Verified prompt component integrity checks during theme application.

---

## [v1.2.3] — 2026-10-31

### Security
- **Secret Redaction in History Cache**:
  - Automatic detection and redaction of 10 credential patterns (cloud keys, API tokens, passwords, private SSH keys) before writing history cache files.
  - Enforced private file modes (600) on all history cache files.

---

## [v1.2.2] — 2026-10-31

### Fixed
- **Non-Interactive Shell Execution**:
  - Gated interactive shell hooks behind interactivity checks, preventing unexpected behavior in background scripts, cron jobs, and SSH remote commands.
- **Boot Configuration Protection**:
  - Added installation directory path validation before writing startup boot shims.

---

## [v1.2.1] — 2026-10-30

### Added
- **Spec-Driven Engineering Process**:
  - Established formal specification, acceptance testing, and review requirements for all architectural changes.
- **Upstream Repository Synchronization**:
  - Upstream change pulling and automatic core tools synchronization in the built-in update command.
