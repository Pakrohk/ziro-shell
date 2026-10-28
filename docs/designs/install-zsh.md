# Design Specification: Native Zsh Bootstrap (`install.zsh`) & Declarative Engine
**Version**: 1.0.0  
**Status**: Stage B Design Document (No Implementation in this stage)  
**Target Script**: `install.zsh` (~120–150 lines, zero dependencies, pure Zsh)  
**Target Engine**: `core/` (Python 3.11+ Declarative Lifecycle)

---

## 1. Responsibilities Split & Design Philosophy

The legacy `install.sh` suffered from mixed responsibilities: it attempted environment sniffing, git cloning into temporary paths, and partial execution without guaranteeing a verified destination.

Under the new architecture, responsibilities are cleanly bifurcated:
- **`install.zsh` is a Bootstrap ONLY**:
  - Enforces hard runtime prerequisites (Zsh >= 5.8, Python >= 3.11, Git when cloning).
  - Guarantees that a verified, tamper-evident repository tree exists at `$ZIRO_HOME`.
  - Atomically delegates execution to the Python engine (`cd "$ZIRO_HOME" && $PYTHON -m core install "$@"`).
  - It contains **zero** configuration logic, zero plugin analysis, and zero shell template parsing.
- **Python Engine (`core/`) is Declarative & Comprehensive**:
  - Handles all filesystem mutations (`load.toml`, `defaults.toml`, completions, venv).
  - Executes the compilation pipeline (`build()`), producing `ziro-boot.zsh`, `ziro-boot.zsh.zwc`, and the baked `boot.zsh` shim.
  - Performs idempotent shell profile activation (`${ZDOTDIR:-$HOME}/.zshrc`) with timestamped backups.
  - Runs post-install verification before exiting 0.

---

## 2. Supported Execution Modes

`install.zsh` guarantees consistent behavior across three entry points:

1. **Piped Mode (`curl -fsSL <url>/install.zsh | zsh`)**:
   - Standard automated installation for end users.
   - Piped streams cannot access stdin directly; `install.zsh` re-opens `/dev/tty` for interactive prompts (e.g. Nerd Font setup), or exports `ZIRO_NONINTERACTIVE=1` if running in headless environments.
   - **Stream Truncation Protection**: The entire script body is wrapped in `_ziro_bootstrap() { ... }` and invoked on the final line. An incomplete network stream will terminate with a syntax error without executing partial logic.
2. **File Mode (`zsh install.zsh [args...]`)**:
   - Downloaded and inspected locally prior to invocation. Full TTY preservation.
3. **Developer Checkout Mode (`cd ~/Projects/ziro-shell && ./install.zsh [args...]`)**:
   - Detects execution from inside a verified clone.
   - Rather than re-cloning to `~/.ziro`, it either symlinks `$ZIRO_HOME` to the current checkout (standard developer workflow) or executes in-place, honoring `--no-activate`.

---

## 3. Source Tree Verification & Security Model

Security invariant: **Never execute or overwrite an unverified directory.**

### 3.1 Verification Criteria
A directory is recognized as a valid Ziro tree if and only if:
1. `core/__main__.py` exists.
2. A unique Ziro root marker exists (`.ziro-root` or `pyproject.toml` containing `name = "ziro-shell"`).
3. If it is a Git repository, the `origin` remote URL must match the canonical repository:
   - HTTPS: `https://github.com/Pakrohk/ziro-shell.git` (or `.git` omitted)
   - SSH: `git@github.com:Pakrohk/ziro-shell.git`
   - Canonical constants sourced from `core/constants.py` (`GITHUB_USER=Pakrohk`, `REPO_NAME=ziro-shell`).
4. **Forks & Mirrors**: If the remote differs, `install.zsh` immediately aborts (Exit 14) unless explicitly overridden by `ZIRO_ALLOW_FORK=1`.

