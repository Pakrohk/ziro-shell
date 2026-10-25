"""4-D: plugin add CLI flag parsing tests."""
from core.plugin_cli import _parse_lazy_flags


def test_eager_flag():
    out = _parse_lazy_flags([], eager=True, defer_slot=None)
    assert out["timing"] == "eager"
    assert "eager" in out["reason"]


def test_defer_flag():
    out = _parse_lazy_flags([], eager=False, defer_slot="b")
    assert out["timing"] == "deferred"
    assert out["slot"] == "b"


def test_lazy_key_flag():
    out = _parse_lazy_flags(["key:^R,^T"], eager=False, defer_slot=None)
    assert out["timing"] == "on-demand"
    assert out["trigger"] == "key"
    assert len(out["trigger_keys"]) == 2


def test_lazy_command_flag():
    out = _parse_lazy_flags(["command:z,zi"], eager=False, defer_slot=None)
    assert out["trigger"] == "command"
    assert out["trigger_commands"] == ["z", "zi"]


def test_lazy_function_flag():
    out = _parse_lazy_flags(["function:mkcd,take"], eager=False, defer_slot=None)
    assert out["trigger"] == "function"
    assert out["trigger_functions"] == ["mkcd", "take"]


def test_no_flags_returns_none():
    out = _parse_lazy_flags([], eager=False, defer_slot=None)
    assert out is None
