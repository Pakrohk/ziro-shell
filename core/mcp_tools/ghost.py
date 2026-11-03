"""Ghost companion tools proxied to ghost-popup mcp.

Spec: 024 (R13)
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from core.paths import get_paths


def _find_ghost_bin() -> str | None:
    """Locate ghost-popup companion executable."""
    paths = get_paths()
    vendor_bin = paths["data"] / "vendor" / "Pakrohk" / "ziro-ghost" / "bin" / "ghost-popup"
    if vendor_bin.is_file() and subprocess.os.access(vendor_bin, subprocess.os.X_OK):
        return str(vendor_bin)

    local_bin = Path.home() / ".local" / "bin" / "ghost-popup"
    if local_bin.is_file() and subprocess.os.access(local_bin, subprocess.os.X_OK):
        return str(local_bin)

    which_bin = shutil.which("ghost-popup")
    if which_bin:
        return which_bin

    return None


def _proxy_call_ghost_mcp(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Send JSON-RPC request to ghost-popup mcp sub-daemon over stdio."""
    bin_path = _find_ghost_bin()
    if not bin_path:
        # Fallback to direct shell command execution if binary is absent
        if tool_name == "ghost.health":
            try:
                proc = subprocess.run(["zsh", "-ic", "ghost health --json"], capture_output=True, text=True, timeout=5)
                if proc.returncode == 0 and proc.stdout.strip():
                    return json.loads(proc.stdout.strip())
            except Exception:
                pass
        return {"error": "ghost-popup binary not found; run `ziro update`"}

    init_req = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    call_req = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": tool_name, "arguments": arguments}})
    payload = f"{init_req}\n{call_req}\n"

    try:
        proc = subprocess.run(
            [bin_path, "mcp"],
            input=payload,
            capture_output=True,
            text=True,
            timeout=5,
        )
        lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
        for ln in reversed(lines):
            try:
                data = json.loads(ln)
                if data.get("id") == 2:
                    res = data.get("result", {})
                    # Unwrap content text if formatted as MCP
                    if "content" in res and res["content"] and "text" in res["content"][0]:
                        try:
                            return json.loads(res["content"][0]["text"])
                        except Exception:
                            return {"raw": res["content"][0]["text"]}
                    return res
            except Exception:
                pass
        return {"raw": proc.stdout.strip()}
    except Exception as e:
        return {"error": f"Failed to communicate with ghost-popup mcp: {e}"}


def tool_ghost_suggest(args: dict[str, Any]) -> dict[str, Any]:
    return _proxy_call_ghost_mcp("ghost.suggest", args)


def tool_ghost_health(args: dict[str, Any]) -> dict[str, Any]:
    return _proxy_call_ghost_mcp("ghost.health", args)


def tool_ghost_stats(args: dict[str, Any]) -> dict[str, Any]:
    return _proxy_call_ghost_mcp("ghost.stats", args)
