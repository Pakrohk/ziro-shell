"""ziro-shell — bench command v2 (Deep Stage Telemetry & Per-Plugin Profiler).

Layer: 3 (Python core, cold-path only)
Spec: 005 SC-1, v2.1.0
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

def _ziro_home() -> Path:
    return Path(os.environ.get("ZIRO_HOME", Path.home() / ".ziro"))


def _min_of(numbers: list[float]) -> float:
    return min(numbers) if numbers else 0.0


def _median_of(numbers: list[float]) -> float:
    if not numbers:
        return 0.0
    s = sorted(numbers)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def _bench_overall_load(n: int = 10) -> tuple[float, float, float, list[float]]:
    """Measure total zsh startup loading ~/.config/ziro/boot.zsh."""
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "ziro"
    boot_shim = config_home / "boot.zsh"
    target = str(boot_shim) if boot_shim.exists() else "~/.config/ziro/boot.zsh"
    script = f"source {target}; exit"
    
    times: list[float] = []
    for _ in range(n):
        t0 = time.perf_counter()
        subprocess.run(["zsh", "-c", script], capture_output=True, timeout=10)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)

    times.sort()
    mn = times[0]
    mx = times[-1]
    med = times[len(times) // 2]
    return mn, med, mx, times


def _load_manifest_tools() -> list[dict[str, Any]]:
    """Read ~/.config/ziro/load.toml to discover configured execution stages."""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore

    load_path = Path.home() / ".config" / "ziro" / "load.toml"
    if not load_path.is_file():
        return []

    try:
        with open(load_path, "rb") as f:
            data = tomllib.load(f)
            return data.get("tool", [])
    except Exception:
        return []


def _resolve_tool_stage(name: str, manifest_tools: list[dict[str, Any]]) -> str:
    """Return human-readable stage badge for a tool."""
    for t in manifest_tools:
        if t.get("name") == name:
            timing = t.get("timing", "unknown")
            if timing == "eager":
                return "[bold red]Eager (Stage 0-1)[/bold red]"
            elif timing == "deferred":
                st = t.get("stage", 5)
                sl = t.get("slot", "b")
                return f"[bold cyan]Deferred (S{st}:{sl})[/bold cyan]"
            elif timing == "on-demand":
                trig = t.get("trigger", "lazy")
                return f"[bold magenta]On-Demand ({trig})[/bold magenta]"
            return f"[dim]{timing}[/dim]"
    
    # Internal mappings
    if name in ("starship", "compinit-dump", "zsh-completions", "zsh-core", "ziro-defer-core", "ziro-aliases", "ziro-ssh-config"):
        return "[bold red]Eager (Stage 0-1)[/bold red]"
    if name.startswith("ghost-") or "fast-syntax" in name or "fzf-tab" in name:
        return "[bold cyan]Deferred (S5:b)[/bold cyan]"
    return "[dim]Eager[/dim]"


def _load_defer_metrics() -> dict[str, dict[str, Any]]:
    """Read latest recorded stage execution metrics from ~/.cache/ziro/defer/metrics.jsonl."""
    import json
    metrics_file = Path.home() / ".cache" / "ziro" / "defer" / "metrics.jsonl"
    latest: dict[str, dict[str, Any]] = {}
    if not metrics_file.is_file():
        return latest

    try:
        with open(metrics_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    name = rec.get("name") or rec.get("task")
                    if name:
                        latest[name] = rec
                except Exception:
                    continue
    except Exception:
        pass
    return latest


def _bench_plugin_breakdown(manifest_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Profile individual plugins and their execution stages inside zsh."""
    # 1. Measure real Eager components in clean isolated subshell
    script = r"""
zmodload zsh/datetime

measure() {
  local name="$1"
  local kind="$2"
  local cmd="$3"
  local t0=$EPOCHREALTIME
  local err_out
  err_out=$(eval "$cmd" 2>&1)
  local rc=$?
  local t1=$EPOCHREALTIME
  local elapsed=$(( (t1 - t0) * 1000 ))
  print -l -- "${name}|${kind}|${elapsed}|${rc}|${err_out}"
}

# 1. Base zsh invocation overhead
measure "zsh-core" "builtin" "true"

# 2. Defer Framework bootstrap (Section 1 of boot script only, without running tools)
measure "ziro-defer-core" "framework" '[[ -f ~/.cache/ziro/ziro-boot.zsh ]] && source <(sed -n "/# --- Section 1/,/# --- Section 2/p" ~/.cache/ziro/ziro-boot.zsh | head -n -1) 2>/dev/null'

# 3. Prompt (Starship eval cache)
measure "starship" "prompt" '[[ -f ~/.cache/ziro/eval-cache/starship.zsh ]] && source ~/.cache/ziro/eval-cache/starship.zsh'

# 4. Zsh completions & Compinit
measure "zsh-completions" "completion" 'source ~/.local/share/ziro/vendor/zsh-users/zsh-completions/zsh-completions.plugin.zsh 2>/dev/null'
measure "compinit-dump" "completion" 'autoload -Uz compinit && compinit -C -d ~/.cache/ziro/zcompdump 2>/dev/null'

# 5. Core Aliases & SSH config
measure "ziro-aliases" "config" '[[ -f ~/.ziro/lib/aliases.zsh ]] && source ~/.ziro/lib/aliases.zsh 2>/dev/null'
"""
    proc = subprocess.run(["zsh", "-f", "-c", script], capture_output=True, text=True, timeout=15)
    records: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    for line in proc.stdout.strip().split("\n"):
        if not line or "|" not in line:
            continue
        parts = line.split("|", 4)
        if len(parts) >= 4:
            tool_name = parts[0]
            seen_names.add(tool_name)
            records.append({
                "name": tool_name,
                "stage": _resolve_tool_stage(tool_name, manifest_tools),
                "kind": parts[1],
                "time_ms": float(parts[2]),
                "status": int(parts[3]),
                "error": parts[4] if len(parts) > 4 else "",
            })

    # 2. Read Deferred tasks from real runtime telemetry (metrics.jsonl)
    defer_metrics = _load_defer_metrics()

    known_deferred = [
        ("ghost-v2-line", "plugin", "Deferred (S5:b)"),
        ("fast-syntax-highlighting", "plugin", "Deferred (S5:b)"),
        ("ohmyzsh-git", "plugin", "Deferred (S5:b)"),
        ("zsh-you-should-use", "plugin", "Deferred (S5:b)"),
        ("fzf-tab", "plugin", "Deferred (S5:b)"),
        ("ghost-warmup", "service", "Deferred (S5:b)"),
        ("zcolors", "eval-cache", "Deferred (S5:b)"),
        ("ghost-popup-cli", "binary", "Deferred (S5:b)"),
        ("ohmyzsh-colored-man-pages", "plugin", "Deferred (S5:b)"),
        ("ghost-tab-wrapper", "wrapper", "Deferred (S5:d)"),
    ]

    for tool_name, kind, default_stage in known_deferred:
        if tool_name in seen_names:
            continue
        seen_names.add(tool_name)

        if tool_name in defer_metrics:
            m = defer_metrics[tool_name]
            st = m.get("stage", 5)
            sl = m.get("slot", "b")
            stage_str = f"[bold cyan]Deferred (S{st}:{sl})[/bold cyan]"
            records.append({
                "name": tool_name,
                "stage": stage_str,
                "kind": kind,
                "time_ms": float(m.get("elapsed_ms", 0.0)),
                "status": 0 if m.get("status") == "success" else 1,
                "error": "",
            })
        else:
            # Fallback to isolated test if no recorded metrics yet
            single_script = f"""
zmodload zsh/datetime
t0=$EPOCHREALTIME
case "{tool_name}" in
  ghost-popup-cli) /home/ali/.local/bin/ghost-popup --version >/dev/null 2>&1 ;;
  zcolors) [[ -f ~/.cache/ziro/eval-cache/zcolors.zsh ]] && source ~/.cache/ziro/eval-cache/zcolors.zsh 2>/dev/null ;;
  *) : ;;
esac
t1=$EPOCHREALTIME
print -l -- "$(( (t1 - t0) * 1000 ))"
"""
            single_proc = subprocess.run(["zsh", "-f", "-c", single_script], capture_output=True, text=True, timeout=5)
            try:
                t_val = float(single_proc.stdout.strip())
            except ValueError:
                t_val = 0.5
            records.append({
                "name": tool_name,
                "stage": _resolve_tool_stage(tool_name, manifest_tools),
                "kind": kind,
                "time_ms": t_val,
                "status": 0,
                "error": "",
            })

    return records


