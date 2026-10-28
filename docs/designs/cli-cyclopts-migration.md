# Architectural Design: CLI Modernization via Cyclopts

> **Status**: Proposed (Phase 0 Design & Rationale)  
> **Target Module**: `core/cli.py` (migrating from `core/__main__.py` & `core/help_cli.py`)  
> **Scope**: Pure refactoring of CLI dispatch and argument validation for all 15 commands without behavioral change.

---

## 1. Current State & 5 Architectural Defects

The current Ziro CLI implementation relies on manual `sys.argv` string inspection and a handwritten help catalog. This design suffers from five concrete architectural problems:

### P1: Fragile Triplicate Command Registration
Adding or updating a command requires manual edits in three disparate locations:
1. The shell-side wrapper (`commands/<cmd>.zsh`)
2. The central Python dispatcher (`core/__main__.py:15-29` and `main()` `if/elif` chain at lines `51-92`)
3. The manual documentation dictionary (`core/help_cli.py:31-410` in `HELP_REGISTRY`)

**Failure Mode**: A developer adding or changing a flag must update both the parser in `<cmd>_cli.py` and the static string tuple in `help_cli.py`. If they desynchronize, `--help` lies to the user.

### P2: Hardcoded Dispatch Without Discovery
In `core/__main__.py:42-95`, dispatch is implemented via a linear `if/elif` ladder. Subcommand discovery (`--list-commands` at line 42) requires maintaining a hardcoded static tuple `COMMANDS`. Dynamic plugins or command aliases cannot register themselves organically.

### P3: Total Absence of Man Pages
Ziro ships zero UNIX man pages (`man ziro`, `man ziro-plugin`). The help text is trapped inside runtime Python data structures (`help_cli.py`), preventing package maintainers (AUR, Homebrew, Debian) from generating standard offline documentation.

### P4: Weak Runtime Type Safety & Fragile `sys.argv` Slicing
Each subcommand manually parses raw strings:
- `core/doctor_cli.py:348`: `verbose = "--verbose" in argv or "-v" in argv`
- `core/update_cli.py:180-210`: Ad-hoc flag parsing loops
- `core/plugin_cli.py:140-200`: Manual array slicing (`argv[0]`, `argv[1:]`)

**Failure Mode**: Type validation (e.g. integer `--iters`, path verification, enum choices) happens deep inside business logic rather than at the CLI boundary. Flag typos are silently ignored or cause confusing `IndexError` exceptions.

### P5: Poor Terminal Help Quality
`help_cli.py:render_entry()` formats plain ASCII text. It lacks modern CLI conventions: syntax-colored flag tables, distinct display of required vs. optional parameters, and native terminal wrapping found in modern developer tools (like `gh` or `kubectl`).

---

## 2. What Cyclopts Solves (Mapping & Before/After)

