# ==============================================================================
# ziro-shell — MCP Command (commands/mcp.zsh)
# Layer: 1 (Zsh CLI Interface) · Spec: 024 · Version: 1.3.0
# ==============================================================================

_ziro_cmd_mcp() {
  (cd "$ZIRO_HOME" && python3 -m core mcp "$@")
}
