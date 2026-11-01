#!/usr/bin/env python3
"""Tests for core.async_helpers."""

import asyncio
import sys
import unittest
from pathlib import Path

# Add ~/.ziro to path
sys.path.insert(0, str(Path.home() / ".ziro"))

from core.async_helpers import (  # noqa: E402
    gather_bounded,
    with_timeout,
    DEFAULT_TIMEOUT_S,
)

import pytest
pytestmark = pytest.mark.unit


class TestGatherBounded(unittest.TestCase):
    def test_preserves_order(self):
        async def slow(n):
            await asyncio.sleep(0.01 * n)
            n_last = n  # keep the value referenced for clarity
            return n_last

        async def main():
            return await gather_bounded([slow(3), slow(1), slow(2)])

        result = asyncio.run(main())
        self.assertEqual(result, [3, 1, 2])

    def test_respects_concurrency(self):
        active = 0
        peak = 0

        async def job():
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1
            return True

        async def main():
            await gather_bounded([job() for _ in range(20)], concurrency=4)
            return peak

        peak = asyncio.run(main())
        self.assertLessEqual(peak, 4)


class TestWithTimeout(unittest.TestCase):
    def test_returns_on_time(self):
        async def fast():
            return 42

        result = asyncio.run(with_timeout(fast(), timeout_s=1.0))
        self.assertEqual(result, 42)

    def test_fallback_on_timeout(self):
        async def slow():
            await asyncio.sleep(10)
            return 1

        result = asyncio.run(
            with_timeout(slow(), timeout_s=0.05, on_timeout=lambda: -1)
        )
        self.assertEqual(result, -1)

    def test_raises_without_fallback(self):
        async def slow():
            await asyncio.sleep(10)

        with self.assertRaises(asyncio.TimeoutError):
            asyncio.run(with_timeout(slow(), timeout_s=0.05))


class TestConstants(unittest.TestCase):
    def test_defaults(self):
        self.assertGreater(DEFAULT_TIMEOUT_S, 0)


if __name__ == "__main__":
    unittest.main()
