"""Phase 4-D: analyze_tool heuristic tests."""
import pytest
from core.analyzer import analyze_tool


def test_prompt_category_eager():
    tool = {
        "name": "starship",
        "type": "binary",
        "category": "prompt",
        "load_method": "eval-cache",
        "init_command": "starship init zsh",
        "requires": "starship",
        "cache_key": "starship",
    }
    out = analyze_tool(tool)
    assert out["timing"] == "eager"
    assert out["method"] == "eval-cache"
    assert "cache_path" in out
    assert "prompt" in out["reason"]


def test_completion_category_eager():
    tool = {
        "name": "zsh-completions",
        "type": "plugin",
        "category": "completion",
        "load_method": "source",
        "source": "zsh-users/zsh-completions",
    }
    out = analyze_tool(tool)
    assert out["timing"] == "eager"
    assert "completion" in out["reason"]


def test_navigation_on_demand_command():
    tool = {
        "name": "zoxide",
        "type": "binary",
        "category": "navigation",
        "load_method": "eval-cache",
        "init_command": "zoxide init zsh",
    }
    out = analyze_tool(tool)
    assert out["timing"] == "on-demand"
    assert out["trigger"] == "command"


def test_fuzzy_finder_on_demand_key():
    tool = {
        "name": "fzf",
        "type": "binary",
        "category": "fuzzy_finder",
        "load_method": "eval-cache",
        "init_command": "fzf --zsh",
    }
    out = analyze_tool(tool)
    assert out["timing"] == "on-demand"
    assert out["trigger"] == "key"


def test_explicit_trigger_keys_wins():
    tool = {
        "name": "fzf",
        "category": "fuzzy_finder",
        "trigger_keys": [{"key": "^R", "widget": "fzf-history-widget"}],
    }
    out = analyze_tool(tool)
    assert out["timing"] == "on-demand"
    assert out["trigger"] == "key"
    assert len(out["trigger_keys"]) == 1


def test_core_plugin_deferred():
    tool = {
        "name": "colored-man-pages",
        "type": "plugin",
        "category": "core",
        "load_method": "source",
        "source": "ohmyzsh/ohmyzsh",
        "subpath": "plugins/colored-man-pages",
    }
    out = analyze_tool(tool)
    assert out["timing"] == "deferred"
    assert out["stage"] == 5


def test_safe_default():
    tool = {"name": "unknown-tool", "type": "plugin", "category": "other"}
    out = analyze_tool(tool)
    assert out["timing"] == "deferred"
    assert "safe default" in out["reason"]


def test_reason_present_in_all_outputs():
    for tool in [
        {"name": "x", "category": "prompt", "load_method": "eval-cache", "init_command": "x init"},
        {"name": "y", "category": "navigation"},
        {"name": "z", "category": "core", "type": "plugin", "source": "x/y"},
        {"name": "w"},
    ]:
        out = analyze_tool(tool)
        assert "reason" in out
        assert isinstance(out["reason"], str)
        assert len(out["reason"]) > 0
