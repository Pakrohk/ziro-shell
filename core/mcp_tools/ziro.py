"""Native Ziro CLI commands exposed to AI models.

Spec: 024 (R14)
"""

from __future__ import annotations

import json
from typing import Any

from core.doctor_cli import run_checks
from core.external_tools import aggregate, discover_tools, read_health, read_metrics
from core.update_cli import find_vendor_plugins


def tool_ziro_analyze(args: dict[str, Any]) -> dict[str, Any]:
    """Execute ziro analyze to report active tools and load performance metrics."""
    from core.generator import load_tools_registry
    tools = load_tools_registry()
    return {
        "active_tools_count": len(tools),
        "tools_summary": [{"name": t.get("name"), "type": t.get("type"), "category": t.get("category")} for t in tools[:15]],
    }


def tool_ziro_doctor(args: dict[str, Any]) -> dict[str, Any]:
    """Execute ziro doctor diagnostic checks and return structured results."""
    checks = run_checks()
    results = {}
    passed = 0
    warnings = 0
    errors = 0

    for name, res in checks.items():
        st, msg, adv = res[0], res[1], res[2] if len(res) > 2 else None
        results[name] = {"status": st, "message": msg, "advice": adv}
        if st == "ok":
            passed += 1
        elif st == "warn":
            warnings += 1
        elif st == "error":
            errors += 1

    return {
        "summary": {"passed": passed, "warnings": warnings, "errors": errors, "total": len(checks)},
        "healthy": errors == 0,
        "checks": results,
    }


def tool_ziro_stats(args: dict[str, Any]) -> dict[str, Any]:
    """Report aggregated metrics across all external tools."""
    tool_name = args.get("tool")
    target_tools = [tool_name] if tool_name else discover_tools()

    stats_data: dict[str, Any] = {}
    for t in target_tools:
        metrics = read_metrics(t)
        stats_data[t] = {
            "aggregation": aggregate(metrics),
            "health": read_health(t),
        }

    return {"tools": stats_data}


def tool_ziro_plugin_list(args: dict[str, Any]) -> dict[str, Any]:
    """List installed plugins and their repository paths."""
    plugins = find_vendor_plugins()
    return {"plugins": [{"name": name, "path": str(path)} for name, path in plugins]}
