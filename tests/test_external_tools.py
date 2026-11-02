"""Tests for External Tools Observability Layer (Spec 038).

Tests discovery, reading, aggregation, health checking, CLI stats, CLI health,
and doctor integration with full hermetic isolation via tmp_path and monkeypatch.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from core import doctor_cli, external_tools, health_cli, stats_cli


@pytest.fixture
def mock_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Fixture that isolates ~/.cache/ziro inside tmp_path."""
    cache_root = tmp_path / "cache" / "ziro"
    cache_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setattr(external_tools, "_get_cache_dir", lambda: cache_root)
    return cache_root


def test_discover_tools_no_metrics(mock_cache_dir: Path) -> None:
    """Empty cache directory discovers no tools."""
    tools = external_tools.discover_tools()
    assert tools == []


def test_discover_tools_finds_ghost(mock_cache_dir: Path) -> None:
    """Discover tools that have a metrics.jsonl file."""
    ghost_dir = mock_cache_dir / "ghost"
    ghost_dir.mkdir()
    (ghost_dir / "metrics.jsonl").write_text('{"ts": 1.0}\n', encoding="utf-8")

    other_dir = mock_cache_dir / "custom"
    other_dir.mkdir()
    (other_dir / "metrics.jsonl").write_text('{"ts": 2.0}\n', encoding="utf-8")

    empty_tool = mock_cache_dir / "empty"
    empty_tool.mkdir()

    tools = external_tools.discover_tools()
    assert sorted(tools) == ["custom", "ghost"]


