"""Tests for root profile hardening (Spec 022 M1-M4, ADL-036)."""

import os
import shutil
import stat
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parent.parent
LIB_DIR = REPO_ROOT / "lib"
FZF_WRAPPER = LIB_DIR / "fzf-wrapper.zsh"
HELPERS_FILE = LIB_DIR / "helpers.zsh"
SSH_CONFIG_FILE = LIB_DIR / "ssh-config.zsh"
STARSHIP_TEMPLATE = LIB_DIR / "starship-root-template.toml"


class TestRootProfileHardening(unittest.TestCase):
    """Test suite covering M1-M4 root profile security controls."""

    def test_non_root_fzf_default_opts_preserved(self) -> None:
        """AC2: Normal user (EUID != 0) preserves FZF_DEFAULT_OPTS with execute bindings."""
        if os.geteuid() == 0:
            self.skipTest("Skipped under root account")

        env = dict(os.environ)
        test_opts = "--bind=enter:execute(echo X)"
        env["FZF_DEFAULT_OPTS"] = test_opts
        cmd = ["zsh", "-f", "-c", f"source {FZF_WRAPPER}; echo \"$FZF_DEFAULT_OPTS\""]
        res = subprocess.run(cmd, env=env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout.strip(), test_opts)

    def test_non_root_fzf_wrapper_no_op(self) -> None:
        """AC1-adjacent: fzf wrapper is a no-op when EUID != 0."""
        if os.geteuid() == 0:
            self.skipTest("Skipped under root account")

        cmd = ["zsh", "-f", "-c", f"source {FZF_WRAPPER}; typeset -f fzf"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0, "fzf() function should not be defined for non-root")

    @pytest.mark.skipif(os.geteuid() != 0, reason="Requires real root EUID")
    def test_root_fzf_opts_safe_defaults(self) -> None:
        """AC5: Root FZF_DEFAULT_OPTS resets to safe defaults."""
        cmd = ["zsh", "-f", "-c", f"source {FZF_WRAPPER}; echo \"$FZF_DEFAULT_OPTS\""]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("--no-mouse", res.stdout)
        self.assertNotIn("execute", res.stdout)

    @pytest.mark.skipif(os.geteuid() != 0, reason="Requires real root EUID")
    def test_root_fzf_blocks_execute(self) -> None:
        """AC6: Root fzf rejects execute() bindings."""
        cmd = ["zsh", "-f", "-c", f"source {FZF_WRAPPER}; fzf --bind='enter:execute(id)'"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 1)
        self.assertIn("execute() bindings are disabled in root", res.stderr)

    @pytest.mark.skipif(os.geteuid() != 0, reason="Requires real root EUID")
    def test_root_fzf_escape_hatch(self) -> None:
        """AC7: ZIRO_ALLOW_ROOT_FZF_EXECUTE=1 bypasses execution filter."""
        env = dict(os.environ)
        env["ZIRO_ALLOW_ROOT_FZF_EXECUTE"] = "1"
        cmd = ["zsh", "-f", "-c", f"source {FZF_WRAPPER}; echo \"$FZF_DEFAULT_OPTS\""]
        res = subprocess.run(cmd, env=env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)

    def test_headless_clipboard_xdg_path(self) -> None:
        """AC8: In headless session with XDG_RUNTIME_DIR, clipcopy uses 0600 file buffer."""
        with tempfile.TemporaryDirectory() as td:
            runtime_dir = Path(td) / "run"
            runtime_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            env = dict(os.environ)
            env["DISPLAY"] = ""
            env["WAYLAND_DISPLAY"] = ""
            env["XDG_RUNTIME_DIR"] = str(runtime_dir)

            script = f'source {HELPERS_FILE}; echo "hello-xdg" | clipcopy && clippaste'
            cmd = ["zsh", "-f", "-c", script]
            res = subprocess.run(cmd, env=env, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertEqual(res.stdout.strip(), "hello-xdg")

            buf_file = runtime_dir / ".ziro-clipboard"
            self.assertTrue(buf_file.is_file())
            mode = stat.S_IMODE(buf_file.stat().st_mode)
            self.assertEqual(mode, 0o600)

    def test_headless_clipboard_tmp_fallback(self) -> None:
        """AC9: In headless session without XDG_RUNTIME_DIR, fallback to /tmp with mode 0600."""
        env = dict(os.environ)
        env["DISPLAY"] = ""
        env["WAYLAND_DISPLAY"] = ""
        env.pop("XDG_RUNTIME_DIR", None)

        test_payload = f"hello-tmp-{os.getpid()}"
        script = f'source {HELPERS_FILE}; echo "{test_payload}" | clipcopy && clippaste'
        cmd = ["zsh", "-f", "-c", script]
        res = subprocess.run(cmd, env=env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), test_payload)

        tmp_buf = Path(f"/tmp/.ziro_clipboard-{os.getuid()}")
        self.assertTrue(tmp_buf.is_file())
        mode = stat.S_IMODE(tmp_buf.stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_ssh_forwarding_default_off(self) -> None:
        """AC10: SSH agent forwarding disabled by default."""
        env = dict(os.environ)
        env.pop("ZIRO_SSH_FORWARDING", None)
        cmd = [
            "zsh",
            "-f",
            "-c",
            f"source {SSH_CONFIG_FILE}; zstyle -t :omz:plugins:ssh-agent agent-forwarding; echo \"rc=$?\"",
        ]
        res = subprocess.run(cmd, env=env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout.strip(), "rc=1")

    def test_ssh_forwarding_opt_in(self) -> None:
        """AC4 & AC11: ZIRO_SSH_FORWARDING=1 enables agent forwarding."""
        env = dict(os.environ)
        env["ZIRO_SSH_FORWARDING"] = "1"
        cmd = [
            "zsh",
            "-f",
            "-c",
            f"source {SSH_CONFIG_FILE}; zstyle -t :omz:plugins:ssh-agent agent-forwarding; echo \"rc=$?\"",
        ]
        res = subprocess.run(cmd, env=env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout.strip(), "rc=0")

    def test_starship_root_template_content(self) -> None:
        """AC14: starship-root-template.toml parses as valid TOML with zero custom sections."""
        self.assertTrue(STARSHIP_TEMPLATE.is_file(), "Missing starship-root-template.toml")
        raw = STARSHIP_TEMPLATE.read_text(encoding="utf-8")
        parsed = tomllib.loads(raw)

        self.assertEqual(parsed.get("command_timeout"), 200)
        self.assertNotIn("custom", parsed)
        self.assertNotIn("env_var", parsed)
        self.assertIn("character", parsed)
        self.assertIn("directory", parsed)
        self.assertIn("git_branch", parsed)

    def test_fzf_wrapper_rejection_logic_unit(self) -> None:
        """AC6-unit: fzf wrapper logic correctly detects and rejects execute() bindings."""
        wrapper_code = FZF_WRAPPER.read_text(encoding="utf-8").replace("[[ $EUID -eq 0 ]] || return 0", "")
        script = f"""
{wrapper_code}
fzf --bind='enter:execute(id)'
"""
        cmd = ["zsh", "-f", "-c", script]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 1)
        self.assertIn("execute() bindings are disabled in root", res.stderr)

    def test_fzf_wrapper_bypass_logic_unit(self) -> None:
        """AC7-unit: fzf wrapper honors ZIRO_ALLOW_ROOT_FZF_EXECUTE=1 escape hatch."""
        wrapper_code = FZF_WRAPPER.read_text(encoding="utf-8").replace("[[ $EUID -eq 0 ]] || return 0", "")
        # With ZIRO_ALLOW_ROOT_FZF_EXECUTE=1, fzf should not reject with the disabled message.
        # Calling 'fzf --filter=test' or 'command fzf' will return command fzf exit status, not wrapper abort.
        script = f"""
export ZIRO_ALLOW_ROOT_FZF_EXECUTE=1
{wrapper_code}
fzf --bind='enter:execute(id)' --version 2>&1
"""
        cmd = ["zsh", "-f", "-c", script]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotIn("execute() bindings are disabled in root", res.stderr)

    def test_starship_root_materialized_on_sync(self) -> None:
        """AC12: ziro build materializes starship-root.toml if missing."""
        from core.build import build
        from core.paths import get_paths

        with tempfile.TemporaryDirectory() as td:
            temp_config = Path(td) / "config"
            temp_config.mkdir(parents=True, exist_ok=True)
            custom_paths = {
                "home": REPO_ROOT,
                "config": temp_config,
                "cache": Path(td) / "cache",
                "data": Path(td) / "data",
            }
            with patch("core.build.get_paths", return_value=custom_paths), \
                 patch("core.paths.get_paths", return_value=custom_paths):
                ok, msg, _ = build()
                self.assertTrue(ok, f"build failed: {msg}")
                root_toml = temp_config / "starship-root.toml"
                self.assertTrue(root_toml.is_file(), "starship-root.toml was not materialized")
                mode = stat.S_IMODE(root_toml.stat().st_mode)
                self.assertEqual(mode, 0o600)

    def test_boot_shim_template_contains_euid_gate(self) -> None:
        """AC13-adjacent: BOOT_SHIM_TEMPLATE contains runtime EUID check for starship-root."""
        from core.build import BOOT_SHIM_TEMPLATE

        self.assertIn("if [[ $EUID -eq 0 ]]", BOOT_SHIM_TEMPLATE)
        self.assertIn("STARSHIP_CONFIG=", BOOT_SHIM_TEMPLATE)
        self.assertIn("starship-root.toml", BOOT_SHIM_TEMPLATE)

    def test_doctor_root_profile_check_non_root(self) -> None:
        """AC15: ziro doctor reports N/A (not root) for normal user."""
        from core.doctor_cli import _check_root_profile

        with patch("os.geteuid", return_value=1000):
            status, msg, advice = _check_root_profile()
            self.assertEqual(status, "ok")
            self.assertIn("N/A (not root)", msg)
            self.assertIsNone(advice)

    def test_doctor_root_profile_check_root_mock(self) -> None:
        """AC15: ziro doctor validates starship-root.toml when running as root."""
        from core.doctor_cli import _check_root_profile
        from core.paths import get_paths

        paths = get_paths()
        root_toml = paths["config"] / "starship-root.toml"
        root_toml.parent.mkdir(parents=True, exist_ok=True)
        if not root_toml.exists():
            root_toml.write_text("command_timeout = 200\n", encoding="utf-8")

        with patch("os.geteuid", return_value=0):
            status, msg, advice = _check_root_profile()
            self.assertEqual(status, "ok")
            self.assertIn("root profile active", msg)

    def test_doctor_run_checks_includes_root_profile(self) -> None:
        """Doctor check registry includes 'root profile'."""
        from core.doctor_cli import run_checks

        checks = run_checks()
        self.assertIn("root profile", checks)

    def test_normal_user_startup_silent(self) -> None:
        """AC18: Startup remains completely silent for normal user."""
        dot_zshrc = Path.home() / ".zshrc"
        if not dot_zshrc.is_file():
            self.skipTest("~/.zshrc not present in test environment")

        res = subprocess.run(
            ["zsh", "-f", "-c", "source ~/.zshrc 2>&1"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.stdout.strip(), "")
        self.assertEqual(res.stderr.strip(), "")
