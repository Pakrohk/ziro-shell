"""Command safety evaluation, gated execution, and audit logging.

Spec: 024 (R12, R15, R18, Q2)
"""

from __future__ import annotations

import json
import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from core.paths import _ensure_secure_perms, get_paths

AUDIT_LOG_FILE = Path.home() / ".cache" / "ziro" / "mcp" / "audit.jsonl"


def _log_audit(command: str, reason: str, blocked: bool, status: str, exit_code: int | None = None) -> None:
    """Record an audit trail event for command checking or execution."""
    AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _ensure_secure_perms(AUDIT_LOG_FILE.parent)

    record = {
        "ts": time.time(),
        "command": command,
        "reason": reason,
        "blocked": blocked,
        "status": status,
        "exit_code": exit_code,
    }

    try:
        with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        _ensure_secure_perms(AUDIT_LOG_FILE)
    except Exception:
        pass


def tool_cmd_check(args: dict[str, Any]) -> dict[str, Any]:
    """Evaluate risk score (0-10) and blocked status of arbitrary shell command strings."""
    cmd = args.get("command", "").strip()
    if not cmd:
        return {"error": "command string is required"}

    critical_patterns = [
        (r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f*|-rf|-fr)\s+(/\s*$|/\*|\.\s*$)", "Recursive root deletion"),
        (r"\bdd\s+if=.*of=/dev/(sd|hd|nvme|vd)", "Raw block device overwriting"),
        (r"\bmkfs(\.\w+)?\s+/dev/", "Filesystem formatting"),
        (r">\s*/dev/(sd|hd|nvme|vd)", "Direct device write redirection"),
        (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "Fork bomb primitive"),
        (r"\b(curl|wget)\b.*\|\s*(sh|bash|zsh|sudo)\b", "Unvetted remote script piping"),
        (r"\bchmod\s+(-[a-zA-Z]*\s+)?777\s+(/\s*$|/\*)", "Permissive permission clobbering"),
    ]

    reasons: list[str] = []
    risk_score = 0
    blocked = False

    for pat, desc in critical_patterns:
        if re.search(pat, cmd, re.IGNORECASE):
            risk_score = 10
            blocked = True
            reasons.append(desc)

    if not blocked:
        # Check warnings
        if re.search(r"\bsudo\b", cmd):
            risk_score = max(risk_score, 7)
            reasons.append("Command uses superuser escalation (sudo)")

        if re.search(r"\brm\s+(-[a-zA-Z]*r|-r)", cmd):
            risk_score = max(risk_score, 6)
            reasons.append("Recursive file deletion requested")

        if re.search(r"\b(reboot|poweroff|shutdown|init\s+0)\b", cmd):
            risk_score = max(risk_score, 8)
            reasons.append("System lifecycle termination command")

        # Safe known read-only commands
        first_token = cmd.split()[0] if cmd.split() else ""
        if first_token in ("ls", "cat", "grep", "rg", "head", "tail", "git", "python3", "pytest", "echo", "pwd", "which"):
            if risk_score == 0:
                risk_score = 1
                reasons.append(f"Standard development command: {first_token}")

    risk_class = (
        "critical"
        if risk_score >= 9
        else ("dangerous" if risk_score >= 6 else ("moderate" if risk_score >= 3 else "safe"))
    )

    return {
        "command": cmd,
        "risk_class": risk_class,
        "risk_score": risk_score,
        "blocked": blocked,
        "reasons": reasons if reasons else ["General shell command execution"],
        "preview": f"Executes: {cmd}",
    }


def tool_cmd_execute(args: dict[str, Any], server: Any = None) -> dict[str, Any]:
    """Execute command with two-step token confirmation and audit logging."""
    cmd = args.get("command", "").strip()
    reason = args.get("reason", "").strip()
    token = args.get("confirm_token", "").strip()

    if not cmd or not reason:
        return {"isError": True, "error": "Both 'command' and 'reason' arguments are required."}

    # 1. Safe-mode gating
    if server and server.safe_mode:
        _log_audit(cmd, reason, blocked=True, status="safe_mode_blocked")
        return {
            "isError": True,
            "error": "SAFE_MODE_ENABLED: Command execution is blocked by default. Restart ziro mcp with --allow-execute to unlock.",
        }

    # 2. Safety evaluation
    eval_res = tool_cmd_check({"command": cmd})
    if eval_res.get("blocked"):
        _log_audit(cmd, reason, blocked=True, status="critical_risk_blocked")
        return {
            "isError": True,
            "error": f"CRITICAL_RISK_BLOCKED: {eval_res.get('reasons')}",
            "check": eval_res,
        }

    # 3. Two-Step Confirmation Token Handling (Q2 answer: 60s TTL, single-use)
    if not token:
        # Step 1: Issue token
        issued_token = str(uuid.uuid4())
        expires_at = time.time() + 60.0
        if server:
            server.tokens[issued_token] = {"command": cmd, "expires": expires_at}

        return {
            "executed": False,
            "needs_confirmation": True,
            "confirm_token": issued_token,
            "expires_in_seconds": 60,
            "preview": eval_res,
            "message": "Step 1 complete. Review plan. To execute, call again with confirm_token within 60s.",
        }

    # Step 2: Validate token
    if not server or token not in server.tokens:
        return {
            "isError": True,
            "error": "INVALID_OR_EXPIRED_TOKEN: Confirm token not found or already consumed.",
        }

    token_info = server.tokens.pop(token)  # Single-use consumption
    if time.time() > token_info["expires"]:
        return {"isError": True, "error": "TOKEN_EXPIRED: 60-second execution window lapsed."}

    if token_info["command"] != cmd:
        return {"isError": True, "error": "TOKEN_MISMATCH: Command string was modified between steps."}

    # Execute
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        dur_ms = round((time.time() - t0) * 1000.0, 2)
        _log_audit(cmd, reason, blocked=False, status="executed", exit_code=proc.returncode)

        return {
            "executed": True,
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "duration_ms": dur_ms,
            "audit_logged": True,
        }
    except subprocess.TimeoutExpired:
        _log_audit(cmd, reason, blocked=False, status="timeout", exit_code=-1)
        return {"isError": True, "error": "Execution timed out after 30 seconds."}
    except Exception as e:
        _log_audit(cmd, reason, blocked=False, status="exception", exit_code=-1)
        return {"isError": True, "error": f"Execution error: {e}"}
