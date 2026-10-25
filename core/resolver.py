"""ziro-shell — Tag resolver (Layer 2).

Merges Layer 1 analysis with user tags → final config.
Layer: 3 (Python core, cold-path only)
Spec: 003 v0.2.0 (Defer v2 slot/stage mapping + cross-stage validation)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from core.models import AnalysisResult, Recommendation, Strategy
from core.tags import Tag, load_all_tags, load_plugin_tags


class ConflictError(Exception):
    """Raised when tags conflict irreconcilably."""


@dataclass(frozen=True)
class ResolvedConfig:
    plugin: str
    strategy: Strategy
    compile: bool = True
    eval_cache: bool = False
    pick: str = ""
    defer_slot: str = ""
    raw: str = ""
    applied_tags: tuple[str, ...] = ()
    stage: int = 5
    slot: str = "b"
    name: str = ""
    depends: tuple[str, ...] = ()
    condition: Optional[str] = None
    on_key: Optional[str] = None
    cache_type: str = "none"
    timeout_ms: Optional[int] = None


def _apply_tag(rec: Recommendation, tag: Tag) -> Recommendation:
    if tag.name == "@compdef":
        return Recommendation(
            strategy=Strategy.EAGER,
            compile=rec.compile,
            eval_cache=rec.eval_cache,
            pick=rec.pick,
            adapter_options=rec.adapter_options,
            stage=2,
            slot="a",
            name=rec.name,
            depends=rec.depends,
            condition=rec.condition,
            on_key=rec.on_key,
            cache_type="none",
            timeout_ms=rec.timeout_ms,
        )
    if tag.name == "@eager":
        return Recommendation(
            strategy=Strategy.EAGER,
            compile=rec.compile,
            eval_cache=rec.eval_cache,
            pick=rec.pick,
            adapter_options=rec.adapter_options,
            stage=4,
            slot="a",
            name=rec.name,
            depends=rec.depends,
            condition=rec.condition,
            on_key=rec.on_key,
            cache_type=rec.cache_type,
            timeout_ms=rec.timeout_ms,
        )
    if tag.name in ("@lazy", "@after-prompt"):
        st = 5 if tag.name == "@lazy" else 5
        sl = "b" if tag.name == "@lazy" else "c"
        return Recommendation(
            strategy=Strategy.AFTER_PROMPT,
            compile=rec.compile,
            eval_cache=rec.eval_cache,
            pick=rec.pick,
            adapter_options=rec.adapter_options,
            stage=st,
            slot=sl,
            name=rec.name,
            depends=rec.depends,
            condition=rec.condition,
            on_key=rec.on_key,
            cache_type=rec.cache_type,
            timeout_ms=rec.timeout_ms,
        )
    if tag.name == "@no-compile":
        return Recommendation(
            strategy=rec.strategy,
            compile=False,
            eval_cache=rec.eval_cache,
            pick=rec.pick,
            adapter_options=rec.adapter_options,
            stage=rec.stage,
            slot=rec.slot,
            name=rec.name,
            depends=rec.depends,
            condition=rec.condition,
            on_key=rec.on_key,
            cache_type=rec.cache_type,
            timeout_ms=rec.timeout_ms,
        )
    if tag.name == "@eval-cache":
        return Recommendation(
            strategy=rec.strategy,
            compile=rec.compile,
            eval_cache=True,
            pick=rec.pick,
            adapter_options=rec.adapter_options,
            stage=4,
            slot="a",
            name=rec.name,
            depends=rec.depends,
            condition=rec.condition,
            on_key=rec.on_key,
            cache_type="eval_output",
            timeout_ms=rec.timeout_ms,
        )
    return rec


def validate_cross_stage(plugins: dict[str, Any] | list[ResolvedConfig]) -> Any:
    """Validate cross-stage dependencies (Spec 001 §Hidden Risks R1).

    If plugin A depends on B, stage(A) MUST be >= stage(B).
    If stage(A) < stage(B), elevates stage(A) = stage(B).
    """
    if isinstance(plugins, dict):
        changed = True
        while changed:
            changed = False
            for name, strat in plugins.items():
                deps = getattr(strat, "depends", ())
                cur_stage = getattr(strat, "stage", 5)
                for dep in deps:
                    if dep in plugins:
                        dep_stage = getattr(plugins[dep], "stage", 5)
                        if cur_stage < dep_stage:
                            strat.stage = dep_stage
                            changed = True
        return plugins

    # list of ResolvedConfig
    stage_map = {c.name or c.plugin: c.stage for c in plugins}
    updated = list(plugins)
    changed = True
    while changed:
        changed = False
        for i, cfg in enumerate(updated):
            for dep in cfg.depends:
                dep_stage = stage_map.get(dep)
                if dep_stage is not None and cfg.stage < dep_stage:
                    cfg_elevated = ResolvedConfig(
                        plugin=cfg.plugin,
                        strategy=cfg.strategy,
                        compile=cfg.compile,
                        eval_cache=cfg.eval_cache,
                        pick=cfg.pick,
                        defer_slot=cfg.defer_slot,
                        raw=cfg.raw,
                        applied_tags=cfg.applied_tags,
                        stage=dep_stage,
                        slot=cfg.slot,
                        name=cfg.name,
                        depends=cfg.depends,
                        condition=cfg.condition,
                        on_key=cfg.on_key,
                        cache_type=cfg.cache_type,
                        timeout_ms=cfg.timeout_ms,
                    )
                    updated[i] = cfg_elevated
                    stage_map[cfg.name or cfg.plugin] = dep_stage
                    changed = True
    return updated


def resolve(
    analysis: AnalysisResult,
    config_dir: Path,
    *,
    raise_on_conflict: bool = False,
) -> ResolvedConfig:
    """Merge analysis + tags → ResolvedConfig.

    Args:
        analysis: Layer 1 output
        config_dir: ~/.config/ziro/
        raise_on_conflict: if True, raise ConflictError; else, last tag wins
    """
    all_tags = load_all_tags(config_dir)
    plugin_tags = load_plugin_tags(config_dir, analysis.plugin)

    # Conflict detection (Spec 003 R4)
    names_set = set(plugin_tags)
    if "@eager" in names_set and "@lazy" in names_set:
        if raise_on_conflict:
            raise ConflictError(
                f"Plugin {analysis.plugin!r}: @eager and @lazy conflict"
            )
    if "@compdef" in names_set and "@lazy" in names_set:
        if raise_on_conflict:
            raise ConflictError(
                f"Plugin {analysis.plugin!r}: @compdef cannot be @lazy"
            )

    # Sort by priority (higher first)
    def prio(name: str) -> int:
        t = all_tags.get(name)
        return t.priority if t else -1

    sorted_tags = sorted(plugin_tags, key=prio, reverse=True)

    rec = analysis.recommended
    for name in sorted_tags:
        tag = all_tags.get(name)
        if tag is not None:
            rec = _apply_tag(rec, tag)

    resolved_slot = ""
    for name in sorted_tags:
        t = all_tags.get(name)
        if t and t.defer_slot and t.defer_slot in ("a", "b", "c"):
            resolved_slot = t.defer_slot
            break

    return ResolvedConfig(
        plugin=analysis.plugin,
        strategy=rec.strategy,
        compile=rec.compile,
        eval_cache=rec.eval_cache,
        pick=rec.pick,
        defer_slot=resolved_slot or rec.slot,
        applied_tags=tuple(sorted_tags),
        stage=rec.stage,
        slot=resolved_slot or rec.slot,
        name=rec.name or analysis.plugin,
        depends=rec.depends,
        condition=rec.condition,
        on_key=rec.on_key,
        cache_type=rec.cache_type,
        timeout_ms=rec.timeout_ms,
    )


__all__ = ["resolve", "ResolvedConfig", "ConflictError", "validate_cross_stage"]
