"""Integration and unit tests for CLI module isolation and discipline.

Layer: 0 (CLI Modular Discipline)
Spec: 008 R1, R2, R3, R4
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import unittest
from pathlib import Path

import pytest
pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestModuleIsolation(unittest.TestCase):
    def test_dispatcher_line_count_under_30(self) -> None:
        """Spec 008 R1: Dispatcher ziro.zsh must have < 30 code lines."""
        dispatcher_path = REPO_ROOT / "ziro.zsh"
        self.assertTrue(dispatcher_path.is_file(), "ziro.zsh missing")

        lines = dispatcher_path.read_text(encoding="utf-8").splitlines()
        code_lines = [
            ln for ln in lines
            if ln.strip() and not ln.strip().startswith("#")
        ]

        self.assertLess(
            len(code_lines),
            30,
            f"ziro.zsh code lines ({len(code_lines)}) must be < 30",
        )
        self.assertLessEqual(
            len(lines),
            30,
            f"ziro.zsh total lines ({len(lines)}) must be <= 30",
        )

    def test_commands_syntax_and_isolated_sourcing(self) -> None:
        """Spec 008 R2: Each commands/*.zsh must source cleanly in isolation."""
        commands_dir = REPO_ROOT / "commands"
        cmd_files = sorted(commands_dir.glob("*.zsh"))
        self.assertGreaterEqual(len(cmd_files), 10, "Expected at least 10 command files")

        for cmd_file in cmd_files:
            with self.subTest(file=cmd_file.name):
                # 1. zsh -n syntax check
                syntax_run = subprocess.run(
                    ["zsh", "-n", str(cmd_file)],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(
                    syntax_run.returncode,
                    0,
                    f"Syntax error in {cmd_file.name}: {syntax_run.stderr}",
                )

                # 2. Isolated source execution
                source_run = subprocess.run(
                    ["zsh", "-c", f'source "{cmd_file}"'],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(
                    source_run.returncode,
                    0,
                    f"Failed to source {cmd_file.name}: {source_run.stderr}",
                )

    def test_commands_export_single_cmd_function(self) -> None:
        """Spec 008 R2: Each commands/*.zsh exports exactly one function _ziro_cmd_<name>."""
        commands_dir = REPO_ROOT / "commands"
        cmd_files = sorted(commands_dir.glob("*.zsh"))

        for cmd_file in cmd_files:
            mod_name = cmd_file.stem
            expected_fn = f"_ziro_cmd_{mod_name}"

            script = f"""
typeset -U before_funcs
before_funcs=(${{(k)functions}})
source "{cmd_file}"
typeset -U after_funcs
after_funcs=(${{(k)functions}})

for f in "${{after_funcs[@]}}"; do
  if [[ -z "${{before_funcs[(r)$f]}}" ]]; then
    print "$f"
  fi
done
"""
            run = subprocess.run(
                ["zsh", "-c", script],
                capture_output=True,
                text=True,
            )
            self.assertEqual(run.returncode, 0, f"Error checking functions in {cmd_file.name}")
            new_funcs = [fn.strip() for fn in run.stdout.strip().splitlines() if fn.strip()]

            self.assertEqual(
                new_funcs,
                [expected_fn],
                f"{cmd_file.name} must export exactly ['{expected_fn}'], got {new_funcs}",
            )

    def test_no_blanket_sourcing_in_commands(self) -> None:
        """Spec 008 R3: Command modules must not blanket source other modules or libraries."""
        commands_dir = REPO_ROOT / "commands"
        cmd_files = sorted(commands_dir.glob("*.zsh"))

        for cmd_file in cmd_files:
            content = cmd_file.read_text(encoding="utf-8")
            for line_no, line in enumerate(content.splitlines(), start=1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                # Reject blanket sourcing lines like 'source ...' or '. ...'
                if stripped.startswith("source ") or stripped.startswith(". "):
                    self.fail(
                        f"{cmd_file.name}:{line_no} contains sourcing: '{stripped}'. "
                        "Commands must not blanket source modules."
                    )

    def test_lib_idempotency_double_sourcing(self) -> None:
        """Spec 008 R3: lib/*.zsh must be idempotent (safe to source multiple times)."""
        lib_dir = REPO_ROOT / "lib"
        lib_files = sorted(lib_dir.glob("*.zsh"))
        self.assertGreaterEqual(len(lib_files), 5, "Expected at least 5 lib files")

        for lib_file in lib_files:
            with self.subTest(file=lib_file.name):
                # Test sourcing twice in same shell session
                script = f"""
source "{lib_file}"
rc1=$?
source "{lib_file}"
rc2=$?
if (( rc1 != 0 || rc2 != 0 )); then
  exit 1
fi
"""
                run = subprocess.run(
                    ["zsh", "-c", script],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(
                    run.returncode,
                    0,
                    f"Double-sourcing failed for {lib_file.name}: {run.stderr}",
                )

        # Test cache preservation across double source in env, platform, terminal, log
        cache_script = f"""
source "{lib_dir}/env.zsh"
_ZIRO_ENV_TYPE_CACHE="custom_cached_env"
source "{lib_dir}/env.zsh"
[[ "$_ZIRO_ENV_TYPE_CACHE" == "custom_cached_env" ]] || exit 2

source "{lib_dir}/platform.zsh"
_ZIRO_PLATFORM_CACHE="custom_cached_platform"
source "{lib_dir}/platform.zsh"
[[ "$_ZIRO_PLATFORM_CACHE" == "custom_cached_platform" ]] || exit 3

source "{lib_dir}/terminal.zsh"
_ZIRO_NERD_FONT_CACHE="custom_cached_font"
_ZIRO_TRUECOLOR_CACHE="custom_cached_tc"
source "{lib_dir}/terminal.zsh"
[[ "$_ZIRO_NERD_FONT_CACHE" == "custom_cached_font" ]] || exit 4
[[ "$_ZIRO_TRUECOLOR_CACHE" == "custom_cached_tc" ]] || exit 5

source "{lib_dir}/log.zsh"
_ZIRO_LOG_LEVEL="custom_cached_level"
source "{lib_dir}/log.zsh"
[[ "$_ZIRO_LOG_LEVEL" == "custom_cached_level" ]] || exit 6
"""
        cache_run = subprocess.run(
            ["zsh", "-c", cache_script],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            cache_run.returncode,
            0,
            f"Cache preservation failed during re-source (exit {cache_run.returncode})",
        )

    def test_core_main_lazy_imports(self) -> None:
        """Spec 008 R4: core/__main__.py must use lazy imports for CLI submodules."""
        main_py = REPO_ROOT / "core" / "__main__.py"
        tree = ast.parse(main_py.read_text(encoding="utf-8"))

        submodules_to_be_lazy = {
            "help_cli",
            "theme_cli",
            "prompt_cli",
            "install_cli",
            "plugin_cli",
            "tag_cli",
            "config_cli",
            "suggest_cli",
            "doctor_cli",
            "bench_cli",
            "completion_cli",
            "update_cli",
        }

        # Check that top-level module statements do not import CLI submodules
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for sub in submodules_to_be_lazy:
                        self.assertNotIn(
                            sub,
                            alias.name,
                            f"Top-level import '{alias.name}' violates lazy import rule",
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for sub in submodules_to_be_lazy:
                        self.assertNotIn(
                            sub,
                            node.module,
                            f"Top-level from '{node.module}' violates lazy import rule",
                        )
                for alias in node.names:
                    self.assertNotIn(
                        alias.name,
                        submodules_to_be_lazy,
                        f"Top-level imported symbol '{alias.name}' violates lazy import rule",
                    )

    def test_ziro_no_args_bench_sub_5ms(self) -> None:
        """Spec 008 SC-1: ziro (no args) dispatcher load + static help execution must be < 5ms."""
        bench_script = f"""
zmodload zsh/datetime
for i in {{1..11}}; do
  t1=$EPOCHREALTIME
  source "{REPO_ROOT}/ziro.zsh"
  ziro >/dev/null
  t2=$EPOCHREALTIME
  echo "$(( (t2 - t1) * 1000 ))"
done
"""
        run = subprocess.run(
            ["zsh", "-c", bench_script],
            capture_output=True,
            text=True,
        )
        self.assertEqual(run.returncode, 0, f"Benchmark script failed: {run.stderr}")
        samples = [float(x.strip()) for x in run.stdout.strip().splitlines() if x.strip()]
        self.assertEqual(len(samples), 11, "Expected 11 benchmark samples")
        min_sample = min(samples)
        self.assertLess(
            min_sample,
            5.0,
            f"ziro (no args) min time {min_sample:.2f}ms exceeds 5.0ms target",
        )


if __name__ == "__main__":
    unittest.main()
