"""Test on-demand emission for all lazy tools."""
import tomllib
from pathlib import Path
import pytest
from core.generator import emit_on_demand_key, emit_on_demand_command, emit_on_demand_function


def load_tools():
    d = tomllib.loads(Path('core/tools_factory.toml').read_text())
    return {t['name']: t for t in d['tool']}


def test_fzf_on_demand_key():
    tools = load_tools()
    assert tools['fzf']['load_timing'] == 'on-demand'
    assert tools['fzf']['trigger_type'] == 'key'
    assert len(tools['fzf']['trigger_keys']) == 3


def test_zoxide_on_demand_command():
    tools = load_tools()
    assert tools['zoxide']['load_timing'] == 'on-demand'
    assert tools['zoxide']['trigger_type'] == 'command'
    assert len(tools['zoxide']['trigger_commands']) == 5


def test_wd_on_demand_command():
    tools = load_tools()
    assert tools['wd']['load_timing'] == 'on-demand'
    assert tools['wd']['trigger_commands'] == ['wd']


def test_helpers_on_demand_function():
    tools = load_tools()
    assert tools['ziro-helpers']['load_timing'] == 'on-demand'
    assert tools['ziro-helpers']['trigger_type'] == 'function'
    assert 'mkcd' in tools['ziro-helpers']['trigger_functions']


def test_starship_zcolors_stay_eager():
    tools = load_tools()
    assert tools['starship']['load_timing'] in ('eval', 'eager')
    assert tools['zcolors']['load_timing'] in ('eval', 'eager')


def test_emit_fzf_contains_bind_widget():
    out = emit_on_demand_key(load_tools()['fzf'])
    assert 'ziro-defer-bind-widget' in out
    for k in ('^R', '^T', '^[c'):
        assert k in out
    assert '_ZIRO_FZF_LOADED' in out


def test_emit_zoxide_contains_proxies():
    out = emit_on_demand_command(load_tools()['zoxide'])
    assert '_ziro_zoxide_ensure' in out
    assert '_ZIRO_ZOXIDE_LOADED' in out
    for c in ('z', 'zi', 'za', 'zr', 'zq'):
        assert f'{c}() {{ _ziro_zoxide_ensure' in out


def test_emit_wd_contains_proxy():
    out = emit_on_demand_command(load_tools()['wd'])
    assert 'wd() { _ziro_wd_ensure wd' in out


def test_emit_helpers_contains_proxies():
    out = emit_on_demand_function(load_tools()['ziro-helpers'])
    assert '_ziro_ziro_helpers_ensure' in out or '_ziro_helpers_ensure' in out
    for fn in ('mkcd', 'take', 'extract', 'clipcopy', 'clippaste'):
        assert f'{fn}() {{' in out
        assert 'unfunction' in out


def test_guard_prevents_reload():
    out = emit_on_demand_key(load_tools()['fzf'])
    assert 'return 0' in out
