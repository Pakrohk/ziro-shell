# Contributing to Ziro Shell

Thank you for contributing to `ziro-shell`. This document outlines the developer workflow, coding standards, performance budgets, testing requirements, and pull request procedures.

Ziro is engineered with a strict latency budget: **under 20ms startup in full-featured interactive sessions**. Every contribution is evaluated against this performance target.

---

## Development Environment Setup

### Prerequisites

- **Zsh**: Version 5.8 or newer (`zsh --version`).
- **Python**: Version 3.11 or newer (required for native `tomllib` support).
- **Git**: Modern git client.
- **UV / Pytest**: Python environment manager and test runner.

### Initial Workstation Setup

On developer workstations, `~/.ziro` is typically symlinked directly to your active repository clone to enable live testing of the boot chain:

```bash
# 1. Clone repository to your projects workspace
git clone https://github.com/Pakrohk/ziro-shell.git ~/Projects/ziro-shell
cd ~/Projects/ziro-shell

# 2. Establish workstation symlink (if ~/.ziro does not exist or points elsewhere)
ln -s ~/Projects/ziro-shell ~/.ziro

# 3. Create and activate a Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 4. Install development dependencies
pip install --upgrade pip
pip install pytest pytest-subtests
```

Verify your setup:
```bash
./bin/ziro doctor
```

---

## Code Standards (ADR-009)

Ziro strictly adheres to **ADR-009 ("Function-Based, Idiom-First")** across both Python and Zsh components.

### Python Guidelines (`core/*.py`)

1. **Standard Library Only**:
   - Zero heavy third-party runtime dependencies. The core runtime relies strictly on Python 3.11+ standard library (`tomllib`, `pathlib`, `subprocess`, `argparse`, `typing`).
2. **Strict Type Annotations**:
   - All function signatures, parameters, and return types must be fully typed:
     ```python
     def analyze_tool(entry: dict[str, Any], base_path: Path) -> ToolResult:
     ```
3. **PEP 8 Compliance & Dict Dispatch**:
   - Prefer dispatch tables and dictionary lookups over long `if/elif/else` ladders:
     ```python
     # Preferred: O(1) dispatch
     handlers: dict[str, Callable[[Namespace], int]] = {
         "analyze": run_analyze,
         "sync": run_sync,
         "doctor": run_doctor,
     }
     handler = handlers.get(args.subcommand, run_help)
     return handler(args)
     ```
   - Avoid double lookups (`if key in dict:` followed by `dict[key]`).
4. **Generator Invariant (`core/build.py`)**:
   - **Never hardcode tool names, plugin lists, or file paths in `core/build.py`**.
   - Build generation logic must read dynamically from `core/tools_factory.toml` and `~/.config/ziro/load.toml`.

### Zsh Guidelines (`*.zsh`, `commands/*.zsh`)

1. **Strict Shell Emulation**:
   - All functions and scripts must enforce local option scoping:
     ```zsh
     emulate -L zsh
     setopt localoptions extendedglob
     ```
2. **Zero-Fork Rule on Hot Path**:
   - Spawning subshells (`$(...)` or backticks) inside the interactive boot chain or prompt loop is strictly prohibited. Subshells fork child processes (~1–3ms penalty each).
   - Use native parameter expansion instead of external binaries:
     - Basename: `${path:t}` (replaces `$(basename "$path")`)
     - Dirname: `${path:h}` (replaces `$(dirname "$path")`)
     - String substitution: `${var//old/new}` (replaces `$(echo "$var" | sed ...)`)
     - Suffix removal: `${var%.*}`
3. **Guard Returns**:
   - Use short-circuit evaluation instead of nested conditional blocks:
     ```zsh
     [[ -f "$target" ]] || return 0
     ```
4. **Default Value Fallbacks**:
   - Prefer `${var:-default}` or `: ${var:="default"}` over multi-line `if [[ -z "$var" ]]`.

---

## Architecture & Codebase Map

When contributing, ensure modifications respect Ziro's architectural layers:

