"""External Tools Observability Layer.

Layer: 3 (Python core, cold-path only)
Spec: 038 (External Tools Observability — read-only aggregator)

Discovers, reads, aggregates metrics from ~/.cache/ziro/<tool>/metrics.jsonl
and health status from ~/.cache/ziro/<tool>/health.json or plugin manifests.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Optional


def _get_cache_dir() -> Path:
    """Return ~/.cache/ziro path respecting XDG_CACHE_HOME."""
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache) / "ziro"
    return Path.home() / ".cache" / "ziro"


def discover_tools() -> list[str]:
    """Scan ~/.cache/ziro/*/metrics.jsonl and return list of discovered tool names.

    Does not hardcode tool names. Returns empty list if no metrics.jsonl exist.
    """
    cache_root = _get_cache_dir()
    if not cache_root.is_dir():
        return []

    tools: list[str] = []
    try:
        for entry in sorted(cache_root.iterdir()):
            if entry.is_dir() and (entry / "metrics.jsonl").is_file():
                tools.append(entry.name)
    except OSError:
        return []
    return tools


def supported_tools() -> list[str]:
    """Return list of known and discovered tools."""
    discovered = set(discover_tools())
    discovered.add("ghost")
    return sorted(discovered)


def read_metrics(
    tool: str,
    since_seconds: Optional[float] = None,
    max_lines: int = 10000,
) -> list[dict[str, Any]]:
    """Read metrics from ~/.cache/ziro/<tool>/metrics.jsonl.

    Skips malformed lines gracefully without crashing.
    Filters by since_seconds if provided (ts >= now - since_seconds).
    Returns list of parsed metric dicts.
    """
    metrics_file = _get_cache_dir() / tool / "metrics.jsonl"
    if not metrics_file.is_file():
        return []

    cutoff = (time.time() - since_seconds) if since_seconds and since_seconds > 0 else 0.0

    lines: list[str] = []
    try:
        with open(metrics_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return []

    if max_lines and len(lines) > max_lines:
        lines = lines[-max_lines:]

    records: list[dict[str, Any]] = []
    skipped_count = 0

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
            if not isinstance(item, dict):
                skipped_count += 1
                continue
            ts = item.get("ts", 0)
            if cutoff > 0 and isinstance(ts, (int, float)) and ts < cutoff:
                continue
            records.append(item)
        except Exception:
            skipped_count += 1
            continue

    return records


def aggregate(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate stats from a list of metric dicts.

    Returns dict with {total, error_count, error_rate, p50, p95, p99, cache_hit_rate,
    by_intent: {name: {count, p50, p95, p99, errors, cache_hits}},
    by_level: {ephemeral: N, standard: N, critical: N},
    last_ts: float}.
    """
    total = len(metrics)
    if total == 0:
        return {
            "total": 0,
            "error_count": 0,
            "error_rate": 0.0,
            "p50": 0.0,
            "p95": 0.0,
            "p99": 0.0,
            "cache_hit_rate": 0.0,
            "by_intent": {},
            "by_level": {"ephemeral": 0, "standard": 0, "critical": 0},
            "last_ts": None,
        }

    durations: list[float] = []
    errors = 0
    cache_hits = 0
    by_level = {"ephemeral": 0, "standard": 0, "critical": 0}
    by_intent: dict[str, dict[str, Any]] = {}
    intent_durs: dict[str, list[float]] = {}
    last_ts: Optional[float] = None

    for m in metrics:
        dur = float(m.get("duration_ms", 0.0) or 0.0)
        durations.append(dur)

        ts = m.get("ts")
        if isinstance(ts, (int, float)):
            if last_ts is None or ts > last_ts:
                last_ts = float(ts)

        status = m.get("status", "ok")
        is_err = status != "ok"
        if is_err:
            errors += 1

        hit = bool(m.get("cache_hit", False))
        if hit:
            cache_hits += 1

        lvl = m.get("level", "ephemeral")
        if lvl in by_level:
            by_level[lvl] += 1
        else:
            by_level[lvl] = 1

        name = m.get("name", "unknown")
        if name not in by_intent:
            by_intent[name] = {"count": 0, "errors": 0, "cache_hits": 0, "p50": 0.0, "p95": 0.0, "p99": 0.0}
            intent_durs[name] = []
        by_intent[name]["count"] += 1
        if is_err:
            by_intent[name]["errors"] += 1
        if hit:
            by_intent[name]["cache_hits"] += 1
        intent_durs[name].append(dur)

    def _calc_percentiles(durs: list[float]) -> tuple[float, float, float]:
        if not durs:
            return 0.0, 0.0, 0.0
        sorted_d = sorted(durs)
        n = len(sorted_d)
        i50 = min(n - 1, max(0, int(n * 0.50)))
        i95 = min(n - 1, max(0, int(n * 0.95)))
        i99 = min(n - 1, max(0, int(n * 0.99)))
        return round(sorted_d[i50], 2), round(sorted_d[i95], 2), round(sorted_d[i99], 2)

    p50, p95, p99 = _calc_percentiles(durations)

    for iname, dlist in intent_durs.items():
        ip50, ip95, ip99 = _calc_percentiles(dlist)
        by_intent[iname]["p50"] = ip50
        by_intent[iname]["p95"] = ip95
        by_intent[iname]["p99"] = ip99

    return {
        "total": total,
        "error_count": errors,
        "error_rate": round(errors / total, 4),
        "p50": p50,
        "p95": p95,
        "p99": p99,
        "cache_hit_rate": round(cache_hits / total, 4),
        "by_intent": by_intent,
        "by_level": by_level,
        "last_ts": last_ts,
    }


def read_health(tool: str) -> Optional[dict[str, Any]]:
    """Read health status for a tool using Protocol v1.

    Sources checked in priority order:
    1. ~/.cache/ziro/<tool>/health.json (if present, static snapshot)
    2. Manifest [health] command in ~/.local/share/ziro/vendor/<tool>/ziro-plugin.toml
       or ~/.config/ziro/plugins/<tool>/ziro-plugin.toml (if command declared, run with 5s timeout)
    3. None (tool does not implement health protocol)
    """
    cache_dir = _get_cache_dir()
    health_json = cache_dir / tool / "health.json"
    if health_json.is_file():
        try:
            with open(health_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass

    # Check for plugin manifest
    manifest_paths = [
        Path.home() / ".local" / "share" / "ziro" / "vendor" / tool / "ziro-plugin.toml",
        Path.home() / ".config" / "ziro" / "plugins" / tool / "ziro-plugin.toml",
    ]
    for mp in manifest_paths:
        if mp.is_file():
            cmd = _parse_manifest_health_command(mp)
            if cmd:
                try:
                    res = subprocess.run(
                        cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if res.returncode == 0 and res.stdout.strip():
                        try:
                            data = json.loads(res.stdout.strip())
                            if isinstance(data, dict):
                                return data
                        except Exception:
                            return {"status": "ok", "message": res.stdout.strip()}
                    return {
                        "status": "error" if res.returncode != 0 else "warn",
                        "message": res.stderr.strip() or res.stdout.strip() or f"exit code {res.returncode}",
                    }
                except subprocess.TimeoutExpired:
                    return {"status": "error", "message": "health check timed out after 5s"}
                except Exception as e:
                    return {"status": "error", "message": f"failed to execute health check: {e}"}

    return None


def _parse_manifest_health_command(manifest_path: Path) -> Optional[str]:
    """Parse health command from a ziro-plugin.toml file without external dependencies."""
    try:
        in_health = False
        with open(manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("[") and line.endswith("]"):
                    in_health = line.strip("[]").strip() == "health"
                    continue
                if in_health and line.startswith("command"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        return parts[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return None
