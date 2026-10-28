# Architectural Specification: Command & Internal Microservices Pattern
**Version**: 1.0.0  
**Status**: Proposed / Core Standard  
**Target Runtime**: Ziro Shell (Native Zsh Hot-Path + Python 3.11+ Cold-Path)

---

## 1. Executive Summary & Problem Statement

### 1.1 Context & Motivation
As `ziro-shell` matured, the codebase experienced architectural drift. What started as an intent-oriented, low-latency Zsh compiler gradually accrued loose scripts, duplicated logic, scattered CLI entry points, and temporary development artifacts (`.specify/`, `.opencode/`, orphaned `.zwc` binaries). 

Furthermore, the relationship between Zsh CLI wrappers (`commands/*.zsh`) and the Python backend (`core/*.py`) lacked formal boundaries:
- In the **Zsh layer**, command resolution was split between root scripts (`ziro.zsh`), shims (`integration.zsh`), and dynamically sourced commands (`commands/*.zsh`).
- In the **Python engine**, responsibilities were tightly coupled: `install_cli.py` attempted configuration management, venv bootstrapping, and generator calls, while `build.py` entangled manifest parsing, string-templated code emission, compilation, and boot validation.
- Documentation suffered from internal specification leakage, cluttering user-facing guides with internal draft jargon ("Spec 006 R4", "Spec 008").

### 1.2 Design Goals
1. **Command Pattern**: Treat every CLI interaction as a discrete, self-contained Command with standardized validation, execution, and introspection capabilities.
2. **Internal Microservices Architecture**: Deconstruct the Python engine into single-responsibility, loosely coupled services communicating via immutable typed Data Transfer Objects (DTOs).
3. **Pristine Project Hierarchy**: Re-establish the clean, canonical directory tree (`bin/`, `commands/`, `core/`, `lib/`, `tests/`) and purge all bloat.
4. **Zero Startup Degradation**: Maintain the strict sub-millisecond hot-path startup budget (< 5ms) while providing full declarative safety in the cold-path engine.

---

## 2. Pattern 1: The Command Pattern (Unified CLI & Execution)

### 2.1 The Problem
Previously, command dispatch was fragmented:
- `core/__main__.py` hardcoded a flat list of commands with bespoke `if/elif` handling.
- `core/help_cli.py` maintained a separate registry (`HELP_REGISTRY`).
- `ziro.zsh` checked for module existence via filesystem inspection (`[[ -r "$module" ]]`).
- Adding a new command required editing up to four different files across Python and Zsh.

### 2.2 Command Architecture Overview
The system employs a two-tier Command Pattern:
1. **Shell Fast-Path Dispatcher (`bin/ziro` & `commands/*.zsh`)**: Lightweight shell wrappers that handle terminal TTY attachment, environment isolation, and fast delegation.
2. **Python Engine Command Contract (`core/commands/`)**: Standardized Python command objects implementing a common interface.

```
                  ┌──────────────────────────────┐
                  │    User Terminal Invocation  │
                  └──────────────┬───────────────┘
                                 │
                         $ ziro sync --force
                                 ▼
                  ┌──────────────────────────────┐
                  │   bin/ziro CLI Dispatcher    │
                  └──────────────┬───────────────┘
                                 │
                      Hot-Path / Interactive?
                     /                       \
           (Zsh Command)                   (Engine Delegation)
                 │                                   │
      commands/sync.zsh                   core/__main__.py
                 │                                   │
        Source Fast-Path                  CommandRegistry.dispatch()
                 │                                   │
                 ▼                                   ▼
          Native Zsh Exec                   SyncCommand.execute()
```

### 2.3 Python Command Contract (`core/commands/base.py`)

All engine subcommands implement the abstract `Command` interface:

