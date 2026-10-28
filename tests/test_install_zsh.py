"""Hermetic test suite for install.zsh and Python engine bootstrap."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _isolated_env(fake_home: Path) -> dict[str, str]:
    """Build a completely hermetic environment for test subshells."""
    env = os.environ.copy()
    env["HOME"] = str(fake_home)
    env["ZIRO_SKIP_VENV_BOOTSTRAP"] = "1"
    env["PYTHONPATH"] = str(REPO_ROOT)
    for k in (
        "ZIRO_HOME",
        "ZIRO_CONFIG",
        "ZIRO_CACHE",
        "ZIRO_DATA",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "XDG_DATA_HOME",
    ):
        env.pop(k, None)
    return env


class TestInstallZsh(unittest.TestCase):
    def test_list_commands_flag(self):
        """Verify python -m core --list-commands outputs expected subcommands."""
        proc = subprocess.run(
            [sys.executable, "-m", "core", "--list-commands"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        cmds = proc.stdout.strip().split()
        self.assertIn("sync", cmds)
        self.assertIn("doctor", cmds)
        self.assertIn("install", cmds)
        self.assertIn("analyze", cmds)
        self.assertIn("plugin", cmds)

    def test_install_zsh_syntax(self):
        """Validate install.zsh syntax with zsh -n."""
        proc = subprocess.run(
            ["zsh", "-n", str(REPO_ROOT / "install.zsh")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, f"zsh -n failed: {proc.stderr}")

    def test_install_from_checkout_hermetic(self):
        """Test running install.zsh from an existing checkout in an isolated HOME."""
        with tempfile.TemporaryDirectory() as td:
            fake_home = Path(td) / "fake_home"
            fake_home.mkdir()

            env = _isolated_env(fake_home)

            proc = subprocess.run(
                ["zsh", str(REPO_ROOT / "install.zsh"), "--no-activate", "--default"],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, f"install.zsh failed: {proc.stderr}\nstdout: {proc.stdout}")

            cfg = fake_home / ".config" / "ziro"
            self.assertTrue((cfg / "boot.zsh").is_file())
            self.assertTrue((cfg / "load.toml").is_file())
            self.assertTrue((cfg / "defaults.toml").is_file())

            boot_content = (cfg / "boot.zsh").read_text(encoding="utf-8")
            self.assertIn("export ZIRO_HOME=", boot_content)
            self.assertIn("export ZIRO_CONFIG=", boot_content)
            self.assertIn("export ZIRO_CACHE=", boot_content)

    def test_activation_idempotency_and_backup(self):
        """Verify that multiple install runs append only once to .zshrc and create backup."""
        with tempfile.TemporaryDirectory() as td:
            fake_home = Path(td) / "fake_home"
            fake_home.mkdir()
            zshrc = fake_home / ".zshrc"
            zshrc.write_text("# Existing user zshrc\nexport FOO=bar\n", encoding="utf-8")

            env = _isolated_env(fake_home)

            proc1 = subprocess.run(
                ["zsh", str(REPO_ROOT / "install.zsh"), "--default"],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc1.returncode, 0, f"Run 1 failed: {proc1.stderr}")

            content1 = zshrc.read_text(encoding="utf-8")
            self.assertIn("source ", content1)
            self.assertIn("boot.zsh", content1)

            backups = list(fake_home.glob(".zshrc.bak.*"))
            self.assertGreaterEqual(len(backups), 1)

            proc2 = subprocess.run(
                ["zsh", str(REPO_ROOT / "install.zsh"), "--default"],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc2.returncode, 0, f"Run 2 failed: {proc2.stderr}")

            content2 = zshrc.read_text(encoding="utf-8")
            count = sum(1 for line in content2.splitlines() if "boot.zsh" in line)
            self.assertEqual(count, 1, f"Expected exactly 1 boot.zsh reference, got {count}")

    def test_unrelated_repo_rejection(self):
        """Test that an unrelated repo in target directory is rejected (Exit 14)."""
        with tempfile.TemporaryDirectory() as td:
            fake_target = Path(td) / "unrelated_repo"
            fake_target.mkdir()
            subprocess.run(["git", "init"], cwd=str(fake_target), capture_output=True)

            env = os.environ.copy()
            env["ZIRO_HOME"] = str(fake_target)
            env["HOME"] = td

            proc = subprocess.run(
                ["zsh", str(REPO_ROOT / "install.zsh"), "--default"],
                cwd=td,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 14, f"Expected exit 14, got {proc.returncode}")

    def test_truncated_stream_safety(self):
        """Verify that a truncated stream terminates with syntax error and runs nothing."""
        script_content = (REPO_ROOT / "install.zsh").read_text(encoding="utf-8")
        truncated = "\n".join(script_content.splitlines()[:50])

        proc = subprocess.run(
            ["zsh"],
            input=truncated,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(proc.returncode, 0)

    def test_piped_install_from_checkout(self):
        """Test cat install.zsh | zsh with an existing verified checkout."""
        with tempfile.TemporaryDirectory() as td:
            fake_home = Path(td) / "fake_home"
            fake_home.mkdir()
            (fake_home / ".ziro").symlink_to(REPO_ROOT)

            env = _isolated_env(fake_home)

            script_text = (REPO_ROOT / "install.zsh").read_text(encoding="utf-8")
            proc = subprocess.run(
                ["zsh", "-s", "--", "--no-activate", "--default"],
                input=script_text,
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, f"Piped install failed: {proc.stderr}")
            self.assertTrue((fake_home / ".config" / "ziro" / "boot.zsh").is_file())

    def test_fresh_shell_unset_ziro_home_loads_ziro(self):
        """REGRESSION: Fresh shell with ZIRO_HOME unset sources boot.zsh and ziro is available."""
        with tempfile.TemporaryDirectory() as td:
            fake_home = Path(td) / "fake_home"
            fake_home.mkdir()

            env = _isolated_env(fake_home)

            proc_inst = subprocess.run(
                ["zsh", str(REPO_ROOT / "install.zsh"), "--no-activate", "--default"],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc_inst.returncode, 0)

            boot_zsh = fake_home / ".config" / "ziro" / "boot.zsh"
            self.assertTrue(boot_zsh.is_file())

            clean_env = _isolated_env(fake_home)
            clean_env["PATH"] = os.environ["PATH"]
            test_sh = f'source "{boot_zsh}"; ziro --version'
            proc_test = subprocess.run(
                ["zsh", "-f", "-c", test_sh],
                env=clean_env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(proc_test.returncode, 0, f"Fresh shell failed: {proc_test.stderr}")
            self.assertIn("ziro-shell v", proc_test.stdout)


if __name__ == "__main__":
    unittest.main()
