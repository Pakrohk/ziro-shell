"""ziro-shell — analysis cache with hash invalidation.

Layer: 3 (Python core, cold-path only)
Spec: 001 FR-006d (drift detection)

Cache lives under ~/.cache/ziro/analysis/<plugin>.json.
If any source file changes (mtime+size), the hash changes and the cache
is invalidated on the next analyze_with_cache() call.

Cache failures are non-fatal — callers always fall back to a fresh analysis.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Optional

from core.models import AnalysisResult


ANALYZER_VERSION = "0.1.0"


def _iter_source_files(plugin_dir: Path) -> list[Path]:
    """All .zsh / .plugin.zsh files, sorted for determinism."""
    files: list[Path] = []
    for pattern in ("**/*.plugin.zsh", "**/*.zsh"):
        files.extend(p for p in plugin_dir.glob(pattern) if p.is_file())
    return sorted(set(files))


def compute_source_hash(plugin_dir: Path) -> str:
    """Hash of (file path, mtime, size) for all source files.

    Used for cache invalidation: if any source file changes,
    hash changes and cache is invalidated.
    """
    h = hashlib.sha256()
    h.update(f"analyzer={ANALYZER_VERSION}\n".encode())

    for path in _iter_source_files(plugin_dir):
        try:
            stat = path.stat()
            rel = path.relative_to(plugin_dir)
            h.update(f"{rel}|{int(stat.st_mtime)}|{stat.st_size}\n".encode())
        except OSError:
            continue

    return h.hexdigest()


def cache_dir() -> Path:
    """Return ~/.cache/ziro/analysis/, creating if needed."""
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    out = base / "ziro" / "analysis"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _cache_file(plugin_name: str) -> Path:
    safe = plugin_name.replace("/", "__")
    return cache_dir() / f"{safe}.json"


def load_cached(plugin_name: str, source_hash: str) -> Optional[AnalysisResult]:
    """Return cached AnalysisResult if hash matches, else None."""
    path = _cache_file(plugin_name)
    if not path.is_file():
        return None

    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    if data.get("source_hash") != source_hash:
        return None

    # Reconstruct AnalysisResult from Schema A
    from core.models import DetectedSignals, Recommendation, Strategy
    try:
        detected = DetectedSignals(
            hooks=tuple(data["detected"]["hooks"]),
            zle_widgets=data["detected"]["zle_widgets"],
            compdef=data["detected"]["compdef"],
            bindkey=data["detected"]["bindkey"],
            eval_commands=tuple(data["detected"].get("eval_commands", [])),
            modifies_path=data["detected"].get("modifies_path", False),
            is_prompt=data["detected"].get("is_prompt", False),
        )
        recommended = Recommendation(
            strategy=Strategy(data["recommended"]["strategy"]),
            compile=data["recommended"].get("compile", True),
            eval_cache=data["recommended"].get("eval_cache", False),
            pick=data["recommended"].get("pick", ""),
            stage=data["recommended"].get("stage", 5),
            slot=data["recommended"].get("slot", "b"),
            name=data["recommended"].get("name", ""),
            depends=tuple(data["recommended"].get("depends", ())),
            condition=data["recommended"].get("condition"),
            on_key=data["recommended"].get("on_key"),
            cache_type=data["recommended"].get("cache_type", "none"),
            timeout_ms=data["recommended"].get("timeout_ms"),
        )
        return AnalysisResult(
            plugin=data["plugin"],
            source=data["source"],
            detected=detected,
            recommended=recommended,
            confidence=data.get("confidence", 0.0),
            analyzed_at=data.get("analyzed_at", ""),
            analyzer_version=data.get("analyzer_version", ANALYZER_VERSION),
        )
    except (KeyError, ValueError):
        return None


def store_cached(plugin_name: str, source_hash: str, result: AnalysisResult) -> None:
    """Write AnalysisResult to cache with source_hash."""
    path = _cache_file(plugin_name)
    payload = {"source_hash": source_hash, **result.to_dict()}
    try:
        path.write_text(json.dumps(payload, indent=2))
    except OSError:
        pass  # cache failure is non-fatal


def clear_cache(plugin_name: Optional[str] = None) -> None:
    """Clear cache for one plugin, or all if None."""
    if plugin_name is None:
        for f in cache_dir().glob("*.json"):
            try:
                f.unlink()
            except OSError:
                pass
    else:
        try:
            _cache_file(plugin_name).unlink()
        except OSError:
            pass


__all__ = [
    "compute_source_hash",
    "cache_dir",
    "load_cached",
    "store_cached",
    "clear_cache",
]