```python
"""core/commands/base.py — Abstract Command definition."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass(frozen=True)
class CommandMetadata:
    """Metadata describing a command for help and completion discovery."""
    name: str
    summary: str
    usage: str
    subcommands: dict[str, str] = field(default_factory=dict)
    flags: list[tuple[str, str]] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CommandResult:
    """Standardized outcome of a command execution."""
    exit_code: int
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.exit_code == 0


class Command(ABC):
    """Encapsulates a CLI action and its parameters."""

    @property
    @abstractmethod
    def metadata(self) -> CommandMetadata:
        """Return the documentation and structural metadata for this command."""
        ...

    @abstractmethod
    def execute(self, argv: Sequence[str]) -> CommandResult:
        """Execute the command with the provided argument vector."""
        ...
```

### 2.4 Command Registry (`core/commands/registry.py`)

A centralized registry replaces hardcoded dispatch tables and provides programmatic introspection (`--list-commands`):

```python
"""core/commands/registry.py — Central Command Registry."""
from __future__ import annotations

from typing import Iterator
from core.commands.base import Command, CommandResult


class CommandRegistry:
    """Central registry and dispatcher for all engine commands."""

    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}

    def register(self, command: Command) -> None:
        name = command.metadata.name
        if name in self._commands:
            raise KeyError(f"Command already registered: {name}")
        self._commands[name] = command

    def get(self, name: str) -> Command | None:
        return self._commands.get(name)

    def list_command_names(self) -> list[str]:
        """Return sorted list of all registered command names."""
        return sorted(self._commands.keys())

    def __iter__(self) -> Iterator[Command]:
        return iter(self._commands.values())

    def dispatch(self, name: str, argv: list[str]) -> CommandResult:
        cmd = self.get(name)
        if not cmd:
            return CommandResult(
                exit_code=2,
                message=f"ziro: unknown command '{name}'. See 'ziro help'."
            )
        return cmd.execute(argv)
```

---

## 3. Pattern 2: Internal Microservices Pattern (Decoupled Cold-Path Services)

### 3.1 The Problem
Historically, modules like `core/build.py` and `core/install_cli.py` operated as monoliths:
- `build.py` read manifests, calculated overrides, rendered raw Zsh scripts via string manipulation, compiled `.zwc`, and performed live subprocess testing on the output script.
- Modifying one aspect (e.g. cache path resolution) required tracing side effects through multiple independent operations.
- State was frequently mutated via `os.environ`, causing unintended test cross-pollution.

### 3.2 Service Architecture & Autonomous Boundaries
The cold-path engine is organized into five focused, internal microservices. Each service:
- Owns a single logical domain.
- Operates strictly through typed interfaces.
- Emits no side effects outside its designated storage roots.
- Communicates using immutable dataclass models (`core/models.py`).

```
                    ┌───────────────────────────────┐
                    │       Command Controller      │
                    │   (Sync, Doctor, Install...)  │
                    └───────────────┬───────────────┘
                                    │
       ┌──────────────┬─────────────┼──────────────┬──────────────┐
       ▼              ▼             ▼              ▼              ▼
┌──────────────┐┌──────────────┐┌──────────────┐┌──────────────┐┌──────────────┐
│ConfigService ││AnalyzeService││ BuildService ││HealthService ││PluginService │
├──────────────┤├──────────────┤├──────────────┤├──────────────┤├──────────────┤
│- load.toml   ││- AST Parser  ││- Script Gen  ││- Diagnostics ││- Git Fetch   │
│- User Config ││- Hook Detect ││- ZWC Compiler││- Path Verif  ││- Manifests   │
│- Overrides   ││- Stage Class ││- Boot Shim   ││- Integrity   ││- Updates     │
└──────────────┘└──────────────┘└──────────────┘└──────────────┘└──────────────┘
```

### 3.3 Service Specifications

#### 1. `ConfigurationService` (`core/services/config_service.py`)
- **Domain**: Storage, parsing, and validation of user preferences and manifests (`load.toml`, `defaults.toml`, `overrides.toml`).
- **Input**: Configuration directory path (`ZIRO_CONFIG`).
- **Output**: Typed `ManifestModel`, `ToolDefinition` instances.
- **Invariant**: Read-only verification unless an explicit modification command is executed.

