"""ziro analyze — analyze tools and regenerate load.toml.

Separate from `ziro sync` (which builds artifacts from load.toml).

Usage:
  ziro analyze           # read-only audit / lint report (no disk write)
  ziro analyze --full    # regenerate load.toml from scratch (writes file)
  ziro analyze --dry-run # show summary of planned writes (backward compat)
  ziro analyze <tool>    # analyze a single tool only
"""
import argparse
import sys
import tomllib
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ziro analyze", description="Analyze tools and regenerate load.toml.")
    parser.add_argument("tool", nargs="?", help="analyze only this tool and print output")
    parser.add_argument("--full", action="store_true", help="full re-analysis from scratch (regenerates load.toml)")
    parser.add_argument("--dry-run", action="store_true", help="show diff/summary without writing (alias for report)")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    from core.analyzer import analyze_all, analyze_tool
    from core.loadtoml_writer import write_load_toml

    load_toml = Path.home() / ".config" / "ziro" / "load.toml"

    if args.tool and not args.full:
        # Single tool analysis
        factory_path = Path(__file__).parent / "tools_factory.toml"
        if not factory_path.is_file():
            print(f"ziro analyze: error: tools_factory.toml not found at {factory_path}", file=sys.stderr)
            return 1
        with factory_path.open("rb") as f:
            factory = tomllib.load(f)
        match = [t for t in factory.get("tool", []) if t.get("name") == args.tool]
        if not match:
            print(f"ziro analyze: error: tool {args.tool!r} not found in tools_factory", file=sys.stderr)
            return 1
        out = analyze_tool(match[0])
        print(f"Analyzed {args.tool}:")
        for k, v in out.items():
            print(f"  {k} = {v!r}")
        return 0

    # Full or standard analysis
    result = analyze_all(load_toml_path=str(load_toml))

    old_tools_count = 0
    old_user_count = 0
    if load_toml.is_file():
        try:
            with load_toml.open("rb") as f:
                old = tomllib.load(f)
            old_tools_count = len(old.get("tool", []))
            user_sec = old.get("user", {})
            if isinstance(user_sec, dict) and "override" in user_sec:
                old_user_count = len(user_sec["override"])
        except Exception:
            pass

    new_tools_count = len(result.get("tool", []))
    user_sec = result.get("user", {})
    new_user_count = len(user_sec.get("override", [])) if isinstance(user_sec, dict) and "override" in user_sec else 0

    if args.dry_run:
        print(f"Would write {load_toml} with:")
        print(f"  [[tool]] entries: {new_tools_count} (was {old_tools_count})")
        print(f"  [user] entries: {new_user_count} (preserved verbatim)")
        return 0

    if not args.full:
        # Default mode: read-only analysis and report (no disk write per ADL-021)
        timing_counts: dict[str, int] = {}
        for t in result.get("tool", []):
            tm = t.get("timing", "unknown")
            timing_counts[tm] = timing_counts.get(tm, 0) + 1

        timing_str = ", ".join(f"{count} {tm}" for tm, count in sorted(timing_counts.items()))
        print("ziro analyze (read-only audit)")
        print("=" * 50)
        print(f"  Tools analyzed:    {new_tools_count} ({timing_str})")
        print(f"  User overrides:    {new_user_count} (preserved)")
        print(f"  Manifest target:   {load_toml}")

        # Security section (Phase C — only print if any tool has security_notes, conflicts, or blockers)
        security_findings: list[str] = []
        for t in result.get("tool", []):
            if t.get("trust_level") == "internal":
                continue
            t_name = t.get("name", "unknown")
            if t.get("blocked"):
                security_findings.append(f"⛔ {t_name}: BLOCKED (dangerous patterns)")
            elif "CONFLICT" in t.get("security_report", ""):
                security_findings.append(f"⚠️  {t_name}: {t.get('security_report')}")
            elif t.get("trust_level") in ("low", "unknown") and t.get("security_notes"):
                notes = ", ".join(t["security_notes"])
                security_findings.append(f"ℹ️  {t_name} (trust={t.get('trust_level')}): {notes}")

        if security_findings:
            print()
            print("Security findings:")
            for finding in security_findings:
                print(f"  {finding}")

        print()
        print("ℹ️  Read-only mode: no files written.")
        print("   To regenerate load.toml, run `ziro analyze --full`.")
        return 0

    write_load_toml(result, str(load_toml))
    print(f"✔ Analyzed {new_tools_count} tools → {load_toml}")
    print("  [user] section preserved verbatim.")
    print("  Run `ziro sync` to rebuild artifacts from this load.toml.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
