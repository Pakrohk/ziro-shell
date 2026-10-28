"""Tests for core/build.py (ziro sync build pipeline)."""

import os
from pathlib import Path
import tempfile
import tomllib
import pytest

from core.build import (
    get_paths,
    load_manifest,
    validate_manifest,
    apply_overrides,
    render_defer_core,
    render_eager_section,
    render_deferred_section,
    render_ondemand_section,
    render_boot_script,
    compile_zwc,
    write_boot_shim,
    build,
    default_manifest_content,
)


@pytest.fixture
def sample_manifest() -> dict:
    content = default_manifest_content()
    return tomllib.loads(content)


def test_validate_manifest_valid(sample_manifest):
    errors = validate_manifest(sample_manifest)
    assert errors == []


def test_validate_manifest_missing_section():
    data = {"meta": {}, "tool": []}
    errors = validate_manifest(data)
    assert any("boot" in e for e in errors)
    assert any("defer" in e for e in errors)


def test_validate_manifest_invalid_timing(sample_manifest):
    sample_manifest["tool"][0]["timing"] = "invalid_timing"
    errors = validate_manifest(sample_manifest)
    assert any("invalid timing" in e for e in errors)


def test_validate_manifest_duplicate_name(sample_manifest):
    sample_manifest["tool"].append(dict(sample_manifest["tool"][0]))
    errors = validate_manifest(sample_manifest)
    assert any("Duplicate tool name" in e for e in errors)


def test_validate_manifest_conflicts(sample_manifest):
    # Add conflicting tools both enabled
    sample_manifest["tool"].append({
        "name": "zsh-autosuggestions",
        "timing": "deferred",
        "order": 50,
        "method": "source",
        "conflicts_with": ["ziro-ghost"],
        "enabled": True,
    })
    errors = validate_manifest(sample_manifest)
    assert any("conflicts with active tool" in e for e in errors)


def test_apply_overrides_user_section(sample_manifest):
    tools = sample_manifest["tool"]
    user_sec = {
        "override": [
            {
                "name": "fzf",
                "timing": "eager",
                "order": 5,
                "reason": "Test override",
            }
        ]
    }
    merged = apply_overrides(tools, user_sec)
    fzf_tool = next(t for t in merged if t["name"] == "fzf")
    assert fzf_tool["timing"] == "eager"
    assert fzf_tool["order"] == 5


def test_apply_overrides_external_override(tmp_path, sample_manifest):
    tools = sample_manifest["tool"]
    user_sec = {
        "override": [
            {"name": "fzf", "timing": "deferred"}
        ]
    }
    ext_file = tmp_path / "override.toml"
    ext_file.write_text("""
[[override]]
name = "fzf"
timing = "eager"
""", encoding="utf-8")

    # External override wins over [user]
    merged = apply_overrides(tools, user_sec, ext_file)
    fzf_tool = next(t for t in merged if t["name"] == "fzf")
    assert fzf_tool["timing"] == "eager"


def test_render_sections(sample_manifest):
    tools = sample_manifest["tool"]
    eager_out = render_eager_section(tools)
    assert "Section 2: Eager tools" in eager_out
    assert "fpath=(" in eager_out
    assert "compinit" in eager_out

    def_out = render_deferred_section(tools)
    assert "Section 3: Deferred tasks" in def_out
    assert "ziro-defer --stage=5" in def_out

    ondemand_out = render_ondemand_section(tools)
    assert "Section 4: On-demand proxies" in ondemand_out
    assert "ziro-defer-bind-widget" in ondemand_out
    assert "_ziro_proxy_zoxide" in ondemand_out


def test_build_end_to_end(tmp_path, monkeypatch):
    home_dir = Path("/home/ali/.ziro")
    config_dir = tmp_path / "config" / "ziro"
    data_dir = tmp_path / "data" / "ziro"
    cache_dir = tmp_path / "cache" / "ziro"

    monkeypatch.setenv("ZIRO_HOME", str(home_dir))
    monkeypatch.setenv("ZIRO_CONFIG", str(config_dir))
    monkeypatch.setenv("ZIRO_DATA", str(data_dir))
    monkeypatch.setenv("ZIRO_CACHE", str(cache_dir))

    load_toml = config_dir / "load.toml"
    ok, msg, counts = build(load_toml_path=load_toml)
    assert ok is True
    assert "Synced:" in msg

    boot_zsh = cache_dir / "ziro-boot.zsh"
    boot_zwc = cache_dir / "ziro-boot.zsh.zwc"
    boot_shim = config_dir / "boot.zsh"

    assert boot_zsh.is_file()
    assert boot_zwc.is_file()
    assert boot_shim.is_file()
    assert counts["eager"] > 0
    assert counts["deferred"] > 0


def test_compile_eager_artifacts_returns_dict(tmp_path):
    """compile_eager_artifacts should return dict with compiled/skipped/errors."""
    from core.build import compile_eager_artifacts
    manifest = {"tool": []}
    result = compile_eager_artifacts(manifest, timeout_s=5)
    assert isinstance(result, dict)
    assert "compiled" in result
    assert "skipped" in result
    assert "errors" in result


def test_compile_eager_artifacts_skips_missing(tmp_path):
    """Missing cache_path should be added to skipped, not error."""
    from core.build import compile_eager_artifacts
    manifest = {"tool": [
        {"name": "x", "timing": "eager", "method": "eval-cache",
         "cache_path": str(tmp_path / "does-not-exist.zsh")}
    ]}
    result = compile_eager_artifacts(manifest, timeout_s=5)
    assert len(result["skipped"]) == 1
    assert len(result["errors"]) == 0