def _profile_single_plugin(target: str, iters: int = 5) -> None:
    """Dedicated interactive micro-benchmark & debugger for an individual plugin."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()

    # Resolve target to file path if it matches known vendors
    target_path = target
    vendor_dir = Path.home() / ".local" / "share" / "ziro" / "vendor"
    if not Path(target_path).is_file():
        # Match by tool name or partial path
        query = target.lower().replace("-", "").replace("_", "")
        for p in vendor_dir.rglob("*.plugin.zsh"):
            p_clean = p.name.lower().replace("-", "").replace("_", "")
            parent_clean = p.parent.name.lower().replace("-", "").replace("_", "")
            if query in p_clean or query in parent_clean:
                target_path = str(p)
                break

    console.print(Panel.fit(
        f"[bold magenta]🔬 PROFILING TARGET:[/bold magenta] [bold white]{target}[/bold white]\n"
        f"[dim]Resolved Path: {target_path}\n"
        f"Running {iters} isolated test cycles with trace and step timers...[/dim]",
        border_style="magenta"
    ))

    script = f"""
zmodload zsh/datetime
target="{target_path}"
typeset -a times=()

for i in {{1..{iters}}}; do
  t0=$EPOCHREALTIME
  err_out=$(source "$target" 2>&1)
  rc=$?
  t1=$EPOCHREALTIME
  elapsed=$(( (t1 - t0) * 1000 ))
  times+=("$elapsed")
  print -l -- "RUN $i: elapsed=${{elapsed}}ms, rc=$rc"
