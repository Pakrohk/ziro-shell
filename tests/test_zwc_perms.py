"""Tests for Spec 016 .zwc cache file permissions (N2).

Validates that compile_eager_artifacts and write_boot_shim enforce 0600 on
eval-cache files and 0700 on eval-cache directory.

Live integration test — requires real ~/.cache/ziro/eval-cache with compiled .zwc files.
Complement to tests/test_universal_chmod.py which is hermetic (mock-based).
This file guards against disk-level permission regressions that hermetic tests miss.
In CI (fresh checkout, no ~/.cache/ziro), the pytestmark skipif below skips all tests.
"""

from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path

import pytest

from core.doctor_cli import _check_eval_cache_perms, _check_ghost_cache_perms
from core.paths import get_paths

_LIVE_CACHE = Path(os.environ.get("ZIRO_CACHE", Path.home() / ".cache" / "ziro"))
_EVAL_CACHE = _LIVE_CACHE / "eval-cache"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
    not _EVAL_CACHE.exists() or not list(_EVAL_CACHE.glob("*.zwc")),
    reason="test_zwc_perms.py requires live ziro cache (run ziro sync first). "
    "Skipped in CI where no ziro install exists.",
),
]



class TestZwcPerms(unittest.TestCase):
    """Test suite for bytecode artifact permission hardening (spec 016 R5-R8)."""

    def test_zwc_file_600_and_dir_700(self) -> None:
        """AC4 & AC5: eval-cache directory is 700 and .zwc files are 600."""
        paths = get_paths()
        eval_cache = paths["cache"] / "eval-cache"
        self.assertTrue(eval_cache.is_dir())

        dir_mode = stat.S_IMODE(eval_cache.stat().st_mode)
        self.assertEqual(dir_mode, 0o700, f"eval-cache dir perms: {oct(dir_mode)}")

        zwc_files = list(eval_cache.glob("*.zwc"))
        self.assertGreater(len(zwc_files), 0, "Expected at least one .zwc file in eval-cache")
        for zwc in zwc_files:
            file_mode = stat.S_IMODE(zwc.stat().st_mode)
            self.assertEqual(file_mode, 0o600, f"{zwc.name} perms: {oct(file_mode)}")

    def test_ghost_cache_perms(self) -> None:
        """AC2 & AC3: ghost history cache is 600 and directory is 700."""
        cache_dir = Path.home() / ".cache" / "ziro" / "ghost"
        if cache_dir.exists():
            dir_mode = stat.S_IMODE(cache_dir.stat().st_mode)
            self.assertEqual(dir_mode, 0o700)
            cache_file = cache_dir / "history-cache"
            if cache_file.exists():
                file_mode = stat.S_IMODE(cache_file.stat().st_mode)
                self.assertEqual(file_mode, 0o600)

    def test_doctor_reports_cache_perms_ok(self) -> None:
        """AC13: Doctor check for eval-cache and ghost-cache reports ok."""
        status_eval, msg_eval, adv_eval = _check_eval_cache_perms()
        self.assertEqual(status_eval, "ok", f"doctor eval-cache perms: {msg_eval}")

        status_ghost, msg_ghost, adv_ghost = _check_ghost_cache_perms()
        self.assertEqual(status_ghost, "ok", f"doctor ghost cache perms: {msg_ghost}")


if __name__ == "__main__":
    unittest.main()
