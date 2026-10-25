"""Path representation: _resolve_vendor_path emits ~-based paths."""
import os
from pathlib import Path
import pytest
from core.analyzer import _resolve_vendor_path


def test_resolver_emits_tilde_path(tmp_path, monkeypatch):
    """Resolver must return ~-based paths (not ${VAR}-based, not absolute)."""
    fake_home = tmp_path
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.setenv('HOME', str(fake_home))

    # Create fake vendor structure
    vendor = fake_home / '.local' / 'share' / 'ziro' / 'vendor' / 'Test' / 'my-plugin'
    vendor.mkdir(parents=True)
    (vendor / 'my-plugin.plugin.zsh').write_text('')

    path, ok = _resolve_vendor_path('Test/my-plugin', plugin_file='my-plugin.plugin.zsh')
    assert ok is True
    assert path.startswith('~/'), f'Expected ~-based path, got: {path}'
    assert not path.startswith('/'), 'Must not be absolute'
    assert '${' not in path, 'Must not contain ${VAR}'
    # And it should resolve with expanduser
    assert os.path.isfile(os.path.expanduser(path))


def test_resolver_returns_empty_when_missing(tmp_path, monkeypatch):
    fake_home = tmp_path
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.setenv('HOME', str(fake_home))
    path, ok = _resolve_vendor_path('NoSuch/repo', plugin_file='x.plugin.zsh')
    assert ok is False
    assert path == ''


def test_resolver_finds_plugin_zsh_fallback(tmp_path, monkeypatch):
    """If requested plugin_file missing but plugin.zsh exists, use it."""
    fake_home = tmp_path
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.setenv('HOME', str(fake_home))

    vendor = fake_home / '.local' / 'share' / 'ziro' / 'vendor' / 'Org' / 'x'
    vendor.mkdir(parents=True)
    (vendor / 'plugin.zsh').write_text('')

    path, ok = _resolve_vendor_path('Org/x', plugin_file='nonexistent.plugin.zsh')
    assert ok is True
    assert path.endswith('plugin.zsh')
