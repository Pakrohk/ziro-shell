"""End-to-end integration tests for ziro-shell."""
import io, os, sys, tempfile, unittest
from contextlib import redirect_stdout
from pathlib import Path
sys.path.insert(0, str(Path.home() / ".ziro"))


class TestEndToEnd(unittest.TestCase):
    """Integration: install → plugin add (dry-run) → tag → generate."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._cfg = os.environ.get("ZIRO_CONFIG")
        self._home = os.environ.get("ZIRO_HOME")
        self._cache = os.environ.get("ZIRO_CACHE")
        self._data = os.environ.get("ZIRO_DATA")
        self._allow_test_home = os.environ.get("ZIRO_ALLOW_TEST_HOME")
        os.environ["ZIRO_CONFIG"] = str(Path(self.tmp.name) / "cfg")
        os.environ["ZIRO_HOME"] = str(Path(self.tmp.name) / "home")
        os.environ["ZIRO_CACHE"] = str(Path(self.tmp.name) / "cache")
        os.environ["ZIRO_DATA"] = str(Path(self.tmp.name) / "data")
        os.environ["ZIRO_ALLOW_TEST_HOME"] = "1"
        Path(os.environ["ZIRO_CONFIG"]).mkdir(parents=True)
        Path(os.environ["ZIRO_HOME"]).mkdir(parents=True)
        Path(os.environ["ZIRO_CACHE"]).mkdir(parents=True)
        Path(os.environ["ZIRO_DATA"]).mkdir(parents=True)

    def tearDown(self):
        for k, v in (
            ("ZIRO_CONFIG", self._cfg),
            ("ZIRO_HOME", self._home),
            ("ZIRO_CACHE", self._cache),
            ("ZIRO_DATA", self._data),
            ("ZIRO_ALLOW_TEST_HOME", self._allow_test_home),
        ):
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)
        self.tmp.cleanup()

    def test_full_flow(self):
        from core import install_cli, plugin_cli, tag_cli, suggest_cli

        # 1. Install
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = install_cli.main(["--default"])
        self.assertEqual(rc, 0)

        # 2. Tag list (should run without error)
        buf = io.StringIO()
        with redirect_stdout(buf):
            tag_cli.main(["list"])

        # 3. Suggest set
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = suggest_cli.main(["set", "ziro-ghost"])
        self.assertEqual(rc, 0)

        # 4. Plugin add (dry-run)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = plugin_cli.main(["add", "fake/repo", "fake", "--dry-run"])
        self.assertEqual(rc, 0)

    def test_doctor_runs(self):
        from core import doctor_cli
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = doctor_cli.main([])
        self.assertIn(rc, (0, 1))


if __name__ == "__main__":
    unittest.main()
