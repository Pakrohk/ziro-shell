"""Tests for core.bench_cli."""
import io, sys, unittest
from contextlib import redirect_stdout
from pathlib import Path
sys.path.insert(0, str(Path.home() / ".ziro"))
from core import bench_cli

import pytest
pytestmark = pytest.mark.unit


class TestBenchCli(unittest.TestCase):
    def test_min_of(self):
        self.assertEqual(bench_cli._min_of([3.0, 1.5, 2.0]), 1.5)
        self.assertEqual(bench_cli._min_of([]), 0.0)

    def test_median_of(self):
        self.assertEqual(bench_cli._median_of([1.0, 2.0, 3.0]), 2.0)
        self.assertEqual(bench_cli._median_of([1.0, 2.0, 3.0, 4.0]), 2.5)

    def test_runs(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = bench_cli.main(["--iters", "3"])
        self.assertEqual(rc, 0)
        self.assertIn("ziro bench", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