#### 2. `AnalysisService` (`core/services/analysis_service.py`)
- **Domain**: Static code analysis of candidate shell scripts and plugins.
- **Capabilities**:
  - Inspects ZLE widgets, completion signatures (`#compdef`), and hook registrations (`add-zsh-hook`).
  - Classifies timing stages: Stage 2 (Eager Env), Stage 4 (Prompt Baseline), Stage 5 (Post-Prompt Deferred), Stage 7 (On-Demand).
- **Invariant**: Pure function. No environment modification, no subshell execution.

#### 3. `BuildService` (`core/services/build_service.py`)
- **Domain**: Deterministic compilation pipeline (orchestrated during `ziro sync` and `ziro install`).
- **Responsibilities**:
  - Accepts validated `ManifestModel`.
  - Generates flattened, dependency-ordered `ziro-boot.zsh`.
  - Bakes runtime paths (`ZIRO_HOME`, `ZIRO_CONFIG`, `ZIRO_DATA`, `ZIRO_CACHE`) into the 7-line `boot.zsh` entrypoint.
  - Invokes `zcompile` to produce byte-compiled `.zwc` wordcode.
  - Verifies artifact freshness.

#### 4. `HealthService` (`core/services/health_service.py`)
- **Domain**: Diagnostic probes and environment verification (`ziro doctor`).
- **Probes**:
  - `PythonVersionProbe`: Verifies Python runtime >= 3.11.
  - `ZshVersionProbe`: Verifies Zsh runtime >= 5.8.
  - `BootChainProbe`: Verifies consistency between `load.toml -> boot.zsh -> ziro-boot.zsh -> ziro-boot.zwc`.
  - `PathResolutionProbe`: Verifies tool targets exist on disk without polluting environment variables.
- **Invariant**: 100% side-effect free. Never writes to disk, never mutates `os.environ`.

#### 5. `PluginService` (`core/services/plugin_service.py`)
- **Domain**: Git checkout lifecycle, submodule coordination, and vendor isolation.
- **Responsibilities**:
  - Clones remote repositories to `$ZIRO_DATA/vendor/` with atomic `.tmp.$$` directory moves.
  - Dispatches `ziro update` check requests against remote remotes.

---

## 4. Canonical Target Repository Layout

To eliminate codebase bloat and align with the clean architecture, the repository adheres to the following structural standard:

```
ziro-shell/
├── bin/
│   └── ziro                       # Canonical executable entrypoint (symlinked to PATH)
├── commands/                      # Fast-path native Zsh commands
│   ├── analyze.zsh                # Analyzer invocation wrapper
│   ├── doctor.zsh                 # Diagnostic runner
│   ├── help.zsh                   # Immediate help renderer
│   ├── install.zsh                # Setup and activation wrapper
│   ├── plugin.zsh                 # Plugin management command
│   ├── sync.zsh                   # Bytecode compilation command
│   └── update.zsh                 # Repository and vendor updater
├── core/                          # Offline Python compiler & engine (Python 3.11+)
│   ├── commands/                  # Command Pattern implementations
│   │   ├── __init__.py
│   │   ├── base.py                # Command and Result protocols
│   │   ├── registry.py            # CommandRegistry
│   │   └── ...                    # Individual command handlers (SyncCommand, etc.)
│   ├── services/                  # Decoupled Microservices
│   │   ├── __init__.py
│   │   ├── analysis.py            # Static AST & signal analyzer
│   │   ├── build.py               # Compilation pipeline & zcompile engine
│   │   ├── config.py              # Manifest & settings service
│   │   ├── health.py              # 11-step diagnostic health engine
│   │   └── plugin.py              # Vendor package orchestrator
│   ├── models.py                  # Immutable DTOs & Schema definitions
│   ├── paths.py                   # Canonical path resolver (get_paths)
│   ├── tools_factory.toml         # Factory tool definitions (28 tools)
│   └── __main__.py                # Main engine CLI entrypoint
├── lib/                           # Core runtime library scripts
│   ├── boot.zsh                   # Fallback bootloader
│   ├── defer.zsh                  # Scheduler and queue orchestration
│   └── xdg.zsh                    # Canonical XDG base directory definitions
├── scripts/                       # Developer & maintenance scripts
│   ├── background-update.zsh      # Safe idle background update checker
│   └── mirror-adrs.sh             # Architecture decision record sync utility
├── tests/                         # Hermetic test suite (pytest + unittest)
│   ├── test_build.py
│   ├── test_doctor.py
│   ├── test_install_zsh.py
│   └── ...
├── docs/                          # Public, human-centric documentation
│   ├── ARCHITECTURE.md            # Overall system architecture
│   ├── BENCHMARKS.md              # Benchmarks and latency methodology
│   ├── CONFIGURATION.md           # Configuration options and overrides
│   ├── CONTRIBUTING.md            # Contributor guide
│   ├── DEFER.md                   # Multi-stage task scheduler guide
│   ├── MIGRATION.md               # Migration guides (OMZ, Prezto, Zinit)
│   ├── designs/                   # Architecture Specifications & Designs
│   │   ├── design-patterns.md     # This document
│   │   └── install-zsh.md         # install.zsh bootstrap design
│   └── README.md                  # Project entrypoint overview
├── pyproject.toml                 # Packaging & tool config
├── install.zsh                    # Zero-dependency bootstrap script (< 150 lines)
├── README.md                      # Primary project documentation
└── LICENSE                        # License definition (MIT)
```

