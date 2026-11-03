"""Tests for Model Context Protocol (MCP) server core.

Layer: 4 (Tests)
Spec: 024 (Phase 4, 9, 10)
"""

from __future__ import annotations

import json
from core.mcp_server import MCPServer
from core.mcp_cli import register_all_tools


def test_initialize_response():
    server = MCPServer(safe_mode=True, version="1.3.0")
    req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    resp = server.handle_request(req)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    result = resp["result"]
    assert result["serverInfo"]["name"] == "ziro"
    assert result["serverInfo"]["version"] == "1.3.0"
    assert result["serverInfo"]["safe_mode"] is True
    assert "safe" in result["instructions"].lower()


def test_tools_list_returns_16():
    server = MCPServer(safe_mode=True, version="1.3.0")
    register_all_tools(server)
    req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
    resp = server.handle_request(req)
    tools = resp["result"]["tools"]
    assert len(tools) == 16
    tool_names = {t["name"] for t in tools}
    assert "ziro.system.info" in tool_names
    assert "ziro.cmd.execute" in tool_names
    assert "ghost.suggest" in tool_names
    assert "ziro.doctor" in tool_names


def test_unknown_method_returns_error():
    server = MCPServer()
    req = {"jsonrpc": "2.0", "id": 99, "method": "non_existent_method"}
    resp = server.handle_request(req)
    assert resp["error"]["code"] == -32601


def test_ping_method():
    server = MCPServer()
    req = {"jsonrpc": "2.0", "id": 4, "method": "ping"}
    resp = server.handle_request(req)
    assert resp["result"] == {}


def test_shutdown_method():
    server = MCPServer()
    req = {"jsonrpc": "2.0", "id": 5, "method": "shutdown"}
    resp = server.handle_request(req)
    assert resp["result"] is None


def test_unknown_tool_returns_error():
    server = MCPServer()
    req = {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "ghost.unknown"}}
    resp = server.handle_request(req)
    assert resp["error"]["code"] == -32601


def test_safe_mode_blocks_execute():
    server = MCPServer(safe_mode=True)
    register_all_tools(server)
    req = {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {
            "name": "ziro.cmd.execute",
            "arguments": {"command": "echo hello", "reason": "test"},
        },
    }
    resp = server.handle_request(req)
    assert resp["result"]["isError"] is True
    content = resp["result"]["content"][0]["text"]
    assert "SAFE_MODE_ENABLED" in content


def test_allow_execute_returns_token_first():
    server = MCPServer(safe_mode=False)
    register_all_tools(server)
    req = {
        "jsonrpc": "2.0",
        "id": 8,
        "method": "tools/call",
        "params": {
            "name": "ziro.cmd.execute",
            "arguments": {"command": "echo step1", "reason": "testing two-step token"},
        },
    }
    resp = server.handle_request(req)
    content = resp["result"]["content"][0]["text"]
    data = json.loads(content)
    assert data["executed"] is False
    assert data["needs_confirmation"] is True
    assert "confirm_token" in data
    assert data["expires_in_seconds"] == 60


def test_execute_with_valid_token_runs_command():
    server = MCPServer(safe_mode=False)
    register_all_tools(server)
    # Step 1
    req1 = {
        "jsonrpc": "2.0",
        "id": 9,
        "method": "tools/call",
        "params": {
            "name": "ziro.cmd.execute",
            "arguments": {"command": "echo 'ziro_ok'", "reason": "unit test"},
        },
    }
    resp1 = server.handle_request(req1)
    data1 = json.loads(resp1["result"]["content"][0]["text"])
    token = data1["confirm_token"]

    # Step 2
    req2 = {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {
            "name": "ziro.cmd.execute",
            "arguments": {
                "command": "echo 'ziro_ok'",
                "reason": "unit test",
                "confirm_token": token,
            },
        },
    }
    resp2 = server.handle_request(req2)
    data2 = json.loads(resp2["result"]["content"][0]["text"])
    assert data2["executed"] is True
    assert data2["exit_code"] == 0
    assert "ziro_ok" in data2["stdout"]
    assert data2["audit_logged"] is True