[Cyclopts](https://github.com/BrianPugh/cyclopts) is a modern CLI framework built on Python type annotations and Rich. It solves each defect directly:

| Defect | Cyclopts Solution | Architectural Benefit |
|:---|:---|:---|
| **P1 & P2** | Single `App()` root with `@app.command` | Zero duplication. Command, handler, and dispatch are declared once. |
| **P3** | Built-in Sphinx extension (`cyclopts.sphinx_ext`) | Automatic generation of man pages (`ziro.1`, `ziro-plugin.1`). |
| **P4** | Native Python type coercion (`Literal`, `Path`, `bool`, `int`) | Arguments validated before entering command body. Zero `sys.argv` slicing. |
| **P5** | Rich terminal rendering engine | Automatic colored flag tables, default values, and choice constraints from docstrings. |

### Concrete Before / After: `ziro doctor`

#### Before (`core/doctor_cli.py` & `core/__main__.py`)
```python
# In core/__main__.py
if sub == "doctor":
    from core import doctor_cli
    return doctor_cli.main(rest)

# In core/doctor_cli.py
def cmd_doctor(argv: list[str]) -> int:
    verbose = "--verbose" in argv or "-v" in argv
    # manual handling of help, execution, and exit codes...
```

#### After (`core/cli.py` + typed `core/doctor_cli.py`)
```python
# In core/cli.py
from cyclopts import App
from core.doctor_cli import run_doctor

app = App(name="ziro", help="Fast, layered Zsh runtime customization")

@app.command
def doctor(verbose: bool = False, json_output: bool = False) -> int:
    """Run full system health checks on runtime, bytecode, and dependencies.
    
    :param verbose: Display granular diagnostics for passing checks.
    :param json_output: Emit machine-readable JSON health report.
    """
    return run_doctor(verbose=verbose, json_output=json_output)
```

---

## 3. Framework Evaluation: Why Cyclopts over Alternatives?

| Criterion | `Cyclopts` (Selected) | `Typer` | `Click` | Standard `argparse` |
|:---|:---:|:---:|:---:|:---:|
| **Type Hint Native** | **100% (Python 3.10+)** | Partial (requires Click) | No (decorators) | No (runtime objects) |
| **`Union` & `Literal`** | **Native out-of-the-box** | Broken / Limited | Manual `Choice` | Manual `choices=` |
| **Sphinx / Man Builder** | **Official `sphinx_ext`** | Third-party / brittle | `sphinx-click` | Manual `sphinx-argparse` |
| **Boilerplate Ratio** | **Lowest (~30-40% less)** | High (`Annotated[...]`) | High (stacked decorators) | Highest (procedural) |
| **Terminal Formatting** | **Built-in Rich tables** | Rich via Click | Plain text | Plain text |
| **Runtime Parser** | **Independent parser** | Bound to Click engine | Procedural engine | Standard library |
| **External Dependencies** | **1 (`cyclopts`)** | Multiple (`click`, etc.)| 1 | 0 |

**Verdict**: Cyclopts provides the cleanest code-to-feature ratio. It leverages Python 3.11+ type hints directly without polluting signatures with Click metadata or `Annotated` wrappers.

---

## 4. Incremental Migration Strategy

To guarantee zero regression, migration proceeds in strict, decoupled phases:

1. **Dual-Mode Dispatch Engine**:
   `core/__main__.py` introduces a feature gate:
   ```python
   if os.environ.get("ZIRO_LEGACY_CLI") == "1":
       return legacy_main(argv)
   from core.cli import app
   return app(argv)
   ```
2. **Order of Command Migration**:
   - Step 1: `help`, `sync`, `doctor` (Zero or minimal flags)
   - Step 2: `bench`, `analyze`, `update` (Typed options, flags, and paths)
   - Step 3: `plugin`, `tag`, `theme`, `prompt`, `config` (Subcommand groups)
   - Step 4: `completion`, `install`, `suggest` (Complex workflows)
3. **Preservation of Function Signatures**:
   Existing `main(argv)` functions in each `<cmd>_cli.py` remain intact as backward-compatible shims until all commands are migrated.

---

## 5. Offline Documentation & Man Page Pipeline

Cyclopts natively integrates with Sphinx through `cyclopts.sphinx_ext`:

```python
# docs/conf.py
extensions = ["cyclopts.sphinx_ext"]

man_pages = [
    ("cli-reference", "ziro", "Ziro Shell CLI Manual", ["Pakrohk"], 1),
]
```

```rst
.. docs/cli-reference.rst
Ziro Manual
===========

.. cyclopts:: core.cli:app
```

Building the man page:
```bash
sphinx-build -b man docs/ docs/_build/man/
# Produces: docs/_build/man/ziro.1
```

---

## 6. Testing & Rollback Safety

1. **CLI Parity Contract**:
   Every command must accept the exact same flags, produce equivalent stdout/stderr output, and return identical integer exit codes (`0`, `1`, `2`).
2. **Hermetic Test Coverage**:
   - Test suites in `tests/` (`test_plugin_cli.py`, `test_install_cli.py`, `test_doctor_cli.py`) continue to pass.
   - Snapshot tests will verify that `ziro <cmd> --help` exposes all documented flags and subcommands.
3. **Instant Rollback**:
   Setting `export ZIRO_LEGACY_CLI=1` immediately reverts execution to the previous `core/__main__.py` dispatcher without needing git operations.
