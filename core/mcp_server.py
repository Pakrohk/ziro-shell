"""ziro-shell — Model Context Protocol (MCP) Server.

Layer: 3 (Python core)
Spec: 024 (Part 2: AI-safe system management layer)
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Callable


class MCPServer:
    """JSON-RPC 2.0 stdio server providing AI-safe system management tools."""

    def __init__(self, safe_mode: bool = True, version: str = "1.3.0"):
        self.safe_mode = safe_mode
        self.version = version
        self.tools: dict[str, dict[str, Any]] = {}
        self.tokens: dict[str, dict[str, Any]] = {}  # token -> {"command": str, "expires": float}

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Callable[..., Any],
    ) -> None:
        """Register an MCP tool definition and handler."""
        self.tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
            "handler": handler,
        }

    def handle_request(self, req: dict[str, Any]) -> dict[str, Any] | None:
        """Process a single JSON-RPC 2.0 request dictionary."""
        req_id = req.get("id")
        method = req.get("method")

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": True}
                    },
                    "serverInfo": {
                        "name": "ziro",
                        "version": self.version,
                        "safe_mode": self.safe_mode,
                    },
                    "instructions": (
                        "ziro-shell AI-safe system management layer. "
                        "Read-only query and inspection tools are safe to execute without limits. "
                        "Mutating execution is gated by safe-mode (disabled by default) and requires "
                        "a two-step time-limited confirmation token. Always dry-run first."
                    ),
                },
            }

        if method == "notifications/initialized":
            return None

        if method == "ping":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {},
            }

        if method == "tools/list":
            tool_list = [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "inputSchema": t["inputSchema"],
                }
                for t in self.tools.values()
            ]
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": tool_list},
            }

        if method == "tools/call":
            params = req.get("params") or {}
            tool_name = params.get("name")
            arguments = params.get("arguments") or {}

            if tool_name not in self.tools:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: '{tool_name}'",
                    },
                }

            tool_def = self.tools[tool_name]
            handler = tool_def["handler"]

            try:
                # Pass server context if requested
                import inspect
                sig = inspect.signature(handler)
                if "server" in sig.parameters:
                    res = handler(arguments, server=self)
                else:
                    res = handler(arguments)

                # Format as MCP content array if not already
                if isinstance(res, dict) and "content" in res:
                    formatted_content = res["content"]
                    is_err = res.get("isError", False)
                else:
                    is_err = isinstance(res, dict) and res.get("isError", False)
                    text_out = json.dumps(res, indent=2) if not isinstance(res, str) else res
                    formatted_content = [{"type": "text", "text": text_out}]

                resp: dict[str, Any] = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": formatted_content,
                    },
                }
                if is_err:
                    resp["result"]["isError"] = True
                return resp
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "isError": True,
                        "content": [{"type": "text", "text": f"Tool execution failed: {e}"}],
                    },
                }

        if method == "shutdown":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": None,
            }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: '{method}'",
            },
        }

    def run(self) -> None:
        """Run stdio event loop processing JSON-RPC lines."""
        if self.safe_mode:
            print("ziro mcp: safe-mode ON (read-only default). Use --allow-execute to unlock command execution.", file=sys.stderr)
        else:
            print("ziro mcp: warning: --allow-execute enabled. Command execution unlocked via two-step token.", file=sys.stderr)

        for line in sys.stdin:
            trimmed = line.strip()
            if not trimmed:
                continue

            try:
                req = json.loads(trimmed)
            except Exception as e:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {e}",
                    },
                }
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()
                continue

            resp = self.handle_request(req)
            if resp is not None:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()

            if req.get("method") == "shutdown":
                break