def test_compile_eager_artifacts_ignores_non_eager(tmp_path):
    """Non-eager tools should not be touched."""
    from core.build import compile_eager_artifacts
    manifest = {"tool": [
        {"name": "y", "timing": "deferred", "method": "source",
         "path": str(tmp_path / "whatever.zsh")}
    ]}
    result = compile_eager_artifacts(manifest, timeout_s=5)
    assert len(result["compiled"]) == 0
    assert len(result["skipped"]) == 0
    assert len(result["errors"]) == 0


def test_compile_eager_artifacts_compiles_real_file(tmp_path):
    """A real .zsh file should compile to .zwc."""
    from core.build import compile_eager_artifacts
    src = tmp_path / "test.zsh"
    src.write_text("echo hello\n")
    manifest = {"tool": [
        {"name": "z", "timing": "eager", "method": "eval-cache",
         "cache_path": str(src)}
    ]}
    result = compile_eager_artifacts(manifest, timeout_s=10)
    assert str(src) in result["compiled"]
    assert (tmp_path / "test.zsh.zwc").is_file()


def test_validate_zwc_freshness_passes_when_fresh(tmp_path):
    """All .zwc newer than source -> no error."""
    from core.build import _validate_zwc_freshness
    import os, time
    src = tmp_path / "x.zsh"
    src.write_text("echo x\n")
    zwc = tmp_path / "x.zsh.zwc"
    zwc.write_bytes(b"zwc")
    # Make .zwc newer
    future = time.time() + 10
    os.utime(zwc, (future, future))
    manifest = {"tool": [
        {"name": "x", "timing": "eager", "method": "source",
         "path": str(src)}
    ]}
    result = _validate_zwc_freshness(manifest, strict=True)
    assert len(result["ok"]) == 1
    assert len(result["missing"]) == 0
    assert len(result["stale"]) == 0


def test_validate_zwc_freshness_fails_when_missing(tmp_path):
    """Missing .zwc -> ValueError in strict mode."""
    from core.build import _validate_zwc_freshness
    src = tmp_path / "x.zsh"
    src.write_text("echo x\n")
    manifest = {"tool": [
        {"name": "x", "timing": "eager", "method": "source",
         "path": str(src)}
    ]}
    import pytest
    with pytest.raises(ValueError, match="missing .zwc"):
        _validate_zwc_freshness(manifest, strict=True)


def test_validate_zwc_freshness_fails_when_stale(tmp_path):
    """Stale .zwc (older than source) -> ValueError in strict mode."""
    from core.build import _validate_zwc_freshness
    import os, time
    src = tmp_path / "x.zsh"
    src.write_text("echo x\n")
    zwc = tmp_path / "x.zsh.zwc"
    zwc.write_bytes(b"zwc")
    # Make .zwc OLDER than source
    past = time.time() - 100
    os.utime(zwc, (past, past))
    manifest = {"tool": [
        {"name": "x", "timing": "eager", "method": "source",
         "path": str(src)}
    ]}
    import pytest
    with pytest.raises(ValueError, match="stale"):
        _validate_zwc_freshness(manifest, strict=True)


def test_validate_zwc_freshness_non_strict_returns_dict(tmp_path):
    """Non-strict mode returns dict instead of raising."""
    from core.build import _validate_zwc_freshness
    src = tmp_path / "x.zsh"
    src.write_text("echo x\n")
    manifest = {"tool": [
        {"name": "x", "timing": "eager", "method": "source",
         "path": str(src)}
    ]}
    result = _validate_zwc_freshness(manifest, strict=False)
    assert len(result["missing"]) == 1
    assert len(result["ok"]) == 0


def test_validate_zwc_ignores_non_eager(tmp_path):
    """Deferred/on-demand tools not checked."""
    from core.build import _validate_zwc_freshness
    manifest = {"tool": [
        {"name": "y", "timing": "deferred", "method": "source",
         "path": str(tmp_path / "missing.zsh")}
    ]}
    result = _validate_zwc_freshness(manifest, strict=True)
    assert len(result["missing"]) == 0
    assert len(result["stale"]) == 0


def test_render_deferred_section_syntax_highlighting_loads_last():
    """Syntax highlighting plugins must sort after any other deferred plugins."""
    tools = [
        {"name": "fast-syntax-highlighting", "timing": "deferred", "category": "syntax_highlighting", "order": 1, "path": "/path/to/fsh.zsh", "enabled": True},
        {"name": "my-custom-plugin", "timing": "deferred", "category": "custom", "order": 100, "path": "/path/to/custom.zsh", "enabled": True},
        {"name": "fzf-tab", "timing": "deferred", "category": "completion", "order": 50, "path": "/path/to/fzf-tab.zsh", "enabled": True},
    ]
    out = render_deferred_section(tools)
    idx_fzf_tab = out.index("fzf-tab")
    idx_custom = out.index("my-custom-plugin")
    idx_fsh = out.index("fast-syntax-highlighting")

    assert idx_fzf_tab < idx_custom
    assert idx_custom < idx_fsh


def test_render_ondemand_section_refreshes_highlight_widgets():
    """On-demand key loader functions must invoke _zsh_highlight_bind_widgets to prevent ZLE desync."""
    tools = [
        {
            "name": "fzf",
            "timing": "on-demand",
            "trigger": "key",
            "trigger_keys": [{"key": "^R", "widget": "fzf-history-widget"}],
            "cache_path": "/path/to/fzf.zsh",
            "enabled": True,
        }
    ]
    out = render_ondemand_section(tools)
    assert "_zsh_highlight_bind_widgets" in out


