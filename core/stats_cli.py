"""ziro stats CLI command.

Layer: 3 (Python core, cold-path only)
Spec: 038 (External Tools Observability — stats)
"""

from __future__ import annotations

import datetime
import json
import sys
import time
from typing import Optional

from core.external_tools import aggregate, discover_tools, read_metrics


def _parse_duration(since_str: str) -> Optional[float]:
    """Parse duration string like 1h, 30m, 1d, 7d into seconds."""
    s = since_str.strip()
    if not s:
        return None
    try:
        if s.endswith("s"):
            return float(s[:-1])
        if s.endswith("m"):
            return float(s[:-1]) * 60
        if s.endswith("h"):
            return float(s[:-1]) * 3600
        if s.endswith("d"):
            return float(s[:-1]) * 86400
        if s.endswith("w"):
            return float(s[:-1]) * 86400 * 7
        return float(s)
    except ValueError:
        return None


def cmd_stats(argv: list[str]) -> int:
    """Entry point for ziro stats."""
    tool_filter: Optional[str] = None
    json_mode = False
    since_str: Optional[str] = None
    limit = 10000
    verbose = False

    idx = 0
    while idx < len(argv):
        arg = argv[idx]
        if arg == "--json":
            json_mode = True
        elif arg == "--verbose" or arg == "-v":
            verbose = True
        elif arg == "--tool":
            idx += 1
            if idx < len(argv):
                tool_filter = argv[idx]
        elif arg.startswith("--tool="):
            tool_filter = arg.split("=", 1)[1]
        elif arg == "--since":
            idx += 1
            if idx < len(argv):
                since_str = argv[idx]
        elif arg.startswith("--since="):
            since_str = arg.split("=", 1)[1]
        elif arg == "--limit":
            idx += 1
            if idx < len(argv):
                try:
                    limit = int(argv[idx])
                except ValueError:
                    pass
        elif arg.startswith("--limit="):
            try:
                limit = int(arg.split("=", 1)[1])
            except ValueError:
                pass
        elif arg in ("-h", "--help"):
            print("Usage: ziro stats [--tool <name>] [--json] [--since <dur>] [--limit <n>] [--verbose]")
            print("\nOptions:")
            print("  --tool <name>    Filter to a single external tool")
            print("  --json           Output structured JSON")
            print("  --since <dur>    Filter events by age (e.g. 30m, 1h, 1d, 7d)")
            print("  --limit <n>      Maximum metrics to read per tool (default: 10000)")
            print("  --verbose        Show per-intent breakdown")
            return 0
        idx += 1

    since_seconds = _parse_duration(since_str) if since_str else None

    discovered = discover_tools()
    if tool_filter:
        tools = [tool_filter]
    else:
        tools = discovered

    if not tools:
        if json_mode:
            print(json.dumps({"tools": []}))
        else:
            print("No external tools with metrics found in ~/.cache/ziro/")
        return 0

    results: list[dict[str, Any]] = []
    total_events = 0

    for t in tools:
        m = read_metrics(t, since_seconds=since_seconds, max_lines=limit)
        agg = aggregate(m)
        total_events += agg["total"]
        results.append({"name": t, "metrics": agg})

    if json_mode:
        print(json.dumps({"tools": results}, indent=2))
        return 0

    if total_events == 0:
        if tool_filter:
            print(f"No metrics found for tool '{tool_filter}'")
        else:
            print("No metrics recorded yet across discovered tools.")
        return 0

    print(f"ziro stats (last {limit} events across {len(tools)} tool{'s' if len(tools) != 1 else ''})")
    print("═" * 60)
    print()

    for item in results:
        t_name = item["name"]
        agg = item["metrics"]
        print(f"{t_name} " + "─" * max(2, 59 - len(t_name)))
        if agg["total"] == 0:
            print("  No events recorded.")
            print()
            continue

        err_pct = agg["error_rate"] * 100
        hit_pct = agg["cache_hit_rate"] * 100
        print(f"  Total intents:    {agg['total']:,}")
        print(f"  Errors:           {agg['error_count']} ({err_pct:.2f}%)")
        print(f"  Cache hit rate:   {hit_pct:.1f}%")
        print("  Latency (ms):")
        print(f"    P50:  {agg['p50']}")
        print(f"    P95:  {agg['p95']}")
        print(f"    P99:  {agg['p99']}")

        print("  By level:")
        for lvl in ("ephemeral", "standard", "critical"):
            cnt = agg["by_level"].get(lvl, 0)
            if cnt > 0:
                print(f"    {lvl:<10}  {cnt:>6,}")

        if agg.get("last_ts"):
            dt = datetime.datetime.fromtimestamp(agg["last_ts"])
            age = int(time.time() - agg["last_ts"])
            age_str = f"{age}s ago" if age < 60 else (f"{age // 60}m ago" if age < 3600 else f"{age // 3600}h ago")
            print(f"  Last activity:    {dt.strftime('%Y-%m-%d %H:%M:%S')} ({age_str})")

        if verbose and agg.get("by_intent"):
            print("  By intent:")
            for iname, istats in agg["by_intent"].items():
                print(f"    {iname}:")
                print(f"      Count: {istats['count']} | P50: {istats['p50']}ms | P95: {istats['p95']}ms | Errors: {istats['errors']}")

        print()

    print("─" * 60)
    print("Path: ~/.cache/ziro/<tool>/metrics.jsonl")
    return 0


def main(argv: list[str] | None = None) -> int:
    return cmd_stats(sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
