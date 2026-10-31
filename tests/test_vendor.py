"""Tests for core.vendor."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.vendor import get_vendor_repos, ensure_vendor_tools, _sync_single_vendor


class TestVendor(unittest.TestCase):
    def test_get_vendor_repos(self):
        manifest = {
            "tool": [
                {"name": "t1", "source": "user1/repo1"},
                {"name": "t2", "source": "user2/repo2"},
                {"name": "t3", "source": "${ZIRO_DATA}/local"},
                {"name": "t4"},
            ]
        }
        repos = get_vendor_repos(manifest)
        self.assertEqual(len(repos), 2)
        self.assertEqual(repos["user1/repo1"], "https://github.com/user1/repo1.git")
        self.assertEqual(repos["user2/repo2"], "https://github.com/user2/repo2.git")

    def test_ensure_vendor_skip_env(self):
        manifest = {"tool": [{"name": "t1", "source": "user1/repo1"}]}
        with patch.dict("os.environ", {"ZIRO_SKIP_VENDOR_CLONE": "1"}):
            cloned = ensure_vendor_tools(manifest, paths={"data": Path("/tmp")})
            self.assertEqual(cloned, [])

    def test_sync_single_vendor_existing_no_update(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "my_plugin"
            dest.mkdir()
            (dest / ".git").mkdir()
            src, ok, msg = _sync_single_vendor("test/plugin", "https://example.com/repo.git", dest, update_existing=False)
            self.assertTrue(ok)
            self.assertEqual(msg, "already present")

    def test_sync_single_vendor_corrupted_directory(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "corrupted_plugin"
            dest.mkdir()
            # Directory exists without .git - corrupted
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                src, ok, msg = _sync_single_vendor("test/corrupted", "https://example.com/repo.git", dest, update_existing=True)
                # It cleans and attempts to clone
                self.assertTrue(mock_run.called)

    def test_ensure_vendor_tools_update_flag(self):
        import tempfile
        manifest = {"tool": [{"name": "t1", "source": "user1/repo1"}]}
        with patch.dict("os.environ", {}, clear=False):
            os.environ.pop("ZIRO_SKIP_VENDOR_CLONE", None)
            with tempfile.TemporaryDirectory() as td:
                paths = {"data": Path(td)}
                dest = Path(td) / "vendor" / "user1" / "repo1"
                dest.mkdir(parents=True)
                (dest / ".git").mkdir()
                with patch("core.vendor._sync_single_vendor", return_value=("user1/repo1", True, "updated")) as mock_sync:
                    res = ensure_vendor_tools(manifest, paths=paths, update_existing=True)
                    self.assertEqual(res, ["user1/repo1"])
                    mock_sync.assert_called_once_with("user1/repo1", "https://github.com/user1/repo1.git", dest, True, False)


if __name__ == "__main__":
    unittest.main()
