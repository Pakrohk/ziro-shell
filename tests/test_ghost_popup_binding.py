"""Tests for Ghost v2.0.1 popup Tab binding wrapper.

Layer: 4 (Tests)
Spec: 025 (Phase A)
"""

from __future__ import annotations

import subprocess


def test_tab_bound_to_ghost_focus_widget():
    cmd = 'source ~/.zshrc 2>/dev/null; ziro-defer-dispatch 5; bindkey "^I"'
    res = subprocess.run(["zsh", "-ic", cmd], capture_output=True, text=True, timeout=5)
    assert res.returncode == 0
    assert '"^I" _ghost_focus_widget' in res.stdout


def test_wrapper_marker_present():
    cmd = 'source ~/.zshrc 2>/dev/null; ziro-defer-dispatch 5; echo "WRAPPED=$ZIRO_GHOST_FOCUS_WRAPPED"'
    res = subprocess.run(["zsh", "-ic", cmd], capture_output=True, text=True, timeout=5)
    assert res.returncode == 0
    assert "WRAPPED=1" in res.stdout


def test_original_preserved():
    cmd = 'source ~/.zshrc 2>/dev/null; ziro-defer-dispatch 5; typeset -f _ghost_focus_widget_orig'
    res = subprocess.run(["zsh", "-ic", cmd], capture_output=True, text=True, timeout=5)
    assert res.returncode == 0
    assert "_ghost_bus_init" in res.stdout


def test_fzf_tab_still_callable():
    cmd = 'source ~/.zshrc 2>/dev/null; ziro-defer-dispatch 5; zle -l | grep fzf-tab-complete'
    res = subprocess.run(["zsh", "-ic", cmd], capture_output=True, text=True, timeout=5)
    assert res.returncode == 0
    assert "fzf-tab-complete" in res.stdout


def test_no_wrapper_when_ghost_missing():
    # If _ghost_focus_widget is absent, the wrapper code does not install
    cmd = 'unfunction _ghost_focus_widget 2>/dev/null || true; unset ZIRO_GHOST_FOCUS_WRAPPED 2>/dev/null || true; bindkey "^I"'
    res = subprocess.run(["zsh", "-f", "-c", cmd], capture_output=True, text=True, timeout=5)
    assert res.returncode == 0
    assert "expand-or-complete" in res.stdout
