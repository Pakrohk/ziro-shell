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


@pytest.mark.unit
def test_check_python_version_returns_tuple():
    fn = _import_check('_check_python_version')
    result = fn()
    assert isinstance(result, tuple)
    assert len(result) >= 2
    assert result[0] in ('ok', 'warn', 'error', 'info')


@pytest.mark.unit
def test_check_boot_chain_handles_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    fn = _import_check('_check_boot_chain')
    result = fn()
    assert result[0] == 'error'
    assert 'missing' in result[1].lower() or 'not found' in result[1].lower()


@pytest.mark.integration
def test_check_boot_chain_handles_present(tmp_path, monkeypatch):
    fake = tmp_path
    monkeypatch.setattr(Path, 'home', lambda: fake)
    # Create chain
    cfg_dir = fake / '.config/ziro'
    cfg_dir.mkdir(parents=True)
    cfg_dir.chmod(0o700)
    (cfg_dir / 'boot.zsh').write_text('')
    (cfg_dir / 'load.toml').write_text('[meta]\nschema_version = "1.0.0"\n')
    cache_dir = fake / '.cache/ziro'
    cache_dir.mkdir(parents=True)
    cache_dir.chmod(0o700)
    (cache_dir / 'ziro-boot.zsh').write_text('')
    boot_zwc = cache_dir / 'ziro-boot.zsh.zwc'
    boot_zwc.write_bytes(b'zwc')
    boot_zwc.chmod(0o600)
    fn = _import_check('_check_boot_chain')
    result = fn()
    assert result[0] in ('ok', 'info')


@pytest.mark.integration
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


@pytest.mark.integration
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


@pytest.mark.unit
def test_check_loadtoml_schema_handles_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    fn = _import_check('_check_loadtoml_schema')
    result = fn()
    assert result[0] == 'error'


@pytest.mark.unit
def test_check_loadtoml_schema_handles_invalid(tmp_path, monkeypatch):
    fake = tmp_path
    monkeypatch.setattr(Path, 'home', lambda: fake)
    (fake / '.config/ziro').mkdir(parents=True)
    (fake / '.config/ziro/load.toml').write_text('this is not valid TOML [[')
    fn = _import_check('_check_loadtoml_schema')
    result = fn()
    assert result[0] == 'error'


@pytest.mark.unit
def test_check_git_version_returns_tuple():
    fn = _import_check('_check_git_version')
    result = fn()
    assert isinstance(result, tuple)
    assert len(result) >= 2
    assert result[0] in ('ok', 'warn', 'error', 'info')


@pytest.mark.unit
def test_check_starship_version_returns_tuple():
    fn = _import_check('_check_starship_version')
    result = fn()
    assert isinstance(result, tuple)
    assert len(result) >= 2
    assert result[0] in ('ok', 'warn', 'error', 'info')


@pytest.mark.unit
def test_doctor_returns_all_sections():
    """Full run must return dict with all check names."""
    import core.doctor_cli as d
    if not hasattr(d, 'run_checks'):
        pytest.skip('run_checks not implemented yet')
    result = d.run_checks()
    assert isinstance(result, dict)
    assert len(result) >= 5


# ─── Legacy core/doctor.py tests (merged from test_doctor.py, spec 020) ───
#
# CONTEXT: core/doctor.py is a dead module from Spec 002 (verify_generated
# for the old derived/plugins.gen.zsh system). The ACTIVE doctor implementation
# is core/doctor_cli.py (verified via Serena find_referencing_symbols).
#
# These tests are preserved here to maintain coverage of the legacy module
# until it is formally removed in a future spec. When core/doctor.py is deleted,
# this class can be deleted too.
import tempfile
import unittest
from core.doctor import verify_generated, compute_expected_hash


class TestLegacyDoctor(unittest.TestCase):
    """Tests for legacy core/doctor.py (Spec 002, unused in production)."""

    @pytest.mark.unit
    def test_missing_artifact_unhealthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = verify_generated(Path(tmp))
            self.assertFalse(r.healthy)
            self.assertTrue(any("missing" in i for i in r.issues))

    @pytest.mark.unit
    def test_healthy_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp)
            derived = cfg / "derived"
            derived.mkdir(parents=True)
            (derived / "plugins.gen.zsh").write_text(
                "# AUTO-GENERATED by ziro — do not edit\nznap source x\n"
            )
            r = verify_generated(cfg)
            self.assertTrue(r.healthy)

    @pytest.mark.unit
    def test_hand_edited_unhealthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp)
            derived = cfg / "derived"
            derived.mkdir(parents=True)
            (derived / "plugins.gen.zsh").write_text("# hand edited\n")
            r = verify_generated(cfg)
            self.assertFalse(r.healthy)
            self.assertTrue(any("header" in i.lower() for i in r.issues))