def test_read_metrics_valid(mock_cache_dir: Path) -> None:
    """Parse valid NDJSON records."""
    ghost_dir = mock_cache_dir / "ghost"
    ghost_dir.mkdir()
    lines = [
        json.dumps({"ts": 100.0, "name": "query", "duration_ms": 0.5, "status": "ok", "cache_hit": True}),
        json.dumps({"ts": 101.0, "name": "query", "duration_ms": 1.2, "status": "ok", "cache_hit": False}),
        json.dumps({"ts": 102.0, "name": "query", "duration_ms": 2.0, "status": "error", "cache_hit": False}),
    ]
    (ghost_dir / "metrics.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    metrics = external_tools.read_metrics("ghost")
    assert len(metrics) == 3
    assert metrics[0]["duration_ms"] == 0.5
    assert metrics[1]["cache_hit"] is False
    assert metrics[2]["status"] == "error"


def test_read_metrics_skips_malformed(mock_cache_dir: Path) -> None:
    """Gracefully skip corrupt or invalid JSON lines without raising exceptions."""
    ghost_dir = mock_cache_dir / "ghost"
    ghost_dir.mkdir()
    lines = [
        '{"ts": 100.0, "name": "valid1", "duration_ms": 0.5}',
        'THIS IS NOT JSON',
        '{"partial":',
        '{"ts": 101.0, "name": "valid2", "duration_ms": 1.0}',
        "",
        "   ",
    ]
    (ghost_dir / "metrics.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    metrics = external_tools.read_metrics("ghost")
    assert len(metrics) == 2
    assert metrics[0]["name"] == "valid1"
    assert metrics[1]["name"] == "valid2"


def test_read_metrics_since_filter(mock_cache_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Filter records by since_seconds relative to current time."""
    now = 1000000.0
    monkeypatch.setattr(external_tools.time, "time", lambda: now)

    ghost_dir = mock_cache_dir / "ghost"
    ghost_dir.mkdir()
    lines = [
        json.dumps({"ts": now - 7200, "name": "2h_old"}),
        json.dumps({"ts": now - 3601, "name": "1h1s_old"}),
        json.dumps({"ts": now - 1800, "name": "30m_old"}),
        json.dumps({"ts": now - 60, "name": "1m_old"}),
    ]
    (ghost_dir / "metrics.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Filter past 1 hour (3600 seconds)
    metrics = external_tools.read_metrics("ghost", since_seconds=3600)
    assert len(metrics) == 2
    assert [m["name"] for m in metrics] == ["30m_old", "1m_old"]


def test_aggregate_basic() -> None:
    """Compute aggregate percentiles and distributions from known duration lists."""
    metrics: list[dict[str, Any]] = []
    # 100 items with durations 1 to 100
    for i in range(1, 101):
        metrics.append({
            "ts": 1000.0 + i,
            "name": "ghost.suggest",
            "duration_ms": float(i),
            "status": "ok",
            "cache_hit": True,
            "level": "ephemeral",
        })

    agg = external_tools.aggregate(metrics)
    assert agg["total"] == 100
    assert agg["error_count"] == 0
    assert agg["error_rate"] == 0.0
    assert agg["cache_hit_rate"] == 1.0
    assert agg["p50"] == 51.0
    assert agg["p95"] == 96.0
    assert agg["p99"] == 100.0
    assert agg["by_level"]["ephemeral"] == 100
    assert "ghost.suggest" in agg["by_intent"]


def test_aggregate_errors() -> None:
    """Validate error rate and error count computation."""
    metrics = [
        {"duration_ms": 1.0, "status": "ok"},
        {"duration_ms": 2.0, "status": "error"},
        {"duration_ms": 3.0, "status": "timeout"},
        {"duration_ms": 4.0, "status": "ok"},
    ]
    agg = external_tools.aggregate(metrics)
    assert agg["total"] == 4
    assert agg["error_count"] == 2
    assert agg["error_rate"] == 0.5


def test_aggregate_cache_hit() -> None:
    """Validate cache hit rate computation."""
    metrics = [
        {"duration_ms": 1.0, "cache_hit": True},
        {"duration_ms": 2.0, "cache_hit": False},
        {"duration_ms": 3.0, "cache_hit": True},
        {"duration_ms": 4.0, "cache_hit": True},
    ]
    agg = external_tools.aggregate(metrics)
    assert agg["total"] == 4
    assert agg["cache_hit_rate"] == 0.75


def test_aggregate_empty() -> None:
    """Empty metric list returns zeroed aggregate structure without error."""
    agg = external_tools.aggregate([])
    assert agg["total"] == 0
    assert agg["p50"] == 0.0
    assert agg["error_count"] == 0
    assert agg["by_intent"] == {}


def test_read_health_no_protocol(mock_cache_dir: Path) -> None:
    """Tool with no health.json and no manifest returns None."""
    res = external_tools.read_health("unknown_tool")
    assert res is None


def test_read_health_from_json(mock_cache_dir: Path) -> None:
    """Read health status from ~/.cache/ziro/<tool>/health.json."""
    tool_dir = mock_cache_dir / "ghost"
    tool_dir.mkdir()
    health_data = {
        "status": "ok",
        "message": "All 8 checks passed",
        "checks": [{"name": "cache_dir", "status": "ok"}],
    }
    (tool_dir / "health.json").write_text(json.dumps(health_data), encoding="utf-8")

    res = external_tools.read_health("ghost")
    assert res is not None
    assert res["status"] == "ok"
    assert res["message"] == "All 8 checks passed"
    assert len(res["checks"]) == 1


def test_read_health_command_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Manifest declaring a slow health command times out safely."""
    vendor_dir = tmp_path / ".local" / "share" / "ziro" / "vendor" / "slowtool"
    vendor_dir.mkdir(parents=True)
    (vendor_dir / "ziro-plugin.toml").write_text(
        '[plugin]\nname = "slowtool"\n\n[health]\ncommand = "sleep 10"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    res = external_tools.read_health("slowtool")
    assert res is not None
    assert res["status"] == "error"
    assert "timed out" in res["message"]


def test_stats_cli_text_output(mock_cache_dir: Path, capsys: pytest.CaptureFixture) -> None:
    """CLI text output formats stats clearly."""
    tool_dir = mock_cache_dir / "ghost"
    tool_dir.mkdir()
    (tool_dir / "metrics.jsonl").write_text(
        json.dumps({"ts": 1000.0, "name": "query", "duration_ms": 0.42, "status": "ok", "cache_hit": True}) + "\n",
        encoding="utf-8",
    )

    rc = stats_cli.cmd_stats([])
    assert rc == 0
    captured = capsys.readouterr().out
    assert "ziro stats" in captured
    assert "ghost" in captured
    assert "0.42" in captured


def test_stats_cli_json_output(mock_cache_dir: Path, capsys: pytest.CaptureFixture) -> None:
    """CLI --json outputs parseable JSON containing tools array."""
    tool_dir = mock_cache_dir / "ghost"
    tool_dir.mkdir()
    (tool_dir / "metrics.jsonl").write_text(
        json.dumps({"ts": 1000.0, "name": "query", "duration_ms": 0.5, "status": "ok", "cache_hit": True}) + "\n",
        encoding="utf-8",
    )

    rc = stats_cli.cmd_stats(["--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert "tools" in data
    assert len(data["tools"]) == 1
    assert data["tools"][0]["name"] == "ghost"
    assert data["tools"][0]["metrics"]["total"] == 1


def test_stats_cli_no_tools(mock_cache_dir: Path, capsys: pytest.CaptureFixture) -> None:
    """CLI exits 0 with graceful message when no tools exist."""
    rc = stats_cli.cmd_stats([])
    assert rc == 0
    captured = capsys.readouterr().out
    assert "No external tools" in captured


def test_health_cli_no_protocol(mock_cache_dir: Path, capsys: pytest.CaptureFixture) -> None:
    """Health command reports INFO when a tool implements no health protocol."""
    rc = health_cli.cmd_health(["ghost"])
    assert rc == 0
    captured = capsys.readouterr().out
    assert "ghost" in captured
    assert "no health protocol implemented" in captured


def test_doctor_includes_external(mock_cache_dir: Path) -> None:
    """Doctor check runs and includes external tools line in run_checks."""
    ghost_dir = mock_cache_dir / "ghost"
    ghost_dir.mkdir()
    (ghost_dir / "metrics.jsonl").write_text(
        json.dumps({"ts": 1000.0, "name": "query", "duration_ms": 0.3, "status": "ok"}) + "\n",
        encoding="utf-8",
    )

    checks = doctor_cli.run_checks()
    assert "external tools" in checks
    status, msg, advice = checks["external tools"]
    assert status == "ok"
    assert "ghost (1 events, 0 errors)" in msg


def test_doctor_no_metrics_info(mock_cache_dir: Path) -> None:
    """Doctor returns info status when no external tools exist."""
    status, msg, advice = doctor_cli._check_external_tools()
    assert status == "info"
    assert "none configured" in msg
