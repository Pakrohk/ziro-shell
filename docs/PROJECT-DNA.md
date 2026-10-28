# Ziro Ecosystem — Design DNA & Inspiration

> **Provenance Record** — This document is permanent. Do not remove or
> modify without explicit architectural decision.

## Primary Inspiration: EVOID

**Repository**: https://github.com/EvolveBeyond/EVOID  
**Project**: Reference Runtime for Intent-Oriented Programming (IOP)  
**Motto**: *"Data declares what, runtime decides how."*

Ziro Ecosystem is architecturally inspired by EVOID. The following core
concepts are directly derived from or influenced by EVOID's design:

### 1. Intent-Oriented Programming (IOP)

**EVOID**: Data declares *what* it needs; runtime decides *how*.
**Ziro**: Sources declare *what* they provide; the strategy engine decides *when* and *how* to invoke them.
**Context**: Implemented in the ghost autocompletion engine and source strategy.

### 2. Intent Levels → Priority Slots

**EVOID**: Three levels (`ephemeral`, `standard`, `critical`) — each maps to a different pipeline depth (validate → authorize → audit → protect).
**Ziro**: Four slots (`a`, `b`, `c`, `d`) — each maps to a different scheduling priority.
**Context**: Implemented in the runtime task scheduler (`a`=critical, `b`=normal, `c`=lazy, `d`=background).

### 3. Pipeline → Strategy Engine

**EVOID**: Pipeline runs Processors (validate, authorize, audit) in sequence.
**Ziro**: Strategy engine evaluates conditions (`requires_present`, `requires_absent`, `requires_success`, `requires_failed`) before dispatch.
**Context**: Implemented in conditional task scheduling and suggestion dispatch.

### 4. Adapter → Source Handler

**EVOID**: Adapter converts external event → Intent.
**Ziro**: Source handler converts query → `_ghost_results` array.
**Context**: Implemented in the source handler function contract.

### 5. Runtime, not Framework

**EVOID**: EVOID is a runtime, not a framework. It composes adapters and pipelines.
**Ziro**: `ziro-defer` is a runtime scheduler, not a framework. It composes tasks and hooks.
**Context**: Core philosophy of `ziro-defer`.

### 6. Declarative Configuration (TOML)

**EVOID**: `evoid.toml` — declarative config.
**Ziro**: `defer.conf`, `ghost.conf`, `ziro-plugin.toml` — all TOML.
**Context**: Applied across declarative configuration and plugin manifests.

### 7. Plugin System

**EVOID**: PyPI + git install plugins.
**Ziro**: `ziro-plugin.toml` manifest — optional, never required.

### 8. AI Agent Integration (MCP)

**EVOID**: `create_mcp_server()` for AI agent integration.
**Ziro**: (Future) Ghost popup as MCP server for AI-driven completion.

## What Ziro Adds Beyond EVOID

| Dimension | EVOID | Ziro |
|:---|:---|:---|
| **Domain** | Application backends | Shell runtime |
| **Hot path** | Not applicable (server) | Strict < 5ms budget |
| **Zero-fork** | Not required | Mandatory in Stages 0-4 |
| **Layers** | Adapters → Runtime | 4-layer system model |
| **Plugin model** | PyPI packages | Sovereign zsh plugins (Principle XIV) |

## Immutable Principles Derived from EVOID

1. **Declarative over imperative** — configuration declares behavior, code executes it.
2. **Runtime over framework** — compose, don't inherit.
3. **Levels over flags** — a small number of semantic levels beats many boolean flags.
4. **Pipeline over conditional** — chains of processors beat nested if/else.
5. **Adapter over monolith** — separate the transport from the logic.

## References

- EVOID repository: https://github.com/EvolveBeyond/EVOID
- EVOID architecture docs: https://deepwiki.com/EvolveBeyond/EVOID
- EVOID documentation: https://evolvebeyond.github.io/EVOID/

---

**Recorded**: 2026-10-18  
**Status**: Permanent — do not remove.
