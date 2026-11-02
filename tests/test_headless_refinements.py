"""Unit and integration tests for spec 023 headless refinements and OSC 52."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parent.parent
HELPERS_FILE = REPO_ROOT / "lib" / "helpers.zsh"


def _run_helpers_zsh(
    script: str, env_overrides: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if env_overrides:
        env.update(env_overrides)
    cmd = ["zsh", "-f", "-c", f"source {HELPERS_FILE}; {script}"]
    return subprocess.run(cmd, env=env, capture_output=True, text=True)


def test_osc52_env_supported_kitty() -> None:
    res = _run_helpers_zsh(
        "_ziro_osc52_env_supported",
        {"KITTY_WINDOW_ID": "1", "TERM": "dumb", "DISPLAY": "", "WAYLAND_DISPLAY": ""},
    )
    assert res.returncode == 0


def test_osc52_env_supported_wezterm() -> None:
    res = _run_helpers_zsh(
        "_ziro_osc52_env_supported",
        {"WEZTERM_PANE": "1", "TERM": "dumb", "DISPLAY": "", "WAYLAND_DISPLAY": ""},
    )
    assert res.returncode == 0


def test_osc52_env_supported_alacritty() -> None:
    res = _run_helpers_zsh(
        "_ziro_osc52_env_supported",
        {"ALACRITTY_WINDOW_ID": "1", "TERM": "dumb", "DISPLAY": "", "WAYLAND_DISPLAY": ""},
    )
    assert res.returncode == 0


def test_osc52_env_supported_ghostty() -> None:
    res = _run_helpers_zsh(
        "_ziro_osc52_env_supported",
        {
            "GHOSTTY_RESOURCES_DIR": "/dummy/path",
            "TERM": "dumb",
            "DISPLAY": "",
            "WAYLAND_DISPLAY": "",
        },
    )
    assert res.returncode == 0


def test_osc52_env_supported_dumb() -> None:
    env = {
        "TERM": "dumb",
        "KITTY_WINDOW_ID": "",
        "WEZTERM_PANE": "",
        "ALACRITTY_WINDOW_ID": "",
        "GHOSTTY_RESOURCES_DIR": "",
        "TERM_PROGRAM": "",
        "ZIRO_OSC52_TERM_ALLOWLIST": "",
        "DISPLAY": "",
        "WAYLAND_DISPLAY": "",
    }
    res = _run_helpers_zsh("_ziro_osc52_env_supported", env)
    assert res.returncode == 1


def test_osc52_env_supported_allowlist() -> None:
    env = {
        "TERM": "custom-terminal-v1",
        "ZIRO_OSC52_TERM_ALLOWLIST": "custom-* otherterm",
        "KITTY_WINDOW_ID": "",
        "WEZTERM_PANE": "",
        "ALACRITTY_WINDOW_ID": "",
        "GHOSTTY_RESOURCES_DIR": "",
        "TERM_PROGRAM": "",
        "DISPLAY": "",
        "WAYLAND_DISPLAY": "",
    }
    res = _run_helpers_zsh("_ziro_osc52_env_supported", env)
    assert res.returncode == 0


def test_osc52_copy_emits_escape() -> None:
    res = _run_helpers_zsh(
        "echo hi | _ziro_osc52_copy",
        {"ZIRO_OSC52_TEST_OUTPUT": "1"},
    )
    assert res.returncode == 0
    # Payload 'hi' with newline or without -> base64 'aGkK' or 'aGk='
    assert "\x1b]52;c;" in res.stdout
    assert res.stdout.endswith("\x07")


def test_clipcopy_headless_uses_osc52() -> None:
    env = {
        "DISPLAY": "",
        "WAYLAND_DISPLAY": "",
        "TERM": "alacritty",
        "ZIRO_OSC52_TEST_OUTPUT": "1",
    }
    res = _run_helpers_zsh("echo payload123 | clipcopy", env)
    assert res.returncode == 0
    assert "\x1b]52;c;" in res.stdout
    assert "cGF5bG9hZDEyMw" in res.stdout  # base64 of payload123


def test_clipcopy_headless_no_osc52_file_buffer() -> None:
    with tempfile.TemporaryDirectory() as td:
        runtime_dir = Path(td) / "run"
        runtime_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        env = {
            "DISPLAY": "",
            "WAYLAND_DISPLAY": "",
            "TERM": "dumb",
            "ZIRO_OSC52_DA1_DISABLE": "1",
            "XDG_RUNTIME_DIR": str(runtime_dir),
            "KITTY_WINDOW_ID": "",
            "WEZTERM_PANE": "",
            "ALACRITTY_WINDOW_ID": "",
            "GHOSTTY_RESOURCES_DIR": "",
            "TERM_PROGRAM": "",
        }
        res = _run_helpers_zsh("echo buffer_test | clipcopy", env)
        assert res.returncode == 0
        buf_file = runtime_dir / ".ziro-clipboard"
        assert buf_file.is_file()
        assert buf_file.read_text().strip() == "buffer_test"
        assert stat.S_IMODE(buf_file.stat().st_mode) == 0o600


def test_clipcopy_verbose_logging() -> None:
    with tempfile.TemporaryDirectory() as td:
        runtime_dir = Path(td) / "run"
        runtime_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        env = {
            "DISPLAY": "",
            "WAYLAND_DISPLAY": "",
            "TERM": "dumb",
            "ZIRO_OSC52_DA1_DISABLE": "1",
            "ZIRO_CLIPBOARD_VERBOSE": "1",
            "XDG_RUNTIME_DIR": str(runtime_dir),
            "KITTY_WINDOW_ID": "",
            "WEZTERM_PANE": "",
            "ALACRITTY_WINDOW_ID": "",
            "GHOSTTY_RESOURCES_DIR": "",
            "TERM_PROGRAM": "",
        }
        res = _run_helpers_zsh("echo test_verbose | clipcopy", env)
        assert res.returncode == 0
        assert "clipcopy: using layer 4" in res.stderr


def test_clippaste_missing_buffer() -> None:
    with tempfile.TemporaryDirectory() as td:
        runtime_dir = Path(td) / "run"
        runtime_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        env = {
            "DISPLAY": "",
            "WAYLAND_DISPLAY": "",
            "XDG_RUNTIME_DIR": str(runtime_dir),
        }
        res = _run_helpers_zsh("clippaste", env)
        assert res.returncode == 1
        assert "clippaste: no clipboard content" in res.stderr


def test_clippaste_reads_buffer() -> None:
    with tempfile.TemporaryDirectory() as td:
        runtime_dir = Path(td) / "run"
        runtime_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        buf_file = runtime_dir / ".ziro-clipboard"
        buf_file.write_text("pasted_content\n")
        buf_file.chmod(0o600)

        env = {
            "DISPLAY": "",
            "WAYLAND_DISPLAY": "",
            "XDG_RUNTIME_DIR": str(runtime_dir),
        }
        res = _run_helpers_zsh("clippaste", env)
        assert res.returncode == 0
        assert res.stdout.strip() == "pasted_content"


def test_open_headless_text_file(tmp_path: Path) -> None:
    txt_file = tmp_path / "sample.txt"
    txt_file.write_text("hello headless world\n")

    env = {
        "DISPLAY": "",
        "WAYLAND_DISPLAY": "",
        "PAGER": "cat",
    }
    res = _run_helpers_zsh(f"xdg-open '{txt_file}'", env)
    assert res.returncode == 0
    assert "hello headless world" in res.stdout


def test_open_headless_binary(tmp_path: Path) -> None:
    bin_file = tmp_path / "binary.bin"
    bin_file.write_bytes(b"\x00\x01\x02\x03\xff")

    env = {
        "DISPLAY": "",
        "WAYLAND_DISPLAY": "",
    }
    res = _run_helpers_zsh(f"xdg-open '{bin_file}'", env)
    assert res.returncode == 1
    assert "cannot open" in res.stderr
    assert "headless environment" in res.stderr


def test_open_headless_url() -> None:
    env = {
        "DISPLAY": "",
        "WAYLAND_DISPLAY": "",
    }
    res = _run_helpers_zsh("xdg-open https://example.com", env)
    assert res.returncode == 1
    assert "cannot open URLs in headless environment" in res.stderr


def test_doctor_gui_fast_path(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.doctor_cli import _check_headless_capabilities

    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)

    res = _check_headless_capabilities()
    assert res[0] == "ok"
    assert "GUI session" in res[1]
    assert res["status"] == "ok"


def test_doctor_headless_supported_alacritty(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.doctor_cli import _check_headless_capabilities

    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setenv("TERM", "alacritty")
    monkeypatch.delenv("TERM_PROGRAM", raising=False)

    res = _check_headless_capabilities()
    assert res[0] == "ok"
    assert "terminal: alacritty" in res[1]


def test_doctor_headless_warning_iterm(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.doctor_cli import OSC52_ENABLE_GUIDE, _check_headless_capabilities

    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")

    res = _check_headless_capabilities()
    assert res[0] == "warn"
    assert "OSC 52 NOT enabled for iTerm.app" in res[1]
    assert res[2] == OSC52_ENABLE_GUIDE["iTerm.app"]


def test_doctor_headless_warning_tmux(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.doctor_cli import OSC52_ENABLE_GUIDE, _check_headless_capabilities

    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("TERM_PROGRAM", raising=False)
    monkeypatch.setenv("TERM", "tmux-256color")

    res = _check_headless_capabilities()
    assert res[0] == "warn"
    assert "OSC 52 NOT enabled for tmux" in res[1]
    assert res[2] == OSC52_ENABLE_GUIDE["tmux"]


def test_doctor_headless_info_apple_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.doctor_cli import _check_headless_capabilities

    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setenv("TERM_PROGRAM", "Apple_Terminal")

    res = _check_headless_capabilities()
    assert res[0] == "info"
    assert "Apple_Terminal" in res[1]
    assert "pbcopy fallback" in res[1]


def test_doctor_headless_info_dumb(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.doctor_cli import _check_headless_capabilities

    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("TERM", "dumb")
    monkeypatch.delenv("TERM_PROGRAM", raising=False)
    monkeypatch.delenv("KITTY_WINDOW_ID", raising=False)
    monkeypatch.delenv("WEZTERM_PANE", raising=False)
    monkeypatch.delenv("ALACRITTY_WINDOW_ID", raising=False)
    monkeypatch.delenv("GHOSTTY_RESOURCES_DIR", raising=False)

    res = _check_headless_capabilities()
    assert res[0] == "info"
    assert "support unknown" in res[1]
    assert "file buffer fallback" in res[1]