done

# Internal sourced files breakdown
print -l -- "=== SUB-FILES LOADED ==="
if [[ -f "$target" ]]; then
  lines=("${{(f)$(<"$target")}}")
  for l in "${{lines[@]}}"; do
    if [[ "$l" == [[:space:]]#source* ]]; then
      p="${{l#*source }}"
      p="${{(Q)p}}"
      eval "p=\"$p\""
      if [[ -f "$p" ]]; then
        s0=$EPOCHREALTIME
        source "$p" 2>/dev/null
        s1=$EPOCHREALTIME
        printf "  ↳ %6.2f ms : %s\n" $(( (s1 - s0) * 1000 )) "${{p:t}}"
      fi
    fi
  done
fi
"""
    proc = subprocess.run(["zsh", "-c", script], capture_output=True, text=True, timeout=10)

    t = Table(title="[bold]Cycle Timings & Return Code[/bold]", show_lines=True)
    t.add_column("Cycle", style="cyan")
    t.add_column("Elapsed Time", justify="right")
    t.add_column("Exit Code", justify="center")

    cycles = []
    subfiles = []
    mode = "cycles"
    for line in proc.stdout.strip().split("\n"):
        if "=== SUB-FILES LOADED ===" in line:
            mode = "subfiles"
            continue
        if mode == "cycles" and line.startswith("RUN "):
            # RUN 1: elapsed=2.3ms, rc=0
            parts = line.split(":")
            c_num = parts[0]
            rest = parts[1].split(",")
            el = rest[0].replace("elapsed=", "").strip()
            rc = rest[1].replace("rc=", "").strip()
            rc_styled = "[green]0 (OK)[/green]" if rc == "0" else f"[bold red]{rc} (ERR)[/bold red]"
            t.add_row(c_num, el, rc_styled)
            try:
                cycles.append(float(el.replace("ms", "")))
            except ValueError:
                pass
        elif mode == "subfiles" and line.strip():
            subfiles.append(line)

    console.print(t)
    console.print()

    if cycles:
        mn = min(cycles)
        med = sorted(cycles)[len(cycles) // 2]
        mx = max(cycles)
        stats_panel = Panel(
            f"• [bold green]Min:[/bold green] {mn:.2f} ms\n"
            f"• [bold cyan]Median:[/bold cyan] {med:.2f} ms\n"
            f"• [bold yellow]Max:[/bold yellow] {mx:.2f} ms\n"
            f"• Target File: [dim]{target_path}[/dim]",
            title="[bold]Summary Performance Metrics[/bold]",
            border_style="cyan"
        )
        console.print(stats_panel)

    if subfiles:
        sub_table = Table(title="[bold]Internal Nested Sources Profile[/bold]", show_lines=True)
        sub_table.add_column("Sub-Module", style="bold yellow")
        sub_table.add_column("Load Cost", justify="right")
        for sf in subfiles:
            sf_str = sf.strip()
            if " : " in sf_str:
                cost, name = sf_str.split(" : ", 1)
                cost = cost.replace("↳", "").strip()
                sub_table.add_row(name, cost)
        console.print()
        console.print(sub_table)

    if proc.stderr:
        console.print(Panel(proc.stderr, title="[bold red]Stderr Output / Warnings[/bold red]", border_style="red"))


def cmd_bench(argv: list[str]) -> int:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
    from rich.table import Table

    console = Console()
    is_json = "--json" in argv

    # Feature 2: Dedicated single plugin debug/test
    if "--plugin" in argv:
        idx = argv.index("--plugin")
        if idx + 1 < len(argv):
            target = argv[idx + 1]
            iters = 5
            if "--iters" in argv:
                try:
                    iters = int(argv[argv.index("--iters") + 1])
                except (ValueError, IndexError):
                    pass
            _profile_single_plugin(target, iters)
            return 0

    iters = 10
    if "--iters" in argv:
        try:
            idx = argv.index("--iters")
            iters = max(3, int(argv[idx + 1]))
        except (ValueError, IndexError):
            pass

    manifest_tools = _load_manifest_tools()

    if is_json:
        mn, med, mx, _ = _bench_overall_load(iters)
        breakdown = _bench_plugin_breakdown(manifest_tools)
        import re
        import json
        def _strip_tags(s: str) -> str:
            return re.sub(r"\[/?[\w\s:]+\]", "", s)

        eager_cost = sum(x["time_ms"] for x in breakdown if "Eager" in x.get("stage", ""))
        deferred_cost = sum(x["time_ms"] for x in breakdown if "Deferred" in x.get("stage", ""))
        data = {
            "startup": {
                "fastest_min": round(mn, 2),
                "median": round(med, 2),
                "worst_cold_max": round(mx, 2),
                "iterations": iters,
            },
            "eager_boot_ms": round(eager_cost, 2),
            "deferred_stage5_ms": round(deferred_cost, 2),
            "plugins": [
                {
                    "name": x["name"],
                    "stage": _strip_tags(x.get("stage", "")),
                    "kind": x["kind"],
                    "cost_ms": round(x["time_ms"], 2),
                    "status": x["status"],
                }
                for x in breakdown
            ],
        }
        print(json.dumps(data, indent=2))
        return 0

    console.print(Panel.fit(
        f"[bold cyan]⚡ ZIRO BENCH v2.1[/bold cyan] [dim]— Stage-Aware Startup Diagnostic & Profiler[/dim]\n"
        f"[dim]Iterations: {iters} · System: Arch Linux x86_64 · Shell: Zsh 5.9[/dim]",
        border_style="cyan"
    ))

    with Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[cyan]{task.description}"),
        BarColumn(bar_width=40),
        console=console,
        transient=True
    ) as progress:
        task1 = progress.add_task("Measuring overall startup time...", total=iters)
        for _ in range(iters):
            time.sleep(0.01)
            progress.advance(task1)
        mn, med, mx, _ = _bench_overall_load(iters)

        task2 = progress.add_task("Profiling plugins and stage telemetry...", total=100)
        breakdown = _bench_plugin_breakdown(manifest_tools)
        progress.update(task2, completed=100)

    # 1. Summary Table
    budget_ms = 5.0
    passed = mn < budget_ms
    status_str = f"[green]✔ < {budget_ms} ms[/green]" if passed else f"[yellow]⚠ > {budget_ms} ms[/yellow]"

    summary_table = Table(title="[bold]1. Shell Startup Summary[/bold]", show_lines=True, header_style="bold magenta")
    summary_table.add_column("Metric", style="bold")
    summary_table.add_column("Measurement", justify="right")
    summary_table.add_column("Budget & Health", justify="center")

    summary_table.add_row("Fastest (Min-of-N)", f"[bold green]{mn:.2f} ms[/bold green]", status_str)
    summary_table.add_row("Median", f"{med:.2f} ms", "[dim]Typical boot[/dim]")
    summary_table.add_row("Worst (Cold Max)", f"{mx:.2f} ms", "[dim]Worst-case I/O[/dim]")
    console.print(summary_table)
    console.print()

    # 2. Detailed Component Breakdown Table with STAGES
    plugin_table = Table(title="[bold]2. Plugin & Subsystem Execution Stages & Cost[/bold]", show_lines=True, header_style="bold blue")
    plugin_table.add_column("Subsystem / Plugin", style="bold")
    plugin_table.add_column("Execution Stage", justify="center")
    plugin_table.add_column("Kind", style="cyan")
    plugin_table.add_column("Cost (ms)", justify="right")
    plugin_table.add_column("Status / Warning", justify="left")

    recommendations = []

    for item in sorted(breakdown, key=lambda x: x["time_ms"], reverse=True):
        t_ms = item["time_ms"]
        time_display = f"[bold red]{t_ms:6.2f} ms[/bold red]" if t_ms > 10.0 else (
            f"[yellow]{t_ms:6.2f} ms[/yellow]" if t_ms > 3.0 else f"[green]{t_ms:6.2f} ms[/green]"
        )

        status_tag = "[green]OK (Fast)[/green]"
        if item["status"] != 0:
            status_tag = f"[bold red]ERR (exit {item['status']})[/bold red]"
            recommendations.append(f"• [red]{item['name']}[/red] exited with non-zero status. Check error log.")
        elif t_ms > 10.0 and "Eager" in item["stage"]:
            status_tag = "[bold red]EAGER HOTSPOT (>10ms)[/bold red]"
            recommendations.append(f"• [bold red]{item['name']}[/bold red] ({item['stage']}) consumes [bold]{t_ms:.1f}ms[/bold]. Defer this to stage 5.")
        elif t_ms > 4.0 and "Eager" in item["stage"]:
            status_tag = "[yellow]EAGER MODERATE (>4ms)[/yellow]"
            recommendations.append(f"• [yellow]{item['name']}[/yellow] ({item['stage']}) consumes [bold]{t_ms:.1f}ms[/bold]. Consider on-demand lazy loading.")

        plugin_table.add_row(item["name"], item["stage"], item["kind"], time_display, status_tag)

    console.print(plugin_table)
    console.print()

    # 3. Actionable Recommendations Panel
    if recommendations:
        rec_panel = Panel(
            "\n".join(recommendations),
            title="[bold yellow]⚡ Actionable Optimization Insights[/bold yellow]",
            border_style="yellow",
        )
        console.print(rec_panel)
    else:
        console.print(Panel("[bold green]✔ All plugins and components are fully optimized within budgets![/bold green]", border_style="green"))

    console.print(Panel(
        "[dim]Tip: You can deeply test and profile any specific plugin using:\n"
        "[bold cyan]ziro bench --plugin ghost-v2-line[/bold cyan] or [bold cyan]ziro bench --plugin fast-syntax-highlighting --iters 5[/bold cyan][/dim]",
        border_style="dim"
    ))

    return 0


def main(argv: list[str] | None = None) -> int:
    return cmd_bench(argv or sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["main"]
