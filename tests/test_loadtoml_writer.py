"""Roundtrip tests: write then re-read load.toml, [user] preserved."""
import tomllib
from pathlib import Path
from core.loadtoml_writer import write_load_toml, load_external_overrides


def test_write_and_read_tool(tmp_path):
    data = {
        "meta": {"schema_version": "1.0.0"},
        "tool": [
            {
                "name": "starship",
                "timing": "eager",
                "method": "eval-cache",
                "cache_path": "~/.cache/ziro/eval-cache/starship.zsh",
                "reason": "eager: category=prompt",
            },
        ],
    }
    p = tmp_path / "load.toml"
    write_load_toml(data, str(p))
    with p.open("rb") as f:
        parsed = tomllib.load(f)
    assert parsed["meta"]["schema_version"] == "1.0.0"
    assert len(parsed["tool"]) == 1
    assert parsed["tool"][0]["name"] == "starship"
    assert parsed["tool"][0]["timing"] == "eager"


def test_user_section_preserved(tmp_path):
    data = {
        "meta": {"schema_version": "1.0.0"},
        "tool": [],
        "user": {
            "override": [
                {"name": "fzf", "timing": "eager", "reason": "user forced eager"},
            ]
        },
    }
    p = tmp_path / "load.toml"
    write_load_toml(data, str(p))
    with p.open("rb") as f:
        parsed = tomllib.load(f)
    assert "user" in parsed
    assert "override" in parsed["user"]
    assert parsed["user"]["override"][0]["name"] == "fzf"
    assert parsed["user"]["override"][0]["timing"] == "eager"


def test_trigger_keys_list_of_dicts(tmp_path):
    data = {
        "meta": {"schema_version": "1.0.0"},
        "tool": [
            {
                "name": "fzf",
                "timing": "on-demand",
                "method": "eval-cache",
                "trigger": "key",
                "trigger_keys": [
                    {"key": "^R", "widget": "fzf-history-widget"},
                    {"key": "^T", "widget": "fzf-file-widget"},
                ],
            },
        ],
    }
    p = tmp_path / "load.toml"
    write_load_toml(data, str(p))
    with p.open("rb") as f:
        parsed = tomllib.load(f)
    keys = parsed["tool"][0]["trigger_keys"]
    assert len(keys) == 2
    assert keys[0]["key"] == "^R"


def test_external_overrides_missing_returns_empty(tmp_path):
    result = load_external_overrides(str(tmp_path / "nope.toml"))
    assert result == {}


def test_external_overrides_parsed(tmp_path):
    f = tmp_path / "ov.toml"
    f.write_text('[[override]]\nname = "fzf"\ntiming = "eager"\n', encoding="utf-8")
    result = load_external_overrides(str(f))
    assert "override" in result
    assert result["override"][0]["name"] == "fzf"
