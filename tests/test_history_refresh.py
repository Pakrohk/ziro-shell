import unittest
from pathlib import Path
from core.generator import load_tools_registry


class TestHistoryRefresh(unittest.TestCase):
    def test_history_refresh_tool_registered(self) -> None:
        """Verify ziro-history-refresh is registered in tools_factory.toml."""
        tools = load_tools_registry()
        tool_names = [t["name"] for t in tools]
        self.assertIn("ziro-history-refresh", tool_names)

        tool = next(t for t in tools if t["name"] == "ziro-history-refresh")
        self.assertEqual(tool.get("load_timing"), "eager")
        self.assertEqual(tool.get("load_method"), "local-source")

    def test_history_refresh_script_exists(self) -> None:
        """Verify history-refresh.zsh exists and is non-empty."""
        repo_root = Path(__file__).resolve().parent.parent
        script = repo_root / "lib" / "history-refresh.zsh"
        self.assertTrue(script.is_file(), f"Missing {script}")
        content = script.read_text(encoding="utf-8")
        self.assertIn("_ziro_ghost_history_append", content)
        self.assertIn("_ziro_ghost_history_mtime_check", content)
        self.assertIn("add-zsh-hook precmd", content)


if __name__ == "__main__":
    unittest.main()
