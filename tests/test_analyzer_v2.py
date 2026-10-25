"""Tests for Defer v2 Analyzer, Resolver, and Manifest integration (Spec 001/003 v0.2.0)."""

import tempfile
import unittest
from pathlib import Path

from core.analyzer import (
    analyze_plugin,
    analyze_from_manifest,
    analyze_by_regex,
    slug,
)
from core.models import DetectedSignals, Strategy
from core.resolver import ResolvedConfig, validate_cross_stage


class TestAnalyzerV2(unittest.TestCase):
    def test_slug_deterministic(self):
        """Pakrohk/ziro-ghost → ziro_ghost."""
        s = slug("Pakrohk/ziro-ghost")
        self.assertEqual(s, "ziro_ghost")

    def test_slug_collision(self):
        """Two different sources with same base name → unique slugs."""
        existing = {"foo"}
        s2 = slug("other/foo", existing=existing)
        self.assertNotEqual(s2, "foo")
        self.assertTrue(s2.startswith("foo_"))

    def test_manifest_first(self):
        """Plugin with ziro-plugin.toml reads stage from manifest."""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            m = p / "ziro-plugin.toml"
            m.write_text(
                '[plugin]\nname = "my-test"\n\n'
                '[load]\nmain = "test.plugin.zsh"\n\n'
                '[[load.stages]]\nid = 1\nname = "boot"\nslot = "a"\n'
            )
            res = analyze_plugin(p, "my-test")
            self.assertEqual(res.recommended.stage, 1)
            self.assertEqual(res.recommended.slot, "a")
            self.assertEqual(res.confidence, 1.0)

    def test_manifest_absent(self):
        """Falls back to regex when manifest is absent."""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            f = p / "test.plugin.zsh"
            f.write_text("add-zsh-hook precmd my_hook\n")
            res = analyze_plugin(p, "test")
            self.assertEqual(res.recommended.stage, 5)
            self.assertEqual(res.recommended.slot, "b")

    def test_compdef_maps_to_stage2(self):
        """Plugin with compdef → stage=2, slot=a."""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            f = p / "comp.plugin.zsh"
            f.write_text("compdef _foo foo\n")
            res = analyze_plugin(p, "comp")
            self.assertEqual(res.recommended.stage, 2)
            self.assertEqual(res.recommended.slot, "a")

    def test_prompt_maps_to_stage4(self):
        """Prompt-related (PS1) → stage=4, slot=a."""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            f = p / "theme.plugin.zsh"
            f.write_text('PROMPT="%~ %# "\n')
            res = analyze_plugin(p, "theme")
            self.assertEqual(res.recommended.stage, 4)
            self.assertEqual(res.recommended.slot, "a")

    def test_zle_key_maps_to_stage7(self):
        """Plugin with bindkey '<key>' → stage=7, on_key=<key>."""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            f = p / "widget.plugin.zsh"
            f.write_text("bindkey '^R' history-incremental-search-backward\n")
            res = analyze_plugin(p, "widget")
            self.assertEqual(res.recommended.stage, 7)
            self.assertEqual(res.recommended.on_key, "^R")

    def test_hook_maps_to_stage5(self):
        """add-zsh-hook precmd → stage=5, slot=b."""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            f = p / "hook.plugin.zsh"
            f.write_text("add-zsh-hook precmd my_precmd\n")
            res = analyze_plugin(p, "hook")
            self.assertEqual(res.recommended.stage, 5)
            self.assertEqual(res.recommended.slot, "b")

    def test_large_no_hook_maps_to_stage6(self):
        """File > 100 lines and no hook → stage=6, slot=d, compiled_zwc."""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            f = p / "large.plugin.zsh"
            f.write_text("echo test\n" * 120)
            res = analyze_plugin(p, "large")
            self.assertEqual(res.recommended.stage, 6)
            self.assertEqual(res.recommended.slot, "d")
            self.assertEqual(res.recommended.cache_type, "compiled_zwc")

    def test_comment_stripped(self):
        """Regular comments are stripped and not detected as code signals."""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            f = p / "comment.plugin.zsh"
            f.write_text("# regular comment line\necho 'plain'\n")
            res = analyze_plugin(p, "comment")
            self.assertFalse(res.detected.compdef)
            self.assertNotEqual(res.recommended.stage, 2)

    def test_magic_comments_preserved(self):
        """Magic comments like #compdef are preserved by _strip_comments."""
        from core.analyzer import _strip_comments

        content = "#compdef foo\n# regular comment\necho hi\n"
        stripped = _strip_comments(content)
        self.assertIn("#compdef foo", stripped)
        self.assertIn("echo hi", stripped)
        self.assertNotIn("regular comment", stripped)

    def test_completion_files_scanned(self):
        """_read_source_files scans src/_* completion definition files."""
        from core.analyzer import _read_source_files

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            src_dir = p / "src"
            src_dir.mkdir()
            comp_file = src_dir / "_git"
            comp_file.write_text("#compdef git\n")
            plugin_file = p / "plugin.zsh"
            plugin_file.write_text("echo loaded\n")

            files = list(_read_source_files(p))
            self.assertGreaterEqual(len(files), 2)
            self.assertTrue(any(f.name == "_git" for f in files))

            res = analyze_plugin(p, "test-comp")
            self.assertEqual(res.recommended.stage, 2)
            self.assertEqual(res.recommended.slot, "a")

    def test_hook_wins_over_bindkey(self):
        """Plugin with both hooks and bindkey assigns to stage 5 (hook wins over on-demand)."""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            f = p / "hook_and_bind.plugin.zsh"
            f.write_text("add-zsh-hook precmd my_precmd\nbindkey '^I' my_widget\n")
            res = analyze_plugin(p, "hook-bind")
            self.assertEqual(res.recommended.stage, 5)
            self.assertEqual(res.recommended.slot, "b")
            self.assertIsNone(res.recommended.on_key)

    def test_bindkey_alone_widget(self):
        """Plugin with only bindkey (non-hot-swap) and no hooks assigns to stage 7 on-demand."""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            f = p / "widget.plugin.zsh"
            f.write_text("bindkey '^F' find-file-widget\n")
            res = analyze_plugin(p, "find-file")
            self.assertEqual(res.recommended.stage, 7)
            self.assertEqual(res.recommended.slot, "b")
            self.assertEqual(res.recommended.on_key, "^F")

    def test_tab_bindkey_hot_swap(self):
        """Plugin with bindkey '^I' (Tab) assigns to stage 5 slot b (hot-swap, not on-demand)."""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            f = p / "fzf_tab.plugin.zsh"
            f.write_text("bindkey '^I' fzf-tab-complete\n")
            res = analyze_plugin(p, "fzf-tab")
            self.assertEqual(res.recommended.stage, 5)
            self.assertEqual(res.recommended.slot, "b")
            self.assertIsNone(res.recommended.on_key)

    def test_other_bindkey_on_demand(self):
        """Plugin with non-Tab bindkey (e.g. '^G') assigns to stage 7 on-demand."""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            f = p / "custom_widget.plugin.zsh"
            f.write_text("bindkey '^G' my-special-widget\n")
            res = analyze_plugin(p, "custom-widget")
            self.assertEqual(res.recommended.stage, 7)
            self.assertEqual(res.recommended.slot, "b")
            self.assertEqual(res.recommended.on_key, "^G")

    def test_fsh_hook_over_aux_compdef(self):
        """Plugin with hook and auxiliary compdef (like fast-syntax-highlighting) assigns to stage 5."""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            main_f = p / "fsh.plugin.zsh"
            main_f.write_text("add-zsh-hook preexec _fsh_preexec\n")
            comp_f = p / "_fast-theme"
            comp_f.write_text("#compdef fast-theme\n")
            res = analyze_plugin(p, "fsh")
            self.assertEqual(res.recommended.stage, 5)
            self.assertEqual(res.recommended.slot, "b")

    def test_sh_file_scanned(self):
        """Plugin with .sh file and hook (like rupa/z) is scanned and maps to stage 5 slot b."""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            sh_f = p / "z.sh"
            sh_f.write_text("precmd_functions+=(_z_precmd)\n")
            res = analyze_plugin(p, "z")
            self.assertEqual(res.recommended.stage, 5)
            self.assertEqual(res.recommended.slot, "b")

    def test_no_extension_file_scanned(self):
        """Plugin with executable no-extension file (like zcolors) is scanned and detected."""
        import os
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            script_f = p / "mytool"
            script_f.write_text("#!/bin/zsh\nadd-zsh-hook precmd _mytool_precmd\n")
            script_f.chmod(0o755)
            res = analyze_plugin(p, "mytool")
            self.assertEqual(res.recommended.stage, 5)
            self.assertEqual(res.recommended.slot, "b")

    def test_indented_bindkey_detected(self):
        """Indented bindkey with -M keymap flags is properly extracted."""
        from core.analyzer import _extract_bindkey

        content = "  bindkey -M emacs '^I' fzf-tab-complete\n  bindkey '^R' other\n"
        key = _extract_bindkey(content)
        self.assertEqual(key, "^I")

    def test_fpath_add_triggers_stage_2(self):
        """Plugin with only fpath+= triggers completion classification (stage=2, slot=a)."""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            f = p / "zsh-completions.plugin.zsh"
            f.write_text('fpath+=("${0:A:h}/src")\n')
            res = analyze_plugin(p, "zsh-completions")
            self.assertEqual(res.recommended.stage, 2)
            self.assertEqual(res.recommended.slot, "a")

    def test_cross_stage_validation(self):
        """If A depends on B and stage(A) < stage(B), A is elevated to stage(B)."""
        cfg_a = ResolvedConfig(
            plugin="plugin-a",
            strategy=Strategy.EAGER,
            stage=4,
            slot="a",
            name="plugin_a",
            depends=("plugin_b",),
        )
        cfg_b = ResolvedConfig(
            plugin="plugin-b",
            strategy=Strategy.AFTER_PROMPT,
            stage=5,
            slot="b",
            name="plugin_b",
        )
        validated = validate_cross_stage([cfg_a, cfg_b])
        res_a = next(c for c in validated if c.name == "plugin_a")
        self.assertEqual(res_a.stage, 5)

    def test_depends_from_manifest(self):
        """Plugin with [[load.stages]] depends → populated in AnalysisResult."""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            m = p / "ziro-plugin.toml"
            m.write_text(
                '[plugin]\nname = "dep-test"\n\n'
                '[load]\nmain = "dep.zsh"\n\n'
                '[[load.stages]]\nid = 5\nname = "dep_test"\nslot = "b"\n'
                'depends = ["ghost", "zcolors"]\n'
            )
            res = analyze_plugin(p, "dep-test")
            self.assertEqual(res.recommended.depends, ("ghost", "zcolors"))


if __name__ == "__main__":
    unittest.main()
