"""Critical acceptance test: verifying declarative architecture.

Proves that registering, configuring, and emitting a new tool is achievable
via TOML configuration alone, requiring zero Python code modifications.
"""

import os
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

from core.generator import generate_plugins_gen, default_output_path

import pytest
pytestmark = pytest.mark.unit


class TestDeclarativeAcceptance(unittest.TestCase):
    """Prove that adding tools requires zero Python code changes."""

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

    def test_add_new_plugin_tool_via_toml_only(self) -> None:
        """GIVEN a new tool declared in tools.toml and selected in defaults.toml

        WHEN generate_plugins_gen runs
        THEN the tool is emitted in plugins.gen.zsh with zero Python modifications.
        """
        # 1. User declares a new plugin in ~/.config/ziro/tools.toml
        user_tools_file = self.config_dir / "tools.toml"
        user_tools_file.write_text(
            """
[[tool]]
name = "my-custom-plugin"
type = "plugin"
category = "syntax_highlighting"
load_method = "clone-source"
load_timing = "defer"
load_order = 7
guard = "none"
source = "community/my-custom-plugin"
""",
            encoding="utf-8",
        )

        # 2. User selects this tool in defaults.toml
        defaults_file = self.config_dir / "defaults.toml"
        defaults_file.write_text(
            """
[syntax_highlighting]
default = "my-custom-plugin"
""",
            encoding="utf-8",
        )

        # 3. Generator runs
        gen_path = generate_plugins_gen(self.config_dir, ziro_home=REPO_ROOT)
        content = gen_path.read_text(encoding="utf-8")

        # 4. Verify emission
        self.assertIn("ziro-defer znap source community/my-custom-plugin", content)
        self.assertNotIn("fast-syntax-highlighting", content)

    def test_add_new_binary_tool_via_toml_only(self) -> None:
        """GIVEN a new binary tool declared in tools.toml and selected in defaults.toml

        WHEN generate_plugins_gen runs
        THEN the binary tool is emitted with guarded eval without Python changes.
        """
        user_tools_file = self.config_dir / "tools.toml"
        user_tools_file.write_text(
            """
[[tool]]
name = "skim"
type = "binary"
category = "fuzzy_finder"
load_method = "binary-eval"
load_timing = "eval"
load_order = 5
guard = "binary-check"
binary_name = "sk"
init_command = "sk --shell"
cache_key = "skim"
""",
            encoding="utf-8",
        )

        defaults_file = self.config_dir / "defaults.toml"
        defaults_file.write_text(
            """
[fuzzy_finder]
default = "skim"
""",
            encoding="utf-8",
        )

        gen_path = generate_plugins_gen(self.config_dir, ziro_home=REPO_ROOT)
        content = gen_path.read_text(encoding="utf-8")

        self.assertIn("(( $+commands[sk] )) && znap eval skim 'sk --shell'", content)
        self.assertNotIn("znap eval fzf", content)

    def test_alternatives_only_omitted_by_default(self) -> None:
        """Alternative tools are omitted unless selected."""
        gen_path = generate_plugins_gen(self.config_dir, ziro_home=REPO_ROOT)
        content = gen_path.read_text(encoding="utf-8")

        self.assertIn("starship", content)
        self.assertNotIn("powerlevel10k", content)
        self.assertNotIn("pure", content)


if __name__ == "__main__":
    unittest.main()
