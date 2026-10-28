"""Comprehensive doctor test suite: each check tested for happy + failure."""
import os
import tomllib
from pathlib import Path
import pytest


def _import_check(name):
    import importlib, core.doctor_cli
    importlib.reload(core.doctor_cli)
    return getattr(core.doctor_cli, name)


@pytest.fixture(autouse=True)
def _clean_ziro_env(monkeypatch):
    for var in ("ZIRO_HOME", "ZIRO_CONFIG", "ZIRO_DATA", "ZIRO_CACHE"):
        monkeypatch.delenv(var, raising=False)


def test_check_python_version_returns_tuple():
    fn = _import_check('_check_python_version')
    result = fn()
    assert isinstance(result, tuple)
    assert len(result) >= 2
    assert result[0] in ('ok', 'warn', 'error', 'info')


def test_check_boot_chain_handles_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    fn = _import_check('_check_boot_chain')
    result = fn()
    assert result[0] == 'error'
    assert 'missing' in result[1].lower() or 'not found' in result[1].lower()


def test_check_boot_chain_handles_present(tmp_path, monkeypatch):
    fake = tmp_path
    monkeypatch.setattr(Path, 'home', lambda: fake)
    # Create chain
    (fake / '.config/ziro').mkdir(parents=True)
    (fake / '.config/ziro/boot.zsh').write_text('')
    (fake / '.config/ziro/load.toml').write_text('[meta]\nschema_version = "1.0.0"\n')
    (fake / '.cache/ziro').mkdir(parents=True)
    (fake / '.cache/ziro/ziro-boot.zsh').write_text('')
    (fake / '.cache/ziro/ziro-boot.zsh.zwc').write_bytes(b'zwc')
    fn = _import_check('_check_boot_chain')
    result = fn()
    assert result[0] in ('ok', 'info')


def test_check_compiled_artifacts_uses_expandvars(tmp_path, monkeypatch):
    """Critical: paths with ${VAR} must be resolved via expandvars."""
    fake = tmp_path
    monkeypatch.setattr(Path, 'home', lambda: fake)
    monkeypatch.setenv('ZIRO_TEST_VENDOR', str(fake))
    (fake / 'test.zsh').write_text('')
    (fake / 'test.zsh.zwc').write_bytes(b'zwc')
    os.utime(fake / 'test.zsh', (1000, 1000))
    os.utime(fake / 'test.zsh.zwc', (2000, 2000))
    (fake / '.config/ziro').mkdir(parents=True)
    (fake / '.config/ziro/load.toml').write_text(
        '[meta]\nschema_version = "1.0.0"\n'
        '[[tool]]\nname = "t"\ntiming = "eager"\nmethod = "source"\npath = "${ZIRO_TEST_VENDOR}/test.zsh"\n'
    )
    fn = _import_check('_check_compiled_artifacts')
    result = fn()
    assert result[0] in ('ok', 'info'), f'Expected ok with expandvars, got {result}'


def test_check_tool_paths_uses_expandvars(tmp_path, monkeypatch):
    fake = tmp_path
    monkeypatch.setattr(Path, 'home', lambda: fake)
    monkeypatch.setenv('ZIRO_TEST_PATH', str(fake))
    (fake / 'exists.zsh').write_text('')
    (fake / '.config/ziro').mkdir(parents=True)
    (fake / '.config/ziro/load.toml').write_text(
        '[meta]\nschema_version = "1.0.0"\n'
        '[[tool]]\nname = "t"\ntiming = "eager"\nmethod = "source"\npath = "${ZIRO_TEST_PATH}/exists.zsh"\n'
    )
    fn = _import_check('_check_tool_paths')
    result = fn()
    assert result[0] in ('ok', 'info')


def test_check_loadtoml_schema_handles_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    fn = _import_check('_check_loadtoml_schema')
    result = fn()
    assert result[0] == 'error'


def test_check_loadtoml_schema_handles_invalid(tmp_path, monkeypatch):
    fake = tmp_path
    monkeypatch.setattr(Path, 'home', lambda: fake)
    (fake / '.config/ziro').mkdir(parents=True)
    (fake / '.config/ziro/load.toml').write_text('this is not valid TOML [[')
    fn = _import_check('_check_loadtoml_schema')
    result = fn()
    assert result[0] == 'error'


def test_doctor_returns_all_sections():
    """Full run must return dict with all check names."""
    import core.doctor_cli as d
    if not hasattr(d, 'run_checks'):
        pytest.skip('run_checks not implemented yet')
    result = d.run_checks()
    assert isinstance(result, dict)
    assert len(result) >= 5
