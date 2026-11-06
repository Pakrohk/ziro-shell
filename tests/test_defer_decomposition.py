"""Tests for SPEC-025 M01-M05 Defer Decomposition."""
import subprocess
from pathlib import Path
import pytest

@pytest.mark.unit
def test_queue_shim_size_under_25_lines():
    from core.build import render_defer_core
    shim = render_defer_core(Path("/fake/defer"), [])
    lines = [l for l in shim.splitlines() if l.strip()]
    assert len(lines) < 25, f"Shim has {len(lines)} lines, must be < 25"

@pytest.mark.integration
def test_defer_queue_flushes_correctly():
    cmd = (
        'source ~/.config/ziro/boot.zsh 2>/dev/null; '
        'ziro-defer "echo FLUSH_TEST_PASSED > /tmp/ziro_defer_decomp_test.txt"; '
        '_ziro_defer_flush; '
        '_ziro_defer_core_dispatch_stage 5; '
        'cat /tmp/ziro_defer_decomp_test.txt'
    )
    res = subprocess.run(["zsh", "-f", "-c", cmd], capture_output=True, text=True, timeout=5)
    assert res.returncode == 0
    assert "FLUSH_TEST_PASSED" in res.stdout

@pytest.mark.integration
def test_lazy_modules_loaded_on_demand():
    cmd = (
        'source ~/.config/ziro/boot.zsh 2>/dev/null; '
        'ziro-defer --after=foo "echo hi"; '
        '_ziro_defer_flush; '
        'echo "DAG_LOADED=${_ZIRO_DEFER_LOADED_MODULES[dag]:-0}"'
    )
    res = subprocess.run(["zsh", "-f", "-c", cmd], capture_output=True, text=True, timeout=5)
    assert res.returncode == 0
    assert "DAG_LOADED=1" in res.stdout
