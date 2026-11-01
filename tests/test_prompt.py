"""Tests for core.prompt."""
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path.home() / ".ziro"))
from core.prompt import (
    read_prompt_conf, write_prompt_conf, resolve_prompt,
    list_prompts, SUPPORTED_PROMPTS, DEFAULT_PROMPT,
)

import pytest
pytestmark = pytest.mark.unit


class TestPromptConf(unittest.TestCase):
    def test_missing_conf_returns_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(read_prompt_conf(Path(tmp)), DEFAULT_PROMPT)

    def test_write_and_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp)
            write_prompt_conf(cfg, "pure")
            self.assertEqual(read_prompt_conf(cfg), "pure")

    def test_unsupported_write_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                write_prompt_conf(Path(tmp), "vim")

    def test_unknown_conf_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp)
            (cfg / "prompt.conf").write_text("unknown-prompt\n")
            self.assertEqual(read_prompt_conf(cfg), DEFAULT_PROMPT)


class TestResolve(unittest.TestCase):
    def test_resolve_starship(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "cfg"
            prm = Path(tmp) / "prm"
            cfg.mkdir()
            prm.mkdir()
            write_prompt_conf(cfg, "starship")
            r = resolve_prompt(cfg, prm)
            self.assertEqual(r.name, "starship")
            self.assertTrue(r.theme_supported)

    def test_list_prompts(self):
        with tempfile.TemporaryDirectory() as tmp:
            prm = Path(tmp)
            (prm / "starship.zsh").write_text("# starship")
            (prm / "pure.zsh").write_text("# pure")
            names = list_prompts(prm)
            self.assertIn("starship", names)
            self.assertIn("pure", names)


if __name__ == "__main__":
    unittest.main()
