"""ziro-shell — bench command (hot-path measurement).

Layer: 3 (Python core, cold-path only)
Spec: 005 SC-1
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


def _ziro_home() -> Path:
    return Path(os.environ.get("ZIRO_HOME", Path.home() / ".ziro"))


def _bench_shell_load(n: int = 11) -> list[float]:
    """Measure zsh startup time loading boot.zsh."""
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "ziro"
    boot_shim = config_home / "boot.zsh"
    if not boot_shim.exists():
        cache_home = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "ziro"
        boot_shim = cache_home / "ziro-boot.zsh"
    target = str(boot_shim) if boot_shim.exists() else "~/.config/ziro/boot.zsh"
    script = f"source {target}"
    times: list[float] = []
    for _ in range(n):
        t0 = time.perf_counter()
        subprocess.run(
            ["zsh", "-c", script],
            capture_output=True,
            timeout=10,
        )
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)  # ms
    return times


def _min_of(times: list[float]) -> float:
    return min(times) if times else 0.0


def _median_of(times: list[float]) -> float:
    if not times:
        return 0.0
    s = sorted(times)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def cmd_bench(argv: list[str]) -> int:
    from core.help_cli import handle_help_if_requested
    ret = handle_help_if_requested(argv, "bench")
    if ret is not None:
        return ret
    iters = 11
    if "--iters" in argv:
        idx = argv.index("--iters")
        if idx + 1 < len(argv):
            try:
                iters = max(3, int(argv[idx + 1]))
            except ValueError:
                pass

    print(f"ziro bench — {iters} iterations (min-of-N)")
    print("=" * 50)

    # 1. Zsh startup with ziro integration
    times = _bench_shell_load(iters)
    mn = _min_of(times)
    med = _median_of(times)

    from core.rich_helpers import render_table
    budget_ms = 5.0
    passed = mn < budget_ms
    status_str = f"✅ < {budget_ms} ms" if passed else f"⚠️ > {budget_ms} ms"

    table_rows = [
        ["Min", f"{mn:.2f} ms", status_str],
        ["Median", f"{med:.2f} ms", "—"],
        ["Max", f"{max(times):.2f} ms" if times else "n/a", "—"],
    ]

    if not render_table(f"Startup Benchmark ({iters} iters)", ["Metric", "Value", "Budget Status"], table_rows):
        print(" zsh + ziro (boot.zsh)")
        print(f" min: {mn:.2f} ms")
        print(f" median: {med:.2f} ms")
        print(f" max: {max(times):.2f} ms" if times else " max: n/a")
        print()
        if passed:
            print(f" ✅ ziro contribution < {budget_ms} ms (min = {mn:.2f} ms)")
        else:
            print(f" ⚠️ ziro contribution exceeds budget: {mn:.2f} ms > {budget_ms} ms")
            print(" (note: this measures total zsh startup, not just ziro)")
    else:
        print()
        if passed:
            print(f" ✅ ziro contribution < {budget_ms} ms (min = {mn:.2f} ms)")
        else:
            print(f" ⚠️ ziro contribution exceeds budget: {mn:.2f} ms > {budget_ms} ms")
            print(" (note: this measures total zsh startup, not just ziro)")

    return 0


def main(argv: list[str]) -> int:
    return cmd_bench(argv)


__all__ = ["main"]
