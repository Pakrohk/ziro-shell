"""Tests for declarative schema validation of core/tools_factory.toml."""

import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FACTORY_FILE = REPO_ROOT / "core" / "tools_factory.toml"


class TestToolsFactorySchema(unittest.TestCase):
    """Validate that core/tools_factory.toml satisfies the Spec 006 v0.2.0 schema."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.assertTrue(FACTORY_FILE.is_file(), f"Missing {FACTORY_FILE}")
        with FACTORY_FILE.open("rb") as f:
            cls.data = tomllib.load(f)
        cls.tools = cls.data.get("tool", [])

    def test_toml_parses_without_error(self) -> None:
        """Case 1: TOML parses cleanly and contains tool list."""
        self.assertIsInstance(self.data, dict)
        self.assertGreaterEqual(len(self.tools), 18)

    def test_all_tools_have_required_fields(self) -> None:
        """Case 2: Every tool entry has all 7 required fields."""
        required = ["name", "type", "category", "load_method", "load_timing", "load_order", "guard"]
        for t in self.tools:
            name = t.get("name", "UNKNOWN")
            for req in required:
                self.assertIn(req, t, f"Tool {name!r} missing required field {req!r}")

    def test_type_enum_valid(self) -> None:
        """Case 3: All tool types are within valid enum values."""
        valid_types = {"plugin", "binary", "builtin", "bootstrap"}
        for t in self.tools:
            self.assertIn(
                t["type"],
                valid_types,
                f"Tool {t['name']!r} has invalid type {t['type']!r}",
            )

    def test_category_enum_valid(self) -> None:
        """Case 4: All tool categories match recognized functional categories."""
        valid_categories = {
            "prompt",
            "auto_suggest",
            "syntax_highlighting",
            "completions",
            "colors",
            "navigation",
            "fuzzy_finder",
            "git",
            "core",
            "infra",
        }
        for t in self.tools:
            self.assertIn(
                t["category"],
                valid_categories,
                f"Tool {t['name']!r} has invalid category {t['category']!r}",
            )

    def test_load_method_enum_valid(self) -> None:
        """Case 5: All load_method values match defined emission patterns."""
        valid_methods = {
            "binary-eval",
            "clone-eval",
            "clone-source",
            "local-source",
            "builtin-load",
            "bootstrap-source",
        }
        for t in self.tools:
            self.assertIn(
                t["load_method"],
                valid_methods,
                f"Tool {t['name']!r} has invalid load_method {t['load_method']!r}",
            )

    def test_load_timing_enum_valid(self) -> None:
        """Case 6: All load_timing values match lifecycle stages."""
        valid_timings = {"eager", "defer", "eval", "prompt", "on-demand"}
        for t in self.tools:
            self.assertIn(
                t["load_timing"],
                valid_timings,
                f"Tool {t['name']!r} has invalid load_timing {t['load_timing']!r}",
            )

    def test_guard_enum_valid(self) -> None:
        """Case 7: All guard values are valid."""
        valid_guards = {"none", "binary-check"}
        for t in self.tools:
            self.assertIn(
                t["guard"],
                valid_guards,
                f"Tool {t['name']!r} has invalid guard {t['guard']!r}",
            )

    def test_no_duplicate_names(self) -> None:
        """Case 8: All tool names are globally unique."""
        names = [t["name"] for t in self.tools]
        duplicates = [n for n in set(names) if names.count(n) > 1]
        self.assertEqual(duplicates, [], f"Found duplicate tool names: {duplicates}")

    def test_load_order_unique_for_default_tools(self) -> None:
        """Case 9: Default active tools (order 1..10) have unique load_order values."""
        default_tools = [
            t for t in self.tools
            if not t.get("alternatives_only", False) and t.get("type") not in ("bootstrap",)
        ]
        orders = [t["load_order"] for t in default_tools]
        duplicate_orders = [o for o in set(orders) if orders.count(o) > 1]
        self.assertEqual(duplicate_orders, [], f"Duplicate load_orders: {duplicate_orders}")

    def test_conditional_fields_present_when_required(self) -> None:
        """Case 10: Conditional fields exist based on load_method and guard."""
        for t in self.tools:
            name = t["name"]
            method = t["load_method"]

            if method == "binary-eval":
                self.assertIn("init_command", t, f"Tool {name!r} needs 'init_command'")
                self.assertIn("cache_key", t, f"Tool {name!r} needs 'cache_key'")

            if method == "clone-eval":
                self.assertIn("eval_command", t, f"Tool {name!r} needs 'eval_command'")
                self.assertIn("cache_key", t, f"Tool {name!r} needs 'cache_key'")
                self.assertIn("source", t, f"Tool {name!r} needs 'source'")

            if method in ("clone-source", "bootstrap-source"):
                self.assertIn("source", t, f"Tool {name!r} needs 'source'")

            if method == "local-source":
                self.assertIn("local_path", t, f"Tool {name!r} needs 'local_path'")

            if t.get("guard") == "binary-check":
                self.assertIn("binary_name", t, f"Tool {name!r} with binary-check needs 'binary_name'")


if __name__ == "__main__":
    unittest.main()
