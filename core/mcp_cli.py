"""ziro-shell — MCP command line interface.

Spec: 024 (R9, R15)
"""

from __future__ import annotations

import sys
from typing import Any

from core.constants import VERSION
from core.mcp_server import MCPServer
from core.mcp_tools.command import tool_cmd_check, tool_cmd_execute
from core.mcp_tools.directory import tool_dir_inspect, tool_dir_safe_to_delete, tool_dir_types
from core.mcp_tools.ghost import tool_ghost_health, tool_ghost_stats, tool_ghost_suggest
from core.mcp_tools.system import tool_system_binaries, tool_system_env, tool_system_info, tool_system_packages
from core.mcp_tools.ziro import tool_ziro_analyze, tool_ziro_doctor, tool_ziro_plugin_list, tool_ziro_stats


def register_all_tools(server: MCPServer) -> None:
    """Register all 16 AI-safe tools across 5 domain categories."""
    # 1. System tools (4)
    server.register_tool(
        "ziro.system.info",
        "Inspect host OS, architecture, kernel, Python, and Ziro versions.",
        {"type": "object", "properties": {}},
        tool_system_info,
    )
    server.register_tool(
        "ziro.system.packages",
        "List installed packages across system and user package managers (pip, uv, npm, cargo, brew, apt).",
        {"type": "object", "properties": {"all": {"type": "boolean", "description": "Scan all discovered package managers"}}},
        tool_system_packages,
    )
    server.register_tool(
        "ziro.system.binaries",
        "Inspect resolved paths and versions for core developer CLI tools.",
        {"type": "object", "properties": {"commands": {"type": "array", "items": {"type": "string"}}}},
        tool_system_binaries,
    )
    server.register_tool(
        "ziro.system.env",
        "Inspect whitelisted non-sensitive environment variables (secrets redacted).",
        {"type": "object", "properties": {}},
        tool_system_env,
    )

    # 2. Directory tools (3)
    server.register_tool(
        "ziro.dir.inspect",
        "Inspect directory semantics: git repo status, language distribution, build manifests, permissions.",
        {"type": "object", "properties": {"path": {"type": "string", "description": "Directory path to inspect"}}, "required": ["path"]},
        tool_dir_inspect,
    )
    server.register_tool(
        "ziro.dir.types",
        "Classify directory semantics: project_root, build_dir, cache_dir, config_dir, temp_dir.",
        {"type": "object", "properties": {"path": {"type": "string"}}},
        tool_dir_types,
    )
    server.register_tool(
        "ziro.dir.safe_to_delete",
        "Assess whether a target directory is safe for AI cleanup heuristics.",
        {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        tool_dir_safe_to_delete,
    )

    # 3. Command safety tools (2)
    server.register_tool(
        "ziro.cmd.check",
        "Evaluate risk rating (0-10), dangerous primitives, and safety category of a shell command string.",
        {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
        tool_cmd_check,
    )
    server.register_tool(
        "ziro.cmd.execute",
        "Execute a shell command with two-step token confirmation and audit logging (blocked in safe-mode).",
        {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "reason": {"type": "string", "description": "Explanation of why this command is being run"},
                "confirm_token": {"type": "string", "description": "60s ephemeral confirmation token received from prior call"},
            },
            "required": ["command", "reason"],
        },
        tool_cmd_execute,
    )

    # 4. Ghost companion tools (3)
    server.register_tool(
        "ghost.suggest",
        "Query autosuggestion candidates from Ghost v2.0.1 engine.",
        {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        tool_ghost_suggest,
    )
    server.register_tool(
        "ghost.health",
        "Check Ghost v2.0.1 diagnostic checks and readiness status.",
        {"type": "object", "properties": {}},
        tool_ghost_health,
    )
    server.register_tool(
        "ghost.stats",
        "Retrieve Ghost v2.0.1 aggregated latency and error telemetry.",
        {"type": "object", "properties": {}},
        tool_ghost_stats,
    )

    # 5. Native Ziro tools (4)
    server.register_tool(
        "ziro.analyze",
        "Report active shell tools and startup performance footprint.",
        {"type": "object", "properties": {}},
        tool_ziro_analyze,
    )
    server.register_tool(
        "ziro.doctor",
        "Run full Ziro system doctor diagnostics and return structured health results.",
        {"type": "object", "properties": {}},
        tool_ziro_doctor,
    )
    server.register_tool(
        "ziro.stats",
        "Retrieve aggregated metrics across external shell tools.",
        {"type": "object", "properties": {"tool": {"type": "string"}}},
        tool_ziro_stats,
    )
    server.register_tool(
        "ziro.plugin.list",
        "List all installed plugins and their repository paths.",
        {"type": "object", "properties": {}},
        tool_ziro_plugin_list,
    )


def cmd_mcp(argv: list[str]) -> int:
    """Run ziro mcp server."""
    allow_execute = "--allow-execute" in argv
    safe_mode = not allow_execute

    server = MCPServer(safe_mode=safe_mode, version=VERSION)
    register_all_tools(server)
    server.run()
    return 0


def main(argv: list[str] | None = None) -> int:
    return cmd_mcp(argv if argv is not None else sys.argv[1:])
