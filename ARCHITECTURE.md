# Ziro-Shell Architecture

Ziro is layered Zsh runtime customization system. Each layer has
one responsibility, communicates via frozen interfaces, and runs
either in hot-path (< 5ms) or cold-path (user-invoked).

## Layered Model

```
┌─────────────────────────────────────────────────────────────┐
│ L0 — Shell Bootstrap (< 5ms, hot)                           │
│     integration.zsh → source vendor + plugins.gen.zsh       │
├─────────────────────────────────────────────────────────────┤
│ L1 — Plugin Analyzer (cold)                                 │
│     Static regex scan → Schema A (analysis JSON)            │
├─────────────────────────────────────────────────────────────┤
│ L2 — Tag System (cold)                                      │
│     Merge analysis + user tags → Schema C                   │
├─────────────────────────────────────────────────────────────┤
│ L3 — znap Runtime (hot, emit-only)                          │
│     ziro_load interface → znap source / ziro-defer          │
│     (includes ziro-ghost from Pakrohk/ziro-ghost)           │
└─────────────────────────────────────────────────────────────┘
```

## Layer 3 Autocompletion & Plugins

Ghost (`ziro-ghost`) is integrated as the default Layer 3 autosuggestion plugin:
- Loaded via znap from `Pakrohk/ziro-ghost` with `ziro-defer` at load order 6 (immediately following `fzf` at order 5).
- Declared in `core/tools_factory.toml` with `load_method = "clone-source"` and mutual exclusion with `zsh-autosuggestions`.
- Zero forks on hot-path; configuration resides in `~/.config/ziro/ghost.conf`.

## Hot-path budget

- **Target**: Ziro contribution < 5ms per shell startup
- **Measured by**: `ziro bench` (min-of-11)
- **Enforced by**: no Python, no subprocess, no file parsing in L0

## Frozen interfaces

| Interface   | Location                                  | Consumed by   |
|-------------|-------------------------------------------|---------------|
| Schema A    | `~/.cache/ziro/analysis/*.json`           | L2 resolver   |
| Schema B    | `~/.config/ziro/tags/`                    | L2 resolver   |
| Schema C    | `~/.config/ziro/derived/plugins.gen.zsh`  | L0 bootstrap  |
| `ziro_load` | `core/ziro_load.py`                       | L2 generator  |

## State management

| Location                     | Category       | Deletable        |
|------------------------------|----------------|------------------|
| `~/.config/ziro/`            | user config    | No               |
| `~/.config/ziro/derived/`    | generated      | Yes (regenerate) |
| `~/.cache/ziro/`             | ephemeral      | Yes              |
| `~/.ziro/`                   | vendored runtime | No             |

## CLI surface

| Command                                    | Layer   | Module                     |
|--------------------------------------------|---------|----------------------------|
| `ziro install`                             | L0      | `core/install_cli.py`      |
| `ziro update`                              | L0      | `core/update_cli.py`       |
| `ziro plugin add/remove/list/show`         | L1+L2+L3| `core/plugin_cli.py`       |
| `ziro tag list/show/add/remove/reset`      | L2      | `core/tag_cli.py`          |
| `ziro config show/edit`                    | L0      | `core/config_cli.py`       |
| `ziro suggest list/set/disable`            | L0      | `core/suggest_cli.py`      |
| `ziro theme list/current/apply/reset`      | T2      | `core/theme_cli.py`        |
| `ziro prompt list/current/set`             | T1      | `core/prompt_cli.py`       |
| `ziro doctor`                              | L0      | `core/doctor_cli.py`       |
| `ziro bench`                               | L0      | `core/bench_cli.py`        |
| `ziro completion`                          | L0      | `core/completion_cli.py`   |

## Non-goals

- Zinit integration (permanently removed, ADR-002)
- IRIS integration (permanently removed)
- Python in hot-path
- Network access in hot-path

## See also

- `README.md` — user guide
- `INSTALL.md` — installation
- `CHANGELOG.md` — version history
- `docs/wiki/sources/` — architecture decision records (ADRs)

## Legacy code

`~/.ziro/ziro/` contains early DDD hexagonal architecture that is
**deprecated** as of v1.0.0. It is not imported by any active code.
See `~/.ziro/ziro/DEPRECATED.md` for full explanation and removal timeline.

Active code lives in:
- `~/.ziro/core/` — Python core (flat modules)
- `~/.ziro/commands/` — Zsh CLI modules
- `~/.ziro/lib/` — Zsh helpers
- `~/.ziro/prompts/` — Prompt adapters
- `~/.ziro/themes/` — Theme files
