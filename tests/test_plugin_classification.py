"""Tests for plugin vs external binary classification in generator and install.

Ensures:
- External binaries (starship, fzf, zoxide) use guarded evaluation: (( $+commands[...] )) && znap eval ...
- Plugins and self-contained repo evals (zcolors, fast-syntax-highlighting, zsh-completions) do NOT use external command guards.
- zcolors is evaluated via repo-scoped znap eval (znap eval marlonrichert/zcolors), not an external system binary.
"""

import os
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

from core import install_cli
from core.generator import generate_plugins_gen, default_output_path


class TestPluginClassification(unittest.TestCase):
    """Verify correct classification of external CLI tools vs Zsh plugins."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)
        self.config_dir = self.test_dir / "config"
        self.data_dir = self.test_dir / "data"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.old_cfg = os.environ.get("ZIRO_CONFIG")
        self.old_data = os.environ.get("ZIRO_DATA")
        self.old_home = os.environ.get("ZIRO_HOME")
        os.environ["ZIRO_CONFIG"] = str(self.config_dir)
        os.environ["ZIRO_DATA"] = str(self.data_dir)
        os.environ["ZIRO_HOME"] = str(REPO_ROOT)

    def tearDown(self) -> None:
        if self.old_cfg is not None:
            os.environ["ZIRO_CONFIG"] = self.old_cfg
        else:
            os.environ.pop("ZIRO_CONFIG", None)

        if self.old_data is not None:
            os.environ["ZIRO_DATA"] = self.old_data
        else:
            os.environ.pop("ZIRO_DATA", None)

        if self.old_home is not None:
            os.environ["ZIRO_HOME"] = self.old_home
        else:
            os.environ.pop("ZIRO_HOME", None)

        self.temp_dir.cleanup()

    def test_external_binaries_have_command_guards(self) -> None:
        """External binaries must have (( $+commands[...] )) guards."""
        gen_file = generate_plugins_gen(self.config_dir, ziro_home=REPO_ROOT)
        content = gen_file.read_text(encoding="utf-8")

        self.assertIn("(( $+commands[starship] )) && znap eval starship", content)
        self.assertIn("(( $+commands[fzf] ))", content)
        self.assertIn("(( $+commands[zoxide] ))", content)

    def test_zsh_plugins_do_not_have_command_guards(self) -> None:
        """Zsh plugins and self-contained repo tools must not be guarded by $+commands checks."""
        gen_file = generate_plugins_gen(self.config_dir, ziro_home=REPO_ROOT)
        content = gen_file.read_text(encoding="utf-8")

        self.assertNotIn("(( $+commands[zcolors] ))", content)
        self.assertNotIn("(( $+commands[fast-syntax-highlighting] ))", content)
        self.assertNotIn("(( $+commands[zsh-completions] ))", content)

    def test_zcolors_emitted_as_repo_eval(self) -> None:
        """zcolors must be emitted via repo-scoped znap eval, not a bare binary call."""
        gen_file = generate_plugins_gen(self.config_dir, ziro_home=REPO_ROOT)
        content = gen_file.read_text(encoding="utf-8")

        self.assertIn('znap eval marlonrichert/zcolors "./zcolors', content)
        self.assertNotIn('znap eval zcolors "zcolors', content)

    def test_fresh_install_contains_zcolors_repo_eval(self) -> None:
        """Fresh install emits plugins.gen.zsh with repo-scoped zcolors eval line."""
        rc = install_cli.main(["--default"])
        self.assertEqual(rc, 0)

        gen_file = default_output_path(self.config_dir)
        content = gen_file.read_text(encoding="utf-8")
        self.assertIn('znap eval marlonrichert/zcolors "./zcolors', content)


if __name__ == "__main__":
    unittest.main()
