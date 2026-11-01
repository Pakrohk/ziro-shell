"""Tests for declarative emission patterns in core.generator."""

import unittest

from core.generator import emit_pattern, wrap_timing

import pytest
pytestmark = pytest.mark.unit


class TestGeneratorEmission(unittest.TestCase):
    """Test emit_pattern across all load_method and guard combinations."""

    def test_binary_eval_with_guard(self) -> None:
        """Case 1: binary-eval with binary-check emits (( $+commands[...] )) guard."""
        tool = {
            "name": "starship",
            "load_method": "binary-eval",
            "guard": "binary-check",
            "binary_name": "starship",
            "cache_key": "starship",
            "init_command": "starship init zsh --print-full-init",
        }
        line = emit_pattern(tool)
        self.assertEqual(
            line,
            "(( $+commands[starship] )) && znap eval starship 'starship init zsh --print-full-init'",
        )

    def test_binary_eval_without_guard(self) -> None:
        """Case 2: binary-eval with guard='none' emits bare znap eval."""
        tool = {
            "name": "mybin",
            "load_method": "binary-eval",
            "guard": "none",
            "cache_key": "mybin",
            "init_command": "mybin init",
        }
        line = emit_pattern(tool)
        self.assertEqual(line, "znap eval mybin 'mybin init'")

    def test_clone_source_eager(self) -> None:
        """Case 3: clone-source with load_timing='eager' emits znap source."""
        tool = {
            "name": "zsh-completions",
            "load_method": "clone-source",
            "load_timing": "eager",
            "source": "zsh-users/zsh-completions",
        }
        line = emit_pattern(tool)
        self.assertEqual(line, "znap source zsh-users/zsh-completions")

    def test_clone_source_with_subpath(self) -> None:
        """Case 4: clone-source with subpath appends subpath."""
        tool = {
            "name": "ohmyzsh-git",
            "load_method": "clone-source",
            "load_timing": "eager",
            "source": "ohmyzsh/ohmyzsh",
            "subpath": "plugins/git",
        }
        line = emit_pattern(tool)
        self.assertEqual(line, "znap source ohmyzsh/ohmyzsh plugins/git")

    def test_clone_source_deferred(self) -> None:
        """Case 5: clone-source with load_timing='defer' emits ziro-defer znap source."""
        tool = {
            "name": "fast-syntax-highlighting",
            "load_method": "clone-source",
            "load_timing": "defer",
            "source": "zdharma-continuum/fast-syntax-highlighting",
        }
        line = emit_pattern(tool)
        self.assertEqual(
            line,
            "ziro-defer znap source zdharma-continuum/fast-syntax-highlighting",
        )

    def test_clone_eval(self) -> None:
        """Case 6: clone-eval emits znap eval with repo scope and eval_command."""
        tool = {
            "name": "zcolors",
            "load_method": "clone-eval",
            "source": "marlonrichert/zcolors",
            "eval_command": './zcolors ${(q)LS_COLORS}',
        }
        line = emit_pattern(tool)
        self.assertEqual(line, 'znap eval marlonrichert/zcolors "./zcolors ${(q)LS_COLORS}"')

    def test_local_source_deferred(self) -> None:
        """Case 7: local-source with load_timing='defer' emits ziro-defer source."""
        tool = {
            "name": "ziro-ghost",
            "load_method": "local-source",
            "load_timing": "defer",
            "local_path": "$ZIRO_HOME/ghost/ghost.zsh",
        }
        line = emit_pattern(tool)
        self.assertEqual(line, "ziro-defer source $ZIRO_HOME/ghost/ghost.zsh")

    def test_local_source_eager(self) -> None:
        """Case 8: local-source with load_timing='eager' emits source directly."""
        tool = {
            "name": "custom-local",
            "load_method": "local-source",
            "load_timing": "eager",
            "local_path": "$ZIRO_HOME/custom.zsh",
        }
        line = emit_pattern(tool)
        self.assertEqual(line, "source $ZIRO_HOME/custom.zsh")

    def test_builtin_load(self) -> None:
        """Case 9: builtin-load emits the bare tool name."""
        tool = {
            "name": "compinit",
            "load_method": "builtin-load",
            "load_timing": "eager",
        }
        line = emit_pattern(tool)
        self.assertEqual(line, "compinit")

    def test_bootstrap_source(self) -> None:
        """Case 10: bootstrap-source emits source to bootstrap script."""
        tool = {
            "name": "znap",
            "load_method": "bootstrap-source",
            "load_timing": "eager",
            "source": "$ZIRO_HOME/vendor/znap/znap.zsh",
        }
        line = emit_pattern(tool)
        self.assertEqual(line, "source $ZIRO_HOME/vendor/znap/znap.zsh")

    def test_unknown_load_method_raises(self) -> None:
        """Case 11: Unknown load_method raises ValueError."""
        tool = {
            "name": "bad-tool",
            "load_method": "magic-load",
        }
        with self.assertRaises(ValueError):
            emit_pattern(tool)

    def test_wrap_timing_utility(self) -> None:
        """Case 12: wrap_timing handles defer vs eager."""
        self.assertEqual(wrap_timing("test_cmd", "defer"), "ziro-defer test_cmd")
        self.assertEqual(wrap_timing("test_cmd", "eager"), "test_cmd")
        self.assertEqual(wrap_timing("test_cmd", "eval"), "test_cmd")


if __name__ == "__main__":
    unittest.main()
