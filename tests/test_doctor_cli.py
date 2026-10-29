"""Tests for core.doctor_cli."""
import io, os, sys, tempfile, unittest
from contextlib import redirect_stdout
from pathlib import Path
sys.path.insert(0, str(Path.home() / ".ziro"))
from core import doctor_cli


class TestDoctorCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._cfg = os.environ.get("ZIRO_CONFIG")
        self._home = os.environ.get("ZIRO_HOME")
        os.environ["ZIRO_CONFIG"] = self.tmp.name
        os.environ["ZIRO_HOME"] = self.tmp.name

    def tearDown(self):
        for k, v in (("ZIRO_CONFIG", self._cfg), ("ZIRO_HOME", self._home)):
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)
        self.tmp.cleanup()

    def test_runs(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = doctor_cli.main([])
        self.assertIn(rc, (0, 1))
        self.assertIn("ziro doctor", buf.getvalue())

    def test_verbose(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            doctor_cli.main(["--verbose"])
        self.assertIn("Python", buf.getvalue())

    def test_check_runtime_commands_missing_boot(self):
        # boot.zsh does not exist in empty tmp
        status, msg, fix = doctor_cli._check_runtime_commands()
        self.assertEqual(status, "warn")
        self.assertIn("boot.zsh not found", msg)

    def test_check_runtime_commands_failure(self):
        from unittest.mock import patch, MagicMock
        cfg = Path(self.tmp.name)
        (cfg / "boot.zsh").write_text("# dummy\n")

        mock_res = MagicMock(returncode=1, stdout="missing: ll, mkcd", stderr="")
        with patch("subprocess.run", return_value=mock_res):
            status, msg, fix = doctor_cli._check_runtime_commands()
            self.assertEqual(status, "error")
            self.assertIn("missing: ll, mkcd", msg)

    def test_check_runtime_commands_success(self):
        from unittest.mock import patch, MagicMock
        cfg = Path(self.tmp.name)
        (cfg / "boot.zsh").write_text("# dummy\n")

        mock_res = MagicMock(returncode=0, stdout="ok", stderr="")
        with patch("subprocess.run", return_value=mock_res):
            status, msg, fix = doctor_cli._check_runtime_commands()
            self.assertEqual(status, "ok")
            self.assertIn("runtime commands and functions loaded", msg)


if __name__ == "__main__":
    unittest.main()
