"""Tests for ziro shell completion generation (Spec 008 R10, Phase 6e).

Layer: 3 (Python CLI tests)
Spec: 008 R10, SC-1, SC-2
"""

from __future__ import annotations

import io
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.completion_cli import (
    cmd_completion,
    generate_zsh_completion,
    get_completion_data,
)


class TestCompletion(unittest.TestCase):
    def test_get_completion_data_structure(self) -> None:
        data = get_completion_data()
        self.assertIn("commands", data)
        self.assertIn("subcommands", data)
        self.assertIn("flags", data)

        cmd_names = [c[0] for c in data["commands"]]
        expected_cmds = [
            "install", "plugin", "tag", "suggest", "theme",
            "prompt", "config", "doctor", "bench", "completion", "update", "help",
        ]
        for ec in expected_cmds:
            self.assertIn(ec, cmd_names, f"Expected {ec} in completion commands")

    def test_generate_zsh_completion_has_compdef_and_ziro_func(self) -> None:
        script = generate_zsh_completion()
        self.assertTrue(script.startswith("#compdef ziro"))
        self.assertIn("_ziro() {", script)
        self.assertIn("compdef _ziro ziro", script)

    def test_completion_covers_all_top_level_commands(self) -> None:
        script = generate_zsh_completion()
        for cmd in ("install", "plugin", "tag", "suggest", "theme", "prompt", "config", "doctor", "bench", "completion", "update", "help"):
            self.assertIn(f"'{cmd}:", script, f"Missing '{cmd}:' in generated completion script")

    def test_completion_covers_subcommands(self) -> None:
        script = generate_zsh_completion()
        self.assertIn("_ziro_plugin() {", script)
        self.assertIn("_ziro_tag() {", script)
        self.assertIn("_ziro_config() {", script)
        self.assertIn("_ziro_theme() {", script)
        self.assertIn("_ziro_prompt() {", script)
        self.assertIn("_ziro_suggest() {", script)

        # Plugin subcommands
        for sub in ("add", "remove", "list", "show"):
            self.assertIn(f"'{sub}:", script)

        # Tag subcommands
        for sub in ("list", "show", "add", "remove", "reset", "define"):
            self.assertIn(f"'{sub}:", script)

    def test_completion_covers_flags(self) -> None:
        script = generate_zsh_completion()
        self.assertIn("--default", script)
        self.assertIn("--custom", script)
        self.assertIn("--dry-run", script)
        self.assertIn("--help", script)
        self.assertIn("--verbose", script)
        self.assertIn("--iters", script)

    def test_cmd_completion_default_zsh(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd_completion([])
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("#compdef ziro", out)
        self.assertIn("_ziro()", out)

    def test_cmd_completion_unsupported_shell(self) -> None:
        buf = io.StringIO()
        err_buf = io.StringIO()
        old_err = sys.stderr
        try:
            sys.stderr = err_buf
            with redirect_stdout(buf):
                rc = cmd_completion(["bash"])
        finally:
            sys.stderr = old_err

        self.assertEqual(rc, 1)
        self.assertIn("unsupported shell 'bash'", err_buf.getvalue())

    def test_completion_script_zsh_syntax(self) -> None:
        script = generate_zsh_completion()
        run = subprocess.run(
            ["zsh", "-n"],
            input=script,
            capture_output=True,
            text=True,
        )
        self.assertEqual(run.returncode, 0, f"zsh -n syntax error: {run.stderr}")

    def test_completion_script_sourceable(self) -> None:
        script = generate_zsh_completion()
        test_zsh = f"""
{script}
(( $+functions[_ziro] )) || exit 1
(( $+functions[_ziro_plugin] )) || exit 2
(( $+functions[__ziro_plugins] )) || exit 3
(( $+functions[__ziro_themes] )) || exit 4
(( $+functions[__ziro_prompts] )) || exit 5
(( $+functions[__ziro_suggests] )) || exit 6
(( $+functions[__ziro_tags] )) || exit 7
exit 0
"""
        run = subprocess.run(
            ["zsh", "-c", test_zsh],
            capture_output=True,
            text=True,
        )
        self.assertEqual(run.returncode, 0, f"Failed to source completion script: {run.stderr}")

    def test_completion_covers_positional_arguments(self) -> None:
        script = generate_zsh_completion()
        self.assertIn("1:theme:__ziro_themes", script)
        self.assertIn("1:plugin:__ziro_plugins", script)
        self.assertIn("1:engine:__ziro_prompts", script)
        self.assertIn("1:provider:__ziro_suggests", script)
        self.assertIn("1:file:__ziro_config_files", script)
        self.assertIn("1:key:__ziro_config_keys", script)

    def test_cmd_completion_rebuild(self) -> None:
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp_data:
            with mock.patch.dict("os.environ", {"ZIRO_DATA": tmp_data}):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = cmd_completion(["--rebuild"])
                self.assertEqual(rc, 0)
                out = buf.getvalue()
                self.assertIn("completion script updated", out)
                comp_file = Path(tmp_data) / "completions" / "_ziro"
                self.assertTrue(comp_file.is_file())

    def test_install_writes_completion_file(self) -> None:
        import tempfile
        from unittest import mock
        from core import install_cli

        with tempfile.TemporaryDirectory() as tmp_cfg, tempfile.TemporaryDirectory() as tmp_data:
            with mock.patch.dict("os.environ", {"ZIRO_CONFIG": tmp_cfg, "ZIRO_DATA": tmp_data}):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = install_cli.main(["--default"])
                self.assertEqual(rc, 0)
                comp_file = Path(tmp_data) / "completions" / "_ziro"
                self.assertTrue(comp_file.is_file(), f"Missing completion file at {comp_file}")
                content = comp_file.read_text(encoding="utf-8")
                self.assertTrue(content.startswith("#compdef ziro"))


if __name__ == "__main__":
    unittest.main()