```
ziro-shell/
├── bin/
│   └── ziro               # Main CLI dispatch executable
├── commands/              # High-performance fast-path Zsh commands
│   ├── analyze.zsh        # Manifest analyzer command wrapper
│   ├── doctor.zsh         # Diagnostics runner
│   ├── help.zsh           # Sub-millisecond help renderer
│   └── sync.zsh           # Bytecode compilation command
├── core/                  # Offline Python compiler & engine (Python 3.11+)
│   ├── analyzer.py        # Static analysis & signal detection
│   ├── build.py           # Boot script generator & zcompile engine
│   ├── doctor.py          # Comprehensive 11-step health check suite
│   ├── models.py          # Dataclasses & schema structures
│   ├── tools_factory.toml # Factory tool registry (23+ profiles)
│   └── update_cli.py      # Multi-stage orchestrator
├── lib/                   # Core runtime library scripts
│   ├── boot.zsh           # Fallback bootloader
│   ├── defer.zsh          # ziro-defer task queue integration
│   └── xdg.zsh            # Canonical XDG base directory paths
└── tests/                 # Unittest and pytest verification suites
```

---

## Test Suite Requirements

All changes must pass the automated test suite without regressions.

### Running Tests

Execute the full test suite via `uv` or `pytest`:

```bash
# Run pytest directly using uv
PYTHONPATH=. uv run --with pytest tests/ -q

# Or run via local virtualenv
PYTHONPATH=. pytest tests/ -q

# Run end-to-end Zsh test harness
./test.sh
```

**Acceptance Baseline**: All **434 tests** (including subtests) must pass cleanly before opening a pull request.

### Writing New Tests

- **Bug Fixes**: Every bug fix must include a reproducing test in `tests/test_*.py` demonstrating the failure before the fix and verification after.
- **New Features**: Every new configuration parameter, flag, or analyzer heuristic requires unit tests covering:
  1. Valid schema parsing.
  2. Missing or malformed input handling.
  3. Preservation of existing configuration sections.

---

## Performance Budget

Ziro enforces a non-negotiable performance budget to protect shell launch speed:

- **Startup Delta Limit**: No PR may increase cold shell startup by more than **+5 ms** over the baseline (`baseline + 5ms` is the rejection threshold).
- **Compinit Floor**: Pure-Zsh synchronous `compinit` floor is ~6.75ms. Any change altering completion initialization must benchmark cold cache hits.
- **Verification**: Run benchmarks before and after your changes:
  ```bash
  # Execute benchmark iterations
  ziro bench --iterations 50
  ```

---

## Pull Request Process & Evidence Rules

To maintain high code quality and reproducibility, all pull requests must follow these steps:

### 1. Branch Naming & Hygiene
- Create a focused topic branch: `feat/descriptive-name` or `fix/issue-description`.
- Keep commits atomic, well-formatted, and focused on a single change.

### 2. The H7 Raw Evidence Rule
Per maintainer values, **speculative or undocumented performance claims are automatically rejected**. 

Your PR description must include:
- Exact before and after command outputs (untruncated text).
- Benchmark outputs from `ziro bench` or `zsh-bench`.
- Diagnostic output from `ziro doctor`.
- Environment details (Operating System, CPU model, Zsh version, Python version).

### 3. Review SLA & Merge Criteria
- **Maintainer Review SLA**: Maintainers review active pull requests within **7 business days**.
- **Checks Required**:
  - All 434 automated tests passing.
  - Zero unvetted dependencies added.
  - No subshell forks introduced into `ziro-boot.zsh`.
  - H9 invariant respected (`[user]` section preserved across analyzer runs).

---

## Security Disclosure Protocol

Security vulnerabilities in Ziro Shell or supported first-party plugins (`ziro-ghost`, `ziro-defer`, `ziro-pf`) must be reported responsibly.

**Do not file public GitHub issues for security vulnerabilities.**

### Disclosure Procedure:
1. **GitHub Security Advisory**: Submit a private report via the [Security Advisories tab](https://github.com/Pakrohk/ziro-shell/security/advisories) of the repository.
2. **Email**: If GitHub Advisories are inaccessible, send an encrypted or standard email to the core maintainer at:
   ```
   pakrohk-security@pm.me
   ```
3. Include:
   - Detailed attack vector and proof of concept.
   - Affected versions.
   - Assessment of potential blast radius (e.g., privilege escalation, arbitrary code execution, unintended file overwrite).

Maintainers will acknowledge receipt within 48 hours and provide remediation timelines before public disclosure.