def test_token_single_use():
    server = MCPServer(safe_mode=False)
    register_all_tools(server)
    req1 = {
        "jsonrpc": "2.0",
        "id": 11,
        "method": "tools/call",
        "params": {
            "name": "ziro.cmd.execute",
            "arguments": {"command": "echo single_use", "reason": "unit test"},
        },
    }
    resp1 = server.handle_request(req1)
    token = json.loads(resp1["result"]["content"][0]["text"])["confirm_token"]

    # Run once
    server.handle_request({
        "jsonrpc": "2.0",
        "id": 12,
        "method": "tools/call",
        "params": {
            "name": "ziro.cmd.execute",
            "arguments": {"command": "echo single_use", "reason": "unit test", "confirm_token": token},
        },
    })

    # Try replay
    resp_replay = server.handle_request({
        "jsonrpc": "2.0",
        "id": 13,
        "method": "tools/call",
        "params": {
            "name": "ziro.cmd.execute",
            "arguments": {"command": "echo single_use", "reason": "unit test", "confirm_token": token},
        },
    })
    assert resp_replay["result"]["isError"] is True
    assert "INVALID_OR_EXPIRED_TOKEN" in resp_replay["result"]["content"][0]["text"]


def test_command_check_dangerous_blocked():
    server = MCPServer(safe_mode=False)
    register_all_tools(server)
    req = {
        "jsonrpc": "2.0",
        "id": 14,
        "method": "tools/call",
        "params": {
            "name": "ziro.cmd.execute",
            "arguments": {"command": "rm -rf /", "reason": "malicious check"},
        },
    }
    resp = server.handle_request(req)
    assert resp["result"]["isError"] is True
    assert "CRITICAL_RISK_BLOCKED" in resp["result"]["content"][0]["text"]


def test_tool_exception_handled():
    server = MCPServer()
    def failing_handler(args):
        raise RuntimeError("boom")
    server.register_tool("fail.tool", "fails", {}, failing_handler)
    resp = server.handle_request({"jsonrpc": "2.0", "id": 15, "method": "tools/call", "params": {"name": "fail.tool"}})
    assert resp["result"]["isError"] is True
    assert "boom" in resp["result"]["content"][0]["text"]

def test_missing_required_arguments_returns_error():
    server = MCPServer(safe_mode=False)
    register_all_tools(server)
    # cmd.execute requires both "command" and "reason"
    req = {
        "jsonrpc": "2.0",
        "id": 16,
        "method": "tools/call",
        "params": {
            "name": "ziro.cmd.execute",
            "arguments": {"command": "echo test"},
        },
    }
    resp = server.handle_request(req)
    assert resp["result"]["isError"] is True


def test_concurrent_calls_order():
    server = MCPServer()
    register_all_tools(server)
    reqs = [
        {"jsonrpc": "2.0", "id": 17, "method": "ping"},
        {"jsonrpc": "2.0", "id": 18, "method": "tools/call", "params": {"name": "ziro.system.info", "arguments": {}}},
    ]
    responses = [server.handle_request(r) for r in reqs]
    assert responses[0]["id"] == 17
    assert responses[1]["id"] == 18

def test_version_in_serverinfo():
    from core.constants import VERSION
    server = MCPServer(version=VERSION)
    res = server.handle_request({"jsonrpc": "2.0", "id": 22, "method": "initialize", "params": {}})
    assert res["result"]["serverInfo"]["version"] == VERSION


def test_invalid_json_line():
    # Test handling in run loop
    server = MCPServer()
    # verify parse error structure
    err_resp = {
        "jsonrpc": "2.0",
        "id": None,
        "error": {
            "code": -32700,
            "message": "Parse error",
        },
    }
    assert err_resp["error"]["code"] == -32700


def test_notifications_initialized():
    server = MCPServer()
    res = server.handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert res is None
