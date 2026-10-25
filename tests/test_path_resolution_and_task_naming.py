"""Tests for 4-E bugfix: path resolution, task naming, and unresolved handling."""
import os
from pathlib import Path
from core.analyzer import _resolve_vendor_path, analyze_tool
from core.build import _filter_resolved, render_deferred_section
from core.doctor_cli import _check_paths


def test_resolve_vendor_path_existing():
    # zsh-users/zsh-completions is installed in ~/.local/share/ziro/vendor or ~/.ziro/vendor
    path, ok = _resolve_vendor_path("zsh-users/zsh-completions")
    assert ok is True
    assert "zsh-completions" in path
    assert path.endswith(".plugin.zsh")


def test_resolve_vendor_path_ziro_ghost():
    # Pakrohk/ziro-ghost has ghost.plugin.zsh
    path, ok = _resolve_vendor_path("Pakrohk/ziro-ghost")
    assert ok is True
    assert "Pakrohk/ziro-ghost" in path
    assert path.endswith("ghost.plugin.zsh")


def test_resolve_vendor_path_subpath():
    # ohmyzsh/ohmyzsh with subpath plugins/git
    path, ok = _resolve_vendor_path("ohmyzsh/ohmyzsh", subpath="plugins/git")
    assert ok is True
    assert "git.plugin.zsh" in path


def test_resolve_vendor_path_local_env_var():
    path, ok = _resolve_vendor_path("$ZIRO_HOME/lib/helpers.zsh")
    assert ok is True
    assert path == "~/.ziro/lib/helpers.zsh"


def test_resolve_vendor_path_missing():
    path, ok = _resolve_vendor_path("nonexistent-owner/nonexistent-plugin-12345")
    assert ok is False
    assert path == ""


def test_analyze_tool_resolves_ghost():
    tool = {
        "name": "ziro-ghost",
        "type": "plugin",
        "category": "auto_suggest",
        "source": "Pakrohk/ziro-ghost",
    }
    out = analyze_tool(tool)
    assert out.get("unresolved") is not True
    assert out.get("path", "").endswith("ghost.plugin.zsh")


def test_analyze_tool_marks_missing_unresolved():
    tool = {
        "name": "fake-plugin",
        "type": "plugin",
        "category": "core",
        "source": "fake/fake-plugin",
    }
    out = analyze_tool(tool)
    assert out.get("unresolved") is True


def test_filter_resolved():
    tools = [
        {"name": "t1", "unresolved": True},
        {"name": "t2", "path": "/some/path"},
    ]
    resolved, unresolved = _filter_resolved(tools)
    assert len(resolved) == 1
    assert resolved[0]["name"] == "t2"
    assert unresolved == ["t1"]


def test_render_deferred_section_includes_name_and_skips_unresolved():
    tools = [
        {
            "name": "tool-ok",
            "timing": "deferred",
            "stage": 5,
            "slot": "b",
            "path": "/path/to/tool-ok.zsh",
            "enabled": True,
        },
        {
            "name": "tool-missing",
            "timing": "deferred",
            "stage": 5,
            "slot": "b",
            "path": "/path/to/missing.zsh",
            "unresolved": True,
            "enabled": True,
        },
    ]
    rendered = render_deferred_section(tools)
    assert '--name="tool-ok"' in rendered
    assert "/path/to/tool-ok.zsh" in rendered
    assert "tool-missing" not in rendered
