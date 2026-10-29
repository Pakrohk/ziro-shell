"""Tests for core.vendor."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.vendor import get_vendor_repos, ensure_vendor_tools


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


if __name__ == "__main__":
    unittest.main()
