"""Tests for v1.1.1 declarative registry tools, helpers, aliases, and defaults."""

import os
import tempfile
import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FACTORY_FILE = REPO_ROOT / "core" / "tools_factory.toml"

from core.generator import generate_plugins_gen, load_tools_registry, emit_pattern


class TestV111Tools(unittest.TestCase):
    """Test v1.1.1 tool additions and behavior in generator."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)
        self.config_dir = self.test_dir / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.old_cfg = os.environ.get("ZIRO_CONFIG")
        self.old_home = os.environ.get("ZIRO_HOME")
        os.environ["ZIRO_CONFIG"] = str(self.config_dir)
        os.environ["ZIRO_HOME"] = str(REPO_ROOT)

    def tearDown(self) -> None:
        if self.old_cfg is not None:
            os.environ["ZIRO_CONFIG"] = self.old_cfg
        else:
            os.environ.pop("ZIRO_CONFIG", None)

        if self.old_home is not None:
            os.environ["ZIRO_HOME"] = self.old_home
        else:
            os.environ.pop("ZIRO_HOME", None)

        self.temp_dir.cleanup()

    def test_tools_factory_count_snapshot(self) -> None:
        """Snapshot of tools_factory.toml tool count.

        History:
          v1.1.1: 23 tools (18 baseline + 5 from Phase 4-D)
          v1.2.0 consolidated fix: 27 tools
            +4 added: ziro-ssh-config, ohmyzsh-ssh-agent,
                      ziro-aliases-core, ziro-keybindings
          v1.2.0 history-fix: 28 tools (+1 ziro-history-refresh)
        """
        tools = load_tools_registry()
        self.assertEqual(
            len(tools), 28,
            "Tool count changed. If intentional, update this test "
            "AND document the delta in .specify/HANDOFF.md.",
        )

    def test_new_default_tools_present(self) -> None:
        """zsh-you-should-use and fzf-tab are registered as default active tools."""
        tools = {t["name"]: t for t in load_tools_registry()}
        self.assertIn("zsh-you-should-use", tools)
        self.assertFalse(tools["zsh-you-should-use"].get("alternatives_only", False))
        self.assertEqual(tools["zsh-you-should-use"]["load_order"], 11)
        self.assertEqual(tools["zsh-you-should-use"]["load_timing"], "defer")

        self.assertIn("fzf-tab", tools)
        self.assertFalse(tools["fzf-tab"].get("alternatives_only", False))
        self.assertEqual(tools["fzf-tab"]["load_order"], 12)
        self.assertEqual(tools["fzf-tab"]["load_timing"], "defer")

    def test_forgit_is_alternative(self) -> None:
        """forgit is registered as alternatives_only=True."""
        tools = {t["name"]: t for t in load_tools_registry()}
        self.assertIn("forgit", tools)
        self.assertTrue(tools["forgit"].get("alternatives_only", False))
        self.assertEqual(tools["forgit"]["load_order"], 13)

    def test_wd_is_alternative(self) -> None:
        """wd is registered as alternatives_only=True with zoxide as default navigation."""
        tools = {t["name"]: t for t in load_tools_registry()}
        self.assertIn("wd", tools)
        self.assertTrue(tools["wd"].get("alternatives_only", False))

    def test_helpers_and_aliases_emit_local_source(self) -> None:
        """ziro-helpers and ziro-aliases emit as deferred local-source."""
        tools = {t["name"]: t for t in load_tools_registry()}

        self.assertIn("ziro-helpers", tools)
        h_tool = tools["ziro-helpers"]
        self.assertEqual(h_tool["load_method"], "local-source")
        self.assertEqual(h_tool["load_timing"], "on-demand")

        self.assertIn("ziro-aliases", tools)
        a_tool = tools["ziro-aliases"]
        self.assertEqual(a_tool["load_method"], "local-source")
        self.assertEqual(a_tool["load_timing"], "defer")
        self.assertEqual(emit_pattern(a_tool), "ziro-defer source $ZIRO_HOME/lib/aliases.zsh")

    def test_regenerated_plugins_gen_contains_v1_1_1_tools(self) -> None:
        """Default generation includes zsh-you-should-use, fzf-tab, helpers, and aliases."""
        gen_path = generate_plugins_gen(self.config_dir, ziro_home=REPO_ROOT)
        content = gen_path.read_text(encoding="utf-8")

        self.assertIn("ziro-defer znap source MichaelAquilina/zsh-you-should-use", content)
        self.assertIn("ziro-defer znap source Aloxaf/fzf-tab", content)
        self.assertIn("_ziro_helpers_ensure", content)
        self.assertIn("ziro-defer source $ZIRO_HOME/lib/aliases.zsh", content)

        # forgit and wd must NOT be present by default
        self.assertNotIn("wfxr/forgit", content)
        self.assertNotIn("mfaerevaag/wd", content)

    def test_git_configurable_with_none_option(self) -> None:
        """Setting git.default = 'none' in defaults.toml omits git plugin."""
        defaults_file = self.config_dir / "defaults.toml"
        defaults_file.write_text(
            """
[git]
default = "none"
""",
            encoding="utf-8",
        )
        gen_path = generate_plugins_gen(self.config_dir, ziro_home=REPO_ROOT)
        content = gen_path.read_text(encoding="utf-8")
        self.assertNotIn("ohmyzsh/ohmyzsh plugins/git", content)