### 4.1 Bloat Pruning Inventory (Immediate Cleanup Targets)
The following files and directories represent development artifacts or obsolete shims and are designated for pruning:
- **Obsolete Root Shims**: `integration.zsh`, `integration.zsh.zwc` (replaced by direct `boot.zsh` source).
- **Temporary Tool Storage**: `.specify/`, `.specify-backup-*/`, `.opencode/`, `opencode-rag.json`.
- **Untracked Local Files**: `.zshrc.local`, `.zshrc.local.example`, `.last_update_check`.
- **Internal Spec Drift**: `docs/wiki/sources/spec-*.md` (re-engineered into formal architectural guides without internal milestone jargon).

---

## 5. Architectural Invariants & Non-Negotiables

1. **Hot-Path Startup Constraint**:
   Hot-path code (`lib/*.zsh`, `ziro-boot.zsh`) must execute in `< 5ms` on modern hardware. Under no circumstances may Python be invoked during interactive shell startup.
2. **Standard Library Purity**:
   The Python cold-path engine must never require third-party dependencies (`pip install`). It must run on standard Python 3.11+ using built-in `tomllib`, `pathlib`, `dataclasses`, and `typing`.
3. **Immutability of System Inspections**:
   Health audits (`ziro doctor`) and analyses (`ziro analyze`) must be strictly read-only. They must never mutate system settings, create stray lockfiles, or modify `os.environ`.
4. **Declarative State Authority**:
   `load.toml` is the sole source of truth for shell startup artifacts. Dynamic filesystem sniffing during startup is prohibited.
5. **Human-Centric Documentation**:
   All public documentation must describe features by purpose and technical design rather than internal sprint milestones or specification IDs.

---

## 6. Implementation & Transition Strategy

To maintain continuous stability and keep all 440 tests green:
1. **Phase 1 (Stage A Completed)**: Fix foundational path resolution (`core/paths.py`), ensure doctor uses unified paths, provide `background-update.zsh`.
2. **Phase 2 (Stage B & C - In Progress)**: Design and implement the native `install.zsh` bootstrap, ensuring declarative path baking into `boot.zsh`.
3. **Phase 3 (Service Refactoring)**: Incrementally extract service classes from monolithic modules (`core/build.py` -> `core/services/build.py`) while maintaining backwards-compatible function aliases in their original modules.
4. **Phase 4 (Repository Pruning)**: Safely remove development leftovers and obsolete wiki source drafts in a dedicated clean commit.
