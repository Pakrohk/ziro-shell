"""Tests for ziro local source capability."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INTEGRATION_ZSH = REPO_ROOT / "integration.zsh"


class TestZiroLocalSource(unittest.TestCase):
    """Test the _ziro_local_source function via zsh subprocess."""

    def _run_zsh(self, script: str, timeout: int = 10) -> tuple[int, str, str]:
        """Run a zsh script and capture output."""
        full_script = f"""
            export ZIRO_HOME='{REPO_ROOT}'
            source '{INTEGRATION_ZSH}'
            {script}
        """
        result = subprocess.run(
            ['zsh', '-c', full_script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr

    def test_dir_with_plugin_zsh(self):
        """_ziro_local_source finds *.plugin.zsh in a directory."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin = Path(tmp) / 'my.plugin.zsh'
            plugin.write_text('export MY_PLUGIN_LOADED=1\n')
            script = f"""
                _ziro_local_source '{tmp}'
                echo "MY_PLUGIN_LOADED=$MY_PLUGIN_LOADED"
            """
            rc, out, err = self._run_zsh(script)
            self.assertEqual(rc, 0, f'stderr: {err}')
            self.assertIn('MY_PLUGIN_LOADED=1', out)

    def test_direct_file_path(self):
        """_ziro_local_source sources a direct file path."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin = Path(tmp) / 'direct.zsh'
            plugin.write_text('export DIRECT_LOADED=1\n')
            script = f"""
                _ziro_local_source '{plugin}'
                echo "DIRECT_LOADED=$DIRECT_LOADED"
            """
            rc, out, err = self._run_zsh(script)
            self.assertEqual(rc, 0, f'stderr: {err}')
            self.assertIn('DIRECT_LOADED=1', out)

    def test_missing_path_fails(self):
        """_ziro_local_source returns error for missing path."""
        script = """
            _ziro_local_source /nonexistent/path/xyz
            echo "rc=$?"
        """
        rc, out, err = self._run_zsh(script)
        self.assertIn('rc=1', out)
        self.assertIn('not found', err.lower())

    def test_zwc_created(self):
        """_ziro_local_source creates .zwc via znap compile."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin = Path(tmp) / 'compiled.plugin.zsh'
            plugin.write_text('export COMPILED=1\n')
            script = f"""
                _ziro_local_source '{plugin}'
                ls -la '{tmp}'/*.zwc 2>&1 | head -2
            """
            rc, out, err = self._run_zsh(script)
            self.assertIn('.zwc', out, f'No .zwc created. out={out} err={err}')

    def test_zwc_reused(self):
        """_ziro_local_source does not recompile if .zwc is fresh."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin = Path(tmp) / 'reuse.plugin.zsh'
            plugin.write_text('export REUSE=1\n')
            # First run — compile
            script1 = f"""
                _ziro_local_source '{plugin}'
            """
            self._run_zsh(script1)
            zwc = Path(f'{plugin}.zwc')
            mtime1 = zwc.stat().st_mtime
            # Second run — should not recompile
            import time
            time.sleep(1.1)
            self._run_zsh(script1)
            mtime2 = zwc.stat().st_mtime
            self.assertEqual(mtime1, mtime2, 'ZWC was recompiled unnecessarily')

    def test_zwc_invalidated(self):
        """_ziro_local_source recompiles if source is newer than .zwc."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin = Path(tmp) / 'invalidated.plugin.zsh'
            plugin.write_text('export V1=1\n')
            script = f"""
                _ziro_local_source '{plugin}'
            """
            self._run_zsh(script)
            zwc = Path(f'{plugin}.zwc')
            mtime1 = zwc.stat().st_mtime
            # Modify source
            import time
            time.sleep(1.1)
            plugin.write_text('export V2=2\n')
            self._run_zsh(script)
            mtime2 = zwc.stat().st_mtime
            self.assertGreater(mtime2, mtime1, 'ZWC was not recompiled after source change')

    def test_ziro_local_dispatcher(self):
        """ziro-local source <path> dispatches to _ziro_local_source."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin = Path(tmp) / 'dispatched.plugin.zsh'
            plugin.write_text('export DISPATCHED=1\n')
            script = f"""
                ziro-local source '{tmp}'
                echo "DISPATCHED=$DISPATCHED"
            """
            rc, out, err = self._run_zsh(script)
            self.assertEqual(rc, 0, f'stderr: {err}')
            self.assertIn('DISPATCHED=1', out)

    def test_deferred_mode(self):
        """_ziro_local_source --defer uses ziro-defer."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin = Path(tmp) / 'deferred.plugin.zsh'
            plugin.write_text('export DEFERRED=1\n')
            script = f"""
                _ziro_local_source '{plugin}' --defer
                sleep 0.5
                echo "DEFERRED=$DEFERRED"
            """
            rc, out, err = self._run_zsh(script)
            self.assertIn('DEFERRED=1', out, f'out={out} err={err}')


if __name__ == '__main__':
    unittest.main()
