"""ziro-shell — ziro_load: frozen interface (Layer 3).

Layer: 3 (znap Runtime)
Spec: 002 R1 (frozen contract)

This module produces the ZSH syntax that plugins.gen.zsh will emit.
It is pure-function emitter — no I/O, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Strategy = Literal["eager", "after-prompt", "lazy", "raw"]


@dataclass(frozen=True)
class LoadSpec:
    """Frozen representation of single plugin load request.

    Mirrors ziro_load interface (Spec 002 R1).
    """
    plugin: str
    strategy: Strategy = "eager"
    sub_slot: str = ""
    lazy_by_function: str = ""
    compile: bool = True
    pick: str = ""
    atinit: str = ""
    atload: str = ""
    notify: str = ""
    lucid: bool = False
    reset_prompt: bool = False
    eval_cache: str = ""
    raw: str = ""
    is_local: bool = False
    stage: int = 5
    slot: str = "b"
    name: str = ""
    depends: tuple[str, ...] = ()
    condition: Optional[str] = None
    on_key: Optional[str] = None
    cache_type: str = "none"
    timeout_ms: Optional[int] = None

    def __post_init__(self) -> None:
        if self.sub_slot and self.sub_slot in ("a", "b", "c", "d"):
            object.__setattr__(self, "slot", self.sub_slot)
        if not self.name and self.plugin:
            try:
                from core.analyzer import slug
                object.__setattr__(self, "name", slug(self.plugin))
            except Exception:
                base = self.plugin.rstrip("/").split("/")[-1]
                object.__setattr__(self, "name", base)


def emit_eager(spec: LoadSpec) -> str:
    """Emit znap source line for eager plugins."""
    if spec.eval_cache:
        return f"znap eval {spec.plugin} '{spec.eval_cache}'"
    if spec.is_local or spec.plugin.startswith(("$ZIRO_HOME/", "~/.ziro/", "plugins/")):
        return f"ziro local source {spec.plugin}"
    if spec.pick:
        return f"znap source {spec.plugin} --pick={spec.pick}"
    return f"znap source {spec.plugin}"


def emit_deferred(spec: LoadSpec) -> str:
    """Emit ziro-defer-wrapped znap source for deferred plugins (Defer v2)."""
    if spec.is_local or spec.plugin.startswith(("$ZIRO_HOME/", "~/.ziro/", "plugins/")):
        inner = f"ziro local source {spec.plugin}"
    elif spec.pick:
        inner = f"znap source {spec.plugin} --pick={spec.pick}"
    else:
        inner = f"znap source {spec.plugin}"

    if spec.on_key:
        return f"ziro-defer-bind-widget '{spec.on_key}' '{inner}'"

    slug_or_name = spec.name
    if not slug_or_name and spec.plugin:
        try:
            from core.analyzer import slug
            slug_or_name = slug(spec.plugin)
        except Exception:
            slug_or_name = spec.plugin.rstrip("/").split("/")[-1]

    parts: list[str] = [
        "ziro-defer",
        f"--stage={spec.stage}",
        f"--slot={spec.slot}",
    ]
    if slug_or_name:
        parts.append(f"--name={slug_or_name}")
    if spec.depends:
        dep_str = " ".join(spec.depends)
        parts.append(f'--depends="{dep_str}"')
    if spec.condition:
        cond = spec.condition if spec.condition.startswith("if-") else f"if-{spec.condition}"
        parts.append(f"--{cond}")
    if spec.timeout_ms:
        parts.append(f"--timeout={spec.timeout_ms}")
    if spec.lazy_by_function:
        parts.append(f'--lazy-by-function="{spec.lazy_by_function}"')
    if spec.atinit:
        parts.append(f'--atinit="{spec.atinit}"')
    if spec.atload:
        parts.append(f'--atload="{spec.atload}"')

    parts.append(inner)
    return " ".join(parts)


def emit_raw(spec: LoadSpec) -> str:
    """Emit raw syntax verbatim (escape hatch, Spec 002 R1)."""
    return spec.raw


def emit(spec: LoadSpec) -> str:
    """Emit zsh line for a LoadSpec — dispatches by strategy."""
    if spec.raw:
        return emit_raw(spec)
    if spec.strategy == "eager":
        return emit_eager(spec)
    if spec.strategy in ("after-prompt", "lazy"):
        return emit_deferred(spec)
    return emit_eager(spec)  # safe fallback


def from_resolved(
    plugin: str,
    strategy: str,
    *,
    compile_: bool = True,
    eval_cache: bool = False,
    pick: str = "",
    defer_slot: str = "",
    raw: str = "",
    is_local: bool = False,
    stage: int = 5,
    slot: str = "b",
    name: str = "",
    depends: tuple[str, ...] = (),
    condition: Optional[str] = None,
    on_key: Optional[str] = None,
    cache_type: str = "none",
    timeout_ms: Optional[int] = None,
) -> LoadSpec:
    """Build LoadSpec from ResolvedConfig fields.

    Maps ResolvedConfig.strategy to LoadSpec.strategy:
    EAGER -> eager
    AFTER_PROMPT -> after-prompt
    LAZY -> lazy
    """
    strategy_lower = strategy.lower().replace("_", "-")
    if strategy_lower not in ("eager", "after-prompt", "lazy"):
        strategy_lower = "eager"  # safe fallback

    resolved_slot = defer_slot if defer_slot in ("a", "b", "c", "d") else slot

    return LoadSpec(
        plugin=plugin,
        strategy=strategy_lower,  # type: ignore[arg-type]
        sub_slot=defer_slot if defer_slot in ("a", "b", "c") else "",
        compile=compile_,
        pick=pick,
        eval_cache=(f"{plugin} init" if eval_cache else ""),
        raw=raw,
        is_local=is_local,
        stage=stage,
        slot=resolved_slot,
        name=name,
        depends=tuple(depends) if isinstance(depends, (list, tuple)) else (),
        condition=condition,
        on_key=on_key,
        cache_type=cache_type,
        timeout_ms=timeout_ms,
    )


__all__ = [
    "LoadSpec",
    "emit",
    "emit_eager",
    "emit_deferred",
    "emit_raw",
    "from_resolved",
]
