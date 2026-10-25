"""ziro-shell — data models for Layer 1 analyzer.

Layer: 3 (Python core, cold-path only)
Spec: 001 v0.2.0 + Spec 000 Schema A v0.2.0
Schema: A (analysis output)

These dataclasses are the stable contract between the Layer 1 analyzer
(Python, cold-path) and the zsh runtime adapters. The frozen design makes
results hashable and safe to cache on disk as JSON (see AnalysisResult.to_dict).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


ANALYZER_VERSION = "0.2.0"


class Strategy(str):
    """Load strategy recommendation with Defer v2 dimensions.

    Backward compatible with legacy Strategy Enum members:
    Strategy.EAGER, Strategy.AFTER_PROMPT, Strategy.AT_PROMPT, Strategy.LAZY.
    """

    EAGER: Strategy
    AFTER_PROMPT: Strategy
    AT_PROMPT: Strategy
    LAZY: Strategy

    def __new__(
        cls,
        value: str | Strategy | None = None,
        *,
        stage: Optional[int] = None,
        slot: Optional[str] = None,
        name: str = "",
        depends: tuple[str, ...] = (),
        condition: Optional[str] = None,
        on_key: Optional[str] = None,
        cache_type: str = "none",
        timeout_ms: Optional[int] = None,
        **kwargs: Any,
    ) -> Strategy:
        if value is not None and isinstance(value, (str, Strategy)):
            val_str = str(value)
            if stage is None:
                stage = 4 if val_str == "eager" else (5 if val_str in ("after-prompt", "at-prompt") else 6)
            if slot is None:
                slot = "a" if val_str == "eager" else ("b" if val_str in ("after-prompt", "at-prompt") else "c")
        else:
            val_str = "eager" if kwargs.get("eager") else (str(value) if value is not None else "eager")
            if stage is None:
                stage = 5
            if slot is None:
                slot = "b"

        obj = super().__new__(cls, val_str)
        obj.stage = stage
        obj.slot = slot
        obj.name = name
        obj.depends = tuple(depends) if isinstance(depends, (list, tuple)) else ()
        obj.condition = condition
        obj.on_key = on_key
        obj.cache_type = cache_type
        obj.timeout_ms = timeout_ms
        return obj

    @property
    def value(self) -> str:
        return str(self)

    @property
    def strategy_name(self) -> str:
        if 1 <= self.stage <= 4:
            return "eager"
        if self.stage == 5:
            return "after-prompt"
        if self.stage >= 6:
            return "lazy"
        return "eager"


Strategy.EAGER = Strategy("eager", stage=4, slot="a")
Strategy.AFTER_PROMPT = Strategy("after-prompt", stage=5, slot="b")
Strategy.AT_PROMPT = Strategy("at-prompt", stage=5, slot="b")
Strategy.LAZY = Strategy("lazy", stage=6, slot="c")


@dataclass(frozen=True)
class DetectedSignals:
    """Raw signals detected in plugin source."""
    hooks: tuple[str, ...] = ()  # precmd, preexec, chpwd
    zle_widgets: bool = False
    compdef: bool = False
    bindkey: bool = False
    eval_commands: tuple[str, ...] = ()
    modifies_path: bool = False
    is_prompt: bool = False

    def has_any(self) -> bool:
        return bool(
            self.hooks or self.zle_widgets or self.compdef
            or self.bindkey or self.eval_commands
            or self.modifies_path or self.is_prompt
        )


@dataclass(frozen=True)
class Recommendation:
    """Recommended load strategy (Defer v2 dimensions + legacy compatibility)."""
    strategy: Strategy = Strategy.EAGER
    compile: bool = True
    eval_cache: bool = False
    adapter_options: tuple[str, ...] = ()
    pick: str = ""
    stage: int = 5
    slot: str = "b"
    name: str = ""
    depends: tuple[str, ...] = ()
    condition: Optional[str] = None
    on_key: Optional[str] = None
    cache_type: str = "none"
    timeout_ms: Optional[int] = None


@dataclass(frozen=True)
class AnalysisResult:
    """Schema A (v0.2.0) — output of Layer 1 analysis."""
    plugin: str
    source: str
    detected: DetectedSignals
    recommended: Recommendation
    confidence: float = 0.0
    analyzed_at: str = ""
    analyzer_version: str = ANALYZER_VERSION
    trust_score: int | None = None
    trust_level: str | None = None
    security_notes: list[str] = field(default_factory=list)
    blocked: bool = False
    override_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize to Schema A JSON."""
        return {
            "plugin": self.plugin,
            "source": self.source,
            "detected": {
                "hooks": list(self.detected.hooks),
                "zle_widgets": self.detected.zle_widgets,
                "compdef": self.detected.compdef,
                "bindkey": self.detected.bindkey,
                "eval_commands": list(self.detected.eval_commands),
                "modifies_path": self.detected.modifies_path,
                "is_prompt": self.detected.is_prompt,
            },
            "recommended": {
                "stage": getattr(self.recommended, "stage", 5),
                "slot": getattr(self.recommended, "slot", "b"),
                "name": getattr(self.recommended, "name", ""),
                "depends": list(getattr(self.recommended, "depends", ())),
                "condition": getattr(self.recommended, "condition", None),
                "on_key": getattr(self.recommended, "on_key", None),
                "cache_type": getattr(self.recommended, "cache_type", "none"),
                "timeout_ms": getattr(self.recommended, "timeout_ms", None),
                "strategy": self.recommended.strategy.value if hasattr(self.recommended.strategy, "value") else str(self.recommended.strategy),
                "compile": self.recommended.compile,
                "eval_cache": self.recommended.eval_cache,
                "adapter_options": list(self.recommended.adapter_options),
                "pick": self.recommended.pick,
            },
            "confidence": self.confidence,
            "analyzed_at": self.analyzed_at,
            "analyzer_version": self.analyzer_version,
            "trust_score": self.trust_score,
            "trust_level": self.trust_level,
            "security_notes": list(self.security_notes) if self.security_notes else [],
            "blocked": self.blocked,
            "override_required": self.override_required,
        }

    @staticmethod
    def empty(plugin: str, source: str = "") -> "AnalysisResult":
        """Safe fallback — unknown plugin → eager."""
        return AnalysisResult(
            plugin=plugin,
            source=source,
            detected=DetectedSignals(),
            recommended=Recommendation(strategy=Strategy.EAGER, stage=4, slot="a"),
            confidence=0.0,
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            analyzer_version=ANALYZER_VERSION,
            trust_score=None,
            trust_level="unknown",
            security_notes=[],
            blocked=False,
            override_required=False,
        )
