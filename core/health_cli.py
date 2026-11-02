"""ziro health CLI command.

Layer: 3 (Python core, cold-path only)
Spec: 038 (External Tools Observability — health)
"""

from __future__ import annotations

import json
import sys
from typing import Optional

from core.external_tools import discover_tools, read_health, supported_tools


def cmd_health(argv: list[str]) -> int:
    """Entry point for ziro health [tool] [--json] [--all]."""
    tool_arg: Optional[str] = None
    json_mode = False
    run_all = True

    idx = 0
    while idx < len(argv):
        arg = argv[idx]
        if arg == "--json":
            json_mode = True
        elif arg == "--all":
            run_all = True
        elif arg in ("-h", "--help"):
            print("Usage: ziro health [tool] [--json] [--all]")
            print("\nOptions:")
            print("  [tool]    Inspect health of a specific tool (e.g. ghost)")
            print("  --json    Output structured JSON")
            print("  --all     Inspect all discovered tools (default)")
            return 0
        elif not arg.startswith("-"):
            tool_arg = arg
        idx += 1

    if tool_arg:
        tools = [tool_arg]
    else:
        tools = supported_tools()

    results: list[dict[str, Any]] = []
    has_errors = False

    for t in tools:
        h = read_health(t)
        if h:
            results.append({"name": t, "health": h})
            if h.get("status") == "error":
                has_errors = True
        else:
            results.append({
                "name": t,
                "health": {
                    "status": "info",
                    "message": "no health protocol implemented (no health.json, no manifest)",
                },
            })

    if json_mode:
        print(json.dumps({"tools": results}, indent=2))
        return 1 if has_errors else 0

    print(f"ziro health ({len(tools)} tool{'s' if len(tools) != 1 else ''})")
    print("═" * 40)
    print()

    for item in results:
        t_name = item["name"]
        h = item["health"]
        st = h.get("status", "info")
        badge = "✅ HEALTHY" if st == "ok" else ("⚠️  WARNING" if st == "warn" else ("❌ ERROR" if st == "error" else "ℹ️  INFO"))

        print(f"{t_name} " + "─" * max(2, 39 - len(t_name)))
        print(f"  Status: {badge}")

        if "message" in h and h["message"]:
            print(f"  Message: {h['message']}")

        checks = h.get("checks")
        if isinstance(checks, list) and checks:
            passed = sum(1 for c in checks if isinstance(c, dict) and c.get("status") == "ok")
            print(f"  Checks: {passed}/{len(checks)} passed")
            for c in checks:
                if isinstance(c, dict):
                    c_st = c.get("status", "ok")
                    c_badge = "✅" if c_st == "ok" else ("⚠️" if c_st == "warn" else "❌")
                    c_name = c.get("name") or c.get("id") or "check"
                    c_msg = c.get("message") or c.get("verify") or ""
                    print(f"    {c_badge} {c_name}: {c_msg}")
        print()

    return 1 if has_errors else 0


def main(argv: list[str] | None = None) -> int:
    return cmd_health(sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