### 3.2 Unrelated Repository Rejection
If the caller's working directory (`$PWD`) or an existing `$ZIRO_HOME` contains an unrelated Git repository (even if it coincidentally contains a `core/` folder), `install.zsh` will refuse to execute it and abort cleanly.

---

## 4. Atomic Clone & Ref Strategy

### 4.1 Atomic Staging
- Clones are never performed directly into `$ZIRO_HOME`.
- Staging directory: `$ZIRO_HOME.tmp.$$` (where `$$` is the script's PID).
- A local `EXIT` trap in Zsh (`local_traps`) ensures that on failure or interrupt (`SIGINT`, `SIGTERM`), the temporary directory is cleaned up:
  ```zsh
  trap '[[ -d "$tmp_dir" ]] && rm -rf "$tmp_dir"' EXIT INT TERM
  ```
- Upon successful clone and verification, atomic rename:
  ```zsh
  mv "$tmp_dir" "$target_home"
  ```
- If `$ZIRO_HOME` already exists and is verified, cloning is skipped (updates are handled via `ziro update`).

### 4.2 Reference Resolution
- Default ref: Latest release tag (`git describe --tags $(git rev-list --tags --max-count=1)` or GitHub API tag).
- Fallback: `main` branch, displaying a clear yellow advisory.
- Overridable via `ZIRO_REF=<tag|commit|branch>`.
- The resolved commit SHA is printed to stdout.

---

## 5. ZIRO_HOME Resolution & Hierarchy

Path resolution in `install.zsh` mirrors `core/paths.py:get_paths()`:
1. User override: `$ZIRO_HOME` environment variable (if non-empty).
2. XDG fallback: `${XDG_DATA_HOME:-$HOME/.local/share}/ziro` (if configured by distro).
3. Default: `$HOME/.ziro`.

Precedence is strictly: `ZIRO_HOME` > `XDG_DATA_HOME/ziro` > `~/.ziro`.

---

## 6. Delegation to the Python Engine

Once `$ZIRO_HOME` is verified, `install.zsh` executes:
```zsh
cd "$ZIRO_HOME"
PYTHONDONTWRITEBYTECODE=1 exec "$PYTHON" -m core "$@"
```
*(Or without `exec` if post-execution cleanup is active; returns the engine's exact exit code).*

### 6.1 Subcommand Defaulting
- If `$1` is empty or an option (`--default`, `--custom`, `--dry-run`, `--no-activate`), prepend `install`.
- Subcommand validation uses `python -m core --list-commands`, avoiding hardcoded lists.

### 6.2 TTY Handling
- When piped (`[[ ! -t 0 ]]`):
  - If `/dev/tty` is readable, redirect python's stdin: `< /dev/tty`.
  - If headless (CI/Docker), export `ZIRO_NONINTERACTIVE=1`.

---

## 7. Deterministic Exit Codes

`install.zsh` reserves specific exit codes for bootstrap-level failures (codes 10–19), while codes >= 2 are forwarded directly from Python:

| Exit Code | Meaning | Remediation |
|:---:|:---|:---|
| **0** | Success | Run `exec zsh` to activate |
| **10** | Zsh version < 5.8 | Upgrade Zsh (`brew install zsh` or package manager) |
| **11** | Python < 3.11 or missing | Install Python 3.11+ |
| **12** | Git missing | Install Git |
| **13** | Git clone failed | Check network or repository access |
| **14** | Source verification failed | Target directory is not a valid Ziro repository |
| **15** | Unsupported OS | Linux or macOS required |
| **16** | Root execution refused | Set `ZIRO_ALLOW_ROOT=1` if running inside a container |

---

## 8. Python Engine Enhancements (`core/`)

To support a seamless bootstrap, the Python engine requires three structural enhancements:

### 8.1 Runtime Path Baking in `build.py`
The `BOOT_SHIM_TEMPLATE` (written to `~/.config/ziro/boot.zsh`) must bake the resolved absolute paths:
```zsh
# Generated by ziro install/sync — do not edit
export ZIRO_HOME="/resolved/path"
export ZIRO_CONFIG="/resolved/config"
export ZIRO_DATA="/resolved/data"
export ZIRO_CACHE="/resolved/cache"
if [ ! -f "${ZIRO_CACHE}/ziro-boot.zsh.zwc" ]; then
  echo 'ziro: ziro-boot.zsh.zwc missing. Run: ziro sync' >&2
  return 1
fi
source "${ZIRO_CACHE}/ziro-boot.zsh"
```
*Impact*: Fixes P0 bug C1. In any new subshell, `ZIRO_HOME` is guaranteed to be set.

### 8.2 Build Pipeline Integration in `install_cli.py`
After `install_cli.py` writes configurations (`load.toml`, `tools.toml`, `tags/`), it immediately invokes `build()` from `core/build.py`.
- If compilation fails, `install` exits non-zero.
- Eliminates the circular documentation requirement where users had to source an empty shim before running `ziro sync`.

### 8.3 Idempotent Activation Step
- Checks `${ZDOTDIR:-$HOME}/.zshrc`.
- If line `source <config>/boot.zsh` is already present, skips addition.
- If missing, creates a timestamped backup (`~/.zshrc.bak.YYYYMMDDHHMMSS`) and appends the line.
- Flags: `--no-activate` disables activation; `--dry-run` simulates without modifying files.
- Default: **Activate enabled** (new users expect an installer to configure their shell).
- Concluding banner outputs: `Run: exec zsh`.

### 8.4 Introspection & Versioning
- `core/__main__.py`: Supports `--list-commands`, outputting a clean whitespace-separated list.
- Single version constant in `core/constants.py` (or read from `pyproject.toml`), referenced by `ziro.zsh`.

---

## 9. Migration & Legacy Installer Handling

- `install.sh` is retired in favor of pure native `install.zsh` (since backward compatibility before initial public release is waived).
- Installations and updates use the native `install.zsh` bootstrap engine directly.

---

## 10. Testing Matrix (Hermetic Tests)

Stage C implementation will include `tests/test_install_zsh.py` executed in isolated environments (`HOME=/tmp/test_home_$$`):

1. **`test_piped_install_creates_repo`**: Verifies `cat install.zsh | zsh` establishes verified Git repo at `$ZIRO_HOME`.
2. **`test_fresh_shell_boot_chain`**: Spawns isolated `zsh -f` sourcing newly created `boot.zsh`; verifies `ziro --version` and `ziro doctor` pass with `ZIRO_HOME` initially unset.
3. **`test_exit_code_old_zsh`**: Mocks `zsh` version < 5.8 -> expects Exit 10.
4. **`test_exit_code_old_python`**: Mocks `python3` version < 3.11 -> expects Exit 11.
5. **`test_unrelated_repo_rejection`**: Directs install to a Git repo lacking Ziro markers -> expects Exit 14.
6. **`test_fork_rejection_and_override`**: Git repo from unknown fork fails with Exit 14 unless `ZIRO_ALLOW_FORK=1`.
7. **`test_cleanup_trap_on_sigint`**: Simulates clone interruption; confirms `$ZIRO_HOME.tmp.$$` is purged.
8. **`test_activation_idempotency`**: Running `install.zsh` twice leaves exactly one `source` line in `~/.zshrc` and creates a backup.
9. **`test_custom_xdg_paths`**: Sets custom `XDG_CACHE_HOME` and `ZIRO_CACHE`; asserts build and boot shim match.
10. **`test_list_commands_parity`**: Asserts `python -m core --list-commands` matches actual command files.

---

## 11. Rollback & Fault Tolerance

If an installation fails mid-run:
1. Trap removes `$ZIRO_HOME.tmp.$$`.
2. If `~/.zshrc` was backed up before an engine crash, the backup file is available and reported in the error message.
3. Partial artifacts in `~/.config/ziro` or `~/.cache/ziro` never leave `.zwc` in an inconsistent state (compiled atomically via temporary files and `os.replace`).
