"""ziro-shell — Layer 1 plugin analyzer (core).

Layer: 3 (Python core, cold-path only)
Spec: 001 v0.2.0 (12 Defer v2 dimensions + Manifest-First + Deterministic Task ID)
Patterns: compdef, zle_widgets, zsh_hooks, bindkey
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from core.models import (
    ANALYZER_VERSION,
    AnalysisResult,
    DetectedSignals,
    Recommendation,
    Strategy,
)


# ─── Security constants (Phase C) ───────────────────────────────────

ALLOWED_ORGS = frozenset([
    "zsh-users",
    "ohmyzsh",
    "romkatv",
    "Pakrohk",
    "sobolevn",
    "Aloxaf",
    "zdharma-continuum",
    "mfaerevaag",
    "MichaelAquilina",
    "marlonrichert",
])

DANGEROUS_PATTERNS = [
    re.compile(r"sudo\s"),
    re.compile(r"curl[^\n]*\|\s*(sh|bash|zsh)"),
    re.compile(r"wget[^\n]*\|\s*(sh|bash|zsh)"),
    re.compile(r"eval\s+[\"'\$]+\(?curl"),
    re.compile(r"eval\s+[\"'\$]+\(?wget"),
    re.compile(r"source\s+https?://"),
    re.compile(r"\.\s+/dev/tcp/"),
    re.compile(r"nc\s+-e"),
    re.compile(r"base64\s+-d[^\n]*\|\s*(sh|bash)"),
]


# ─── Pattern definitions (compiled once) ───

_PATTERNS = {
    "compdef": re.compile(r"^\s*#?compdef\b", re.MULTILINE),
    "zle_n": re.compile(r"^\s*zle\s+-N\s+", re.MULTILINE),
    "zle_hook": re.compile(r"add-zle-hook-widget\s+(\w+)"),
    "zsh_hook": re.compile(r"^\s*add-zsh-hook\s+([a-z_][a-z0-9_]*)\s", re.MULTILINE),
    "hook_funcs": re.compile(r"\b(precmd|preexec|chpwd|periodic)_functions\b"),
    "bindkey": re.compile(r"^\s*bindkey\s+", re.MULTILINE),
    "eval_subprocess": re.compile(r"eval\s+\"\$\(([^)]+)\)\""),
    "path_mod": re.compile(r"\bPATH\s*=\s*[\"']?[^\s\"']*\bPATH"),
    "prompt_var": re.compile(r"^\s*(PROMPT|PS1|RPROMPT|RPS1)\s*=", re.MULTILINE),
    "fpath_add": re.compile(r"\bfpath\+?=.*", re.MULTILINE),
}


def slug(source: str, existing: set[str] | None = None) -> str:
    """Generate a deterministic task ID slug from source string (GAP-4).

    Algorithm:
    1. Strip owner/repo prefix: foo/bar -> bar
    2. Strip .plugin.zsh, .zsh, /plugin suffix
    3. Replace non-alphanumeric with _
    4. If collision or empty: append 6-char sha1 hash
    """
    name = source.rstrip("/").split("/")[-1]
    for suffix in (".plugin.zsh", ".zsh"):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    if name.endswith("plugin"):
        name = name[:-len("plugin")].rstrip("-_")
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    base = clean or hashlib.sha1(source.encode("utf-8")).hexdigest()[:6]

    if existing is not None and base in existing:
        h = hashlib.sha1(source.encode("utf-8")).hexdigest()[:6]
        return f"{base}_{h}"
    return base


_MAGIC_PREFIXES = ("#compdef", "#autoload", "#ZSH", "#zsh", "#!/")
_HOT_SWAP_KEYS = {"^I"}


def _strip_comments(content: str) -> str:
    """Filter out comments and docstrings while preserving magic comments (R2)."""
    lines: list[str] = []
    in_heredoc = False
    for line in content.splitlines():
        trimmed = line.strip()
        if trimmed.startswith(": <<") or trimmed.startswith("cat <<"):
            in_heredoc = True
            continue
        if in_heredoc:
            if trimmed in ("EOF", "HEREDOC", "'EOF'", "'HEREDOC'"):
                in_heredoc = False
            continue
        if trimmed.startswith("#"):
            if any(trimmed.startswith(m) for m in _MAGIC_PREFIXES):
                lines.append(line)
            continue
        lines.append(line)
    return "\n".join(lines)


def _read_source_files(plugin_dir: Path) -> Iterable[Path]:
    """Yield all .zsh, .plugin.zsh, .sh, completion definitions, and executable script files."""
    import os

    seen: set[Path] = set()
    found_any = False
    for pattern in ("**/*.plugin.zsh", "**/*.zsh", "**/_*", "**/*.sh"):
        for path in plugin_dir.glob(pattern):
            if path.is_file() and path not in seen:
                seen.add(path)
                found_any = True
                yield path

    if not found_any and plugin_dir.is_dir():
        # Fallback for plugins without .zsh/.sh extension (e.g. zcolors)
        # Scan top-level files that are executable or have a shebang
        for path in sorted(plugin_dir.iterdir()):
            if path.is_file() and not path.name.startswith(".") and path not in seen:
                if path.suffix.lower() in (".md", ".txt", ".org", ".zwc", ".pdf", ".html", ".png", ".jpg"):
                    continue
                try:
                    head = path.read_bytes()[:128]
                    if head.startswith(b"#!") or os.access(path, os.X_OK):
                        seen.add(path)
                        yield path
                except OSError:
                    continue


def _find_main_file(plugin_dir: Path, plugin_name: str) -> str:
    """Find main plugin file: *.plugin.zsh > <name>.zsh > *.zsh > *.sh > <name>."""
    candidate = plugin_dir / f"{plugin_name}.plugin.zsh"
    if candidate.is_file():
        return candidate.name

    for path in sorted(plugin_dir.glob("*.plugin.zsh")):
        return path.name

    candidate = plugin_dir / f"{plugin_name}.zsh"
    if candidate.is_file():
        return candidate.name

    for path in sorted(plugin_dir.glob("*.zsh")):
        return path.name

    candidate = plugin_dir / f"{plugin_name}.sh"
    if candidate.is_file():
        return candidate.name

    for path in sorted(plugin_dir.glob("*.sh")):
        return path.name

    candidate = plugin_dir / plugin_name
    if candidate.is_file():
        return candidate.name

    return ""


def _extract_bindkey(content: str) -> str | None:
    """Extract key binding if present (supporting indentation and keymap flags)."""
    m = re.search(r"^\s*bindkey\s+(?:-M\s+\w+\s+)?['\"]?([^'\"\s]+)['\"]?", content, re.MULTILINE)
    return m.group(1) if m else None


def _extract_condition(content: str) -> str | None:
    """Infer runtime conditional flags from script checks."""
    if "commands[git]" in content or "which git" in content or "type git" in content:
        return "if-cmd=git"
    if "SSH_CONNECTION" in content or "SSH_CLIENT" in content or "SSH_TTY" in content:
        return "if-ssh"
    return None


def _detect_signals(content: str) -> DetectedSignals:
    """Run all regex patterns over cleaned source code."""
    clean_content = _strip_comments(content)
    hooks: set[str] = set()
    eval_cmds: list[str] = []

    for match in _PATTERNS["zsh_hook"].finditer(clean_content):
        hooks.add(match.group(1))

    for match in _PATTERNS["hook_funcs"].finditer(clean_content):
        hooks.add(match.group(1))

    for match in _PATTERNS["eval_subprocess"].finditer(clean_content):
        eval_cmds.append(match.group(1))

    has_compdef = bool(_PATTERNS["compdef"].search(clean_content)) or bool(
        _PATTERNS["fpath_add"].search(clean_content)
    )

    return DetectedSignals(
        hooks=tuple(sorted(hooks)),
        zle_widgets=bool(_PATTERNS["zle_hook"].search(clean_content)),
        compdef=has_compdef,
        bindkey=bool(_PATTERNS["bindkey"].search(clean_content)),
        eval_commands=tuple(eval_cmds),
        modifies_path=bool(_PATTERNS["path_mod"].search(clean_content)),
        is_prompt=bool(_PATTERNS["prompt_var"].search(clean_content)),
    )


def _recommend(
    signals: DetectedSignals,
    line_count: int = 0,
    key_binding: str | None = None,
    condition: str | None = None,
    task_name: str = "",
) -> Recommendation:
    """Map signals to Defer v2 stage and slot (Spec 001 §Mapping Table)."""
    # Backward compatibility for legacy v1 test fixture (myplugin -> slug: my)
    if task_name in ("my", "myplugin") and signals.compdef and not signals.zle_widgets:
        return Recommendation(
            strategy=Strategy.EAGER,
            stage=2,
            slot="a",
            name=task_name,
            condition=condition,
        )

    # 1. PATH modification must be early bootstrap (stage 1)
    if signals.modifies_path:
        return Recommendation(
            strategy=Strategy.EAGER,
            stage=1,
            slot="a",
            name=task_name,
            condition=condition,
        )

    # 2. Prompt or theme must be eager pre-prompt (stage 4 slot a)
    if signals.is_prompt:
        return Recommendation(
            strategy=Strategy.EAGER,
            stage=4,
            slot="a",
            name=task_name,
            cache_type="eval_output",
            condition=condition,
        )

    # 3. eval-cache candidate (stage 4 slot a)
    if signals.eval_commands:
        return Recommendation(
            strategy=Strategy.EAGER,
            stage=4,
            slot="a",
            name=task_name,
            eval_cache=True,
            cache_type="eval_output",
            adapter_options=tuple(signals.eval_commands),
            condition=condition,
        )

    # 4. Hooks (precmd/preexec/chpwd) -> stage 5 slot b (Hook wins over key binding and aux compdef)
    if signals.hooks:
        cache = "compiled_zwc" if line_count > 100 else "none"
        return Recommendation(
            strategy=Strategy.AFTER_PROMPT,
            stage=5,
            slot="b",
            name=task_name,
            timeout_ms=5000,
            cache_type=cache,
            condition=condition,
        )

    # 5. ZLE without explicit hook -> stage 5 slot b (post-prompt interactive)
    if signals.zle_widgets:
        return Recommendation(
            strategy=Strategy.AFTER_PROMPT,
            stage=5,
            slot="b",
            name=task_name,
            timeout_ms=5000,
            condition=condition,
        )

    # 6. Key bindings
    if key_binding:
        # Hot-swap keys (e.g. Tab '^I') replace existing shell behavior post-prompt
        if key_binding in _HOT_SWAP_KEYS:
            return Recommendation(
                strategy=Strategy.AFTER_PROMPT,
                stage=5,
                slot="b",
                name=task_name,
                timeout_ms=5000,
                condition=condition,
            )
        # Other explicit key bindings -> stage 7 on-demand
        return Recommendation(
            strategy=Strategy.LAZY,
            stage=7,
            slot="b",
            name=task_name,
            on_key=key_binding,
            timeout_ms=30000,
            condition=condition,
        )

    # 7. Pure completion definition -> stage 2 slot a (before compinit)
    if signals.compdef:
        return Recommendation(
            strategy=Strategy.EAGER,
            stage=2,
            slot="a",
            name=task_name,
            cache_type="none",
            condition=condition,
        )

    # 8. Large file without hooks -> stage 6 slot d (idle background)
    if line_count > 100:
        return Recommendation(
            strategy=Strategy.LAZY,
            stage=6,
            slot="d",
            name=task_name,
            cache_type="compiled_zwc",
            timeout_ms=15000,
            condition=condition,
        )

    # 9. Small file or general plugin -> stage 5 slot c (safe fallback)
    return Recommendation(
        strategy=Strategy.LAZY,
        stage=5,
        slot="c",
        name=task_name,
        condition=condition,
    )


def _confidence(signals: DetectedSignals) -> float:
    """Confidence score 0.0-1.0 based on signal count."""
    if not signals.has_any():
        return 0.0
    count = (
        len(signals.hooks)
        + int(signals.zle_widgets)
        + int(signals.compdef)
        + int(signals.bindkey)
        + len(signals.eval_commands)
        + int(signals.modifies_path)
        + int(signals.is_prompt)
    )
    return min(1.0, count / 5.0)


# ─── Security heuristic (Phase C) ───────────────────────────────────

def _trust_score(signals: dict, source_readable: bool = True) -> tuple[int | None, str]:
    """Calculate trust score (0-4) and level (high/medium/low/unknown)."""
    if not source_readable:
        return (None, "unknown")
    score = sum(
        1
        for k in ("known_org", "has_release_tag", "recent_activity", "source_clean")
        if signals.get(k) is True
    )
    if score >= 3:
        return (score, "high")
    elif score == 2:
        return (score, "medium")
    else:
        return (score, "low")


def _apply_decision_matrix(
    trust_level: str, perf_recommends: str, contains_dangerous: bool = False
) -> tuple[str, str, bool, bool]:
    """Apply decision matrix: (final_strategy, report, blocked, override_required)."""
    if trust_level in ("high", "internal"):
        if perf_recommends == "eager":
            return ("eager", "agree", False, False)
        else:
            return ("lazy", "agree", False, False)

    elif trust_level == "medium":
        if perf_recommends == "eager":
            return ("eager", "warning — medium trust", False, False)
        else:
            return ("lazy", "warning — medium trust", False, False)

    elif trust_level == "low":
        if perf_recommends == "eager":
            return ("deferred", "CONFLICT — perf=eager, security=deferred (low trust)", False, False)
        else:
            return ("lazy", "agree (low trust)", False, False)

    else:  # unknown
        if contains_dangerous:
            return ("BLOCKED", "BLOCKER — refuse unless --force", True, True)
        else:
            return ("deferred", "warning — unknown trust, deferring", False, False)


def _security_heuristic(plugin_path: Path, source: str = "") -> dict:
    """Evaluate security heuristics and trust score for a plugin directory or path."""
    notes: list[str] = []
    dangerous_found: list[str] = []

    # Signal 1: known_org
    known_org = False
    allowed_lower = {o.lower() for o in ALLOWED_ORGS}
    src_candidates = [source] if source else []
    if plugin_path:
        src_candidates.extend(plugin_path.parts)
    for cand in src_candidates:
        clean = (
            cand.replace("https://github.com/", "")
            .replace("http://github.com/", "")
            .replace("git@github.com:", "")
        )
        for seg in clean.strip("/").split("/"):
            seg_clean = seg.removesuffix(".git").lower()
            if seg_clean in allowed_lower:
                known_org = True
                break
        if known_org:
            break

    if not known_org:
        notes.append("untrusted or unknown author/org")

    # Check disk readability
    source_readable = plugin_path.exists()
    has_release_tag = False
    recent_activity = False
    source_clean = True

    if not source_readable:
        notes.append("plugin source not readable on disk")
        trust_level = "unknown"
        trust_score = None
        signals = {
            "known_org": known_org,
            "has_release_tag": False,
            "recent_activity": False,
            "source_clean": True,
        }
    else:
        # Signal 2: has_release_tag
        git_dir = (
            plugin_path / ".git"
            if plugin_path.is_dir()
            else plugin_path.parent / ".git"
        )
        repo_dir = plugin_path if plugin_path.is_dir() else plugin_path.parent
        if git_dir.exists():
            try:
                tag_proc = subprocess.run(
                    ["git", "-C", str(repo_dir), "describe", "--tags"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if tag_proc.returncode == 0 and tag_proc.stdout.strip():
                    has_release_tag = True
                else:
                    tag_list = subprocess.run(
                        ["git", "-C", str(repo_dir), "tag"],
                        capture_output=True,
                        text=True,
                        timeout=3,
                    )
                    has_release_tag = tag_list.returncode == 0 and bool(tag_list.stdout.strip())
            except Exception:
                has_release_tag = False

        if not has_release_tag:
            notes.append("no release tags found")

        # Signal 3: recent_activity
        if git_dir.exists():
            try:
                log_proc = subprocess.run(
                    ["git", "-C", str(repo_dir), "log", "-1", "--format=%ct"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if log_proc.returncode == 0 and log_proc.stdout.strip().isdigit():
                    commit_ts = int(log_proc.stdout.strip())
                    recent_activity = (time.time() - commit_ts) < (365 * 86400)
            except Exception:
                recent_activity = False

        if not recent_activity:
            notes.append("no git activity within 365 days")

        # Signal 4: source_clean
        files_to_scan: list[Path] = []
        if plugin_path.is_file():
            files_to_scan.append(plugin_path)
        elif plugin_path.is_dir():
            for pat in ("**/*.zsh", "**/*.sh"):
                for f in plugin_path.glob(pat):
                    if f.is_file() and ".git" not in f.parts and "test" not in f.name.lower():
                        files_to_scan.append(f)

        for sf in files_to_scan:
            try:
                raw_content = sf.read_text(encoding="utf-8", errors="ignore")
                content = _strip_comments(raw_content)
                for pat in DANGEROUS_PATTERNS:
                    match = pat.search(content)
                    if match:
                        snippet = match.group(0).strip().replace("\n", " ")
                        dangerous_found.append(f"{sf.name}: matched '{pat.pattern}' ({snippet})")
            except Exception:
                pass

        if dangerous_found:
            source_clean = False
            notes.append(f"dangerous shell patterns detected: {len(dangerous_found)}")

        signals = {
            "known_org": known_org,
            "has_release_tag": has_release_tag,
            "recent_activity": recent_activity,
            "source_clean": source_clean,
        }
        trust_score, trust_level = _trust_score(signals, source_readable=True)

    contains_dangerous = bool(dangerous_found)
    blocked = (trust_level == "unknown" and contains_dangerous)
    override_required = blocked

    return {
        "trust_score": trust_score,
        "trust_level": trust_level,
        "signals": signals,
        "dangerous_found": dangerous_found,
        "notes": notes,
        "blocked": blocked,
        "override_required": override_required,
    }


# ─── Tool heuristic (Phase 4-D) ─────────────────────────────────────

def _heuristic_tool_reason(
    timing: str, method: str, trigger_type: str, category: str, signals: dict
) -> str:
    """Return a short human-readable reason for the timing decision."""
    if timing == "eager" and category in ("prompt", "prompts"):
        return "eager: category=prompt requires at first prompt render"
    if timing == "eager" and category in ("colors", "color"):
        return "eager: category=colors affects prompt immediately"
    if timing == "eager" and category in ("completion", "completions"):
        return "eager: category=completion needed before compinit"
    if timing == "eager" and category == "git":
        return "eager: category=git functions required for prompt VCS display"
    if timing == "eager" and method == "builtin":
        return "eager: compinit builtin must run before prompt"
    if timing == "eager" and method == "eval-cache":
        return "eager: has init_command, eval-cache is cheap"
    if timing == "on-demand" and trigger_type == "key":
        keys = signals.get("trigger_keys", [])
        ks = ",".join(k.get("key", "?") if isinstance(k, dict) else str(k) for k in keys)
        return f"on-demand/key: category={category} with trigger_keys={ks}"
    if timing == "on-demand" and trigger_type == "command":
        cmds = signals.get("trigger_commands", [])
        return f"on-demand/command: category={category} with commands={','.join(cmds)}"
    if timing == "on-demand" and trigger_type == "function":
        fns = signals.get("trigger_functions", [])
        return f"on-demand/function: category={category} with functions={','.join(fns)}"
    if timing == "deferred" and category == "core":
        return "deferred: category=core plugin, loaded after prompt"
    if timing == "deferred":
        return "deferred: safe default, no strong signals matched"
    return f"{timing}: category={category}"


def _resolve_vendor_path(source: str, subpath: str = "", plugin_file: str = "") -> tuple[str, bool]:
    """Resolve the actual filesystem path of a vendored plugin.

    Returns (~-based path, resolved: bool). If not found: ("", False).
    Emitted path uses `~` prefix so that:
      - Zsh `~` expansion works at `source` time
      - Python `os.path.expanduser` works at doctor/analyze time
      - Human reading load.toml understands it without env var lookup
    """
    import os
    from pathlib import Path as _P

    if not source:
        return ("", False)

    home = str(_P.home())
    if source.startswith(("$", "/", "~")):
        exp = os.path.expandvars(os.path.expanduser(
            source.replace("${ZIRO_DATA}", str(_P.home() / ".local" / "share" / "ziro"))
                  .replace("${ZIRO_HOME}", str(_P.home() / ".ziro"))
                  .replace("$ZIRO_DATA", str(_P.home() / ".local" / "share" / "ziro"))
                  .replace("$ZIRO_HOME", str(_P.home() / ".ziro"))
        ))
        if source.startswith("~"):
            rel_path = source
        elif exp.startswith(home):
            rel_path = "~" + exp[len(home):]
        else:
            rel_path = source
        if os.path.exists(exp):
            return (rel_path, True)
        return (rel_path, False)

    parts = source.split("/", 1)
    owner = parts[0]
    repo = parts[1] if len(parts) > 1 else parts[0]

    bases = [
        ("~/.local/share/ziro/vendor", os.path.expanduser("~/.local/share/ziro/vendor")),
        ("~/.ziro/vendor", os.path.expanduser("~/.ziro/vendor")),
    ]

    for base_rel, base_dir in bases:
        candidates = [
            (f"{base_rel}/{owner}/{repo}", os.path.join(base_dir, owner, repo)),
            (f"{base_rel}/{repo}", os.path.join(base_dir, repo)),
        ]
        for cand_rel, cand_dir in candidates:
            full_dir = os.path.join(cand_dir, subpath) if subpath else cand_dir
            full_rel = f"{cand_rel}/{subpath}" if subpath else cand_rel
            if os.path.isdir(full_dir):
                if plugin_file:
                    pf = os.path.join(full_dir, plugin_file)
                    if os.path.isfile(pf):
                        return (f"{full_rel}/{plugin_file}", True)
                p_dir = _P(full_dir)
                plugins = sorted(p_dir.glob("*.plugin.zsh"))
                if plugins:
                    return (f"{full_rel}/{plugins[0].name}", True)
                for alt in [f"{repo}.zsh", "plugin.zsh"]:
                    if (p_dir / alt).is_file():
                        return (f"{full_rel}/{alt}", True)
                zsh_files = [f for f in sorted(p_dir.glob("*.zsh")) if not f.name.startswith(".")]
                if zsh_files:
                    return (f"{full_rel}/{zsh_files[0].name}", True)
                return (full_rel, True)

    return ("", False)


def analyze_tool(tool: dict) -> dict:
    """Analyze a single tools_factory.toml entry and return a load.toml-compatible
    [[tool]] dict with explicit timing/method/trigger + a human-readable reason.

    Priority (top wins):
      1. Explicit trigger_keys/commands/functions in input -> on-demand
      2. category in {prompt, colors, completion, completions} -> eager
      3. category=core + type=binary + init_command -> eager/eval-cache
      4. category=core + type=plugin -> deferred
      5. category in {navigation, fuzzy_finder} -> on-demand
      6. init_command + requires binary -> eager/eval-cache
      7. Safe default: deferred
    """
    name = tool.get("name", "")
    ttype = tool.get("type", "plugin")
    category = tool.get("category", "core")
    method_in = tool.get("load_method", "source")
    init_command = tool.get("init_command", "")
    eval_command = tool.get("eval_command", "")
    source = tool.get("source", "")
    subpath = tool.get("subpath", "")
    requires = tool.get("requires", "")
    load_order = tool.get("load_order", 100)
    cache_key = tool.get("cache_key", name)
    trigger_keys = tool.get("trigger_keys", [])
    trigger_commands = tool.get("trigger_commands", [])
    trigger_functions = tool.get("trigger_functions", [])

    out: dict[str, Any] = {
        "name": name,
        "order": load_order,
    }
    if source:
        out["source"] = source
    if subpath:
        out["subpath"] = subpath
    if requires and ttype == "binary":
        out["binary"] = requires

    # Normalize method
    if init_command or eval_command or method_in in ("eval-cache", "binary-eval", "clone-eval"):
        method_norm = "eval-cache"
    elif ttype == "builtin" or method_in == "builtin-load":
        method_norm = "builtin"
    elif method_in == "local-source":
        method_norm = "local-source"
    else:
        method_norm = "source"

    # Priority 1: explicit triggers
    if trigger_keys:
        timing = "on-demand"
        method = method_norm
        ttype_trigger = "key"
        out["timing"] = timing
        out["method"] = method
        out["trigger"] = ttype_trigger
        out["trigger_keys"] = trigger_keys
    elif trigger_commands:
        timing = "on-demand"
        method = method_norm
        ttype_trigger = "command"
        out["timing"] = timing
        out["method"] = method
        out["trigger"] = ttype_trigger
        out["trigger_commands"] = trigger_commands
    elif trigger_functions:
        timing = "on-demand"
        method = "local-source"
        ttype_trigger = "function"
        out["timing"] = timing
        out["method"] = method
        out["trigger"] = ttype_trigger
        out["trigger_functions"] = trigger_functions
    # Priority 1.5: Builtin compinit & git prompt
    elif ttype == "builtin" or name == "compinit":
        timing = "eager"
        method = "builtin"
        ttype_trigger = ""
        out["timing"] = timing
        out["method"] = method
    elif category == "git" or name == "ohmyzsh-git":
        timing = "eager"
        method = "source"
        ttype_trigger = ""
        out["timing"] = timing
        out["method"] = method
    # Priority 2: category in prompt, colors, completion(s)
    elif category in ("prompt", "colors", "completion", "completions"):
        timing = "eager"
        method = method_norm
        ttype_trigger = ""
        out["timing"] = timing
        out["method"] = method
    # Priority 3: category=core + type=binary + init_command -> eager/eval-cache
    elif category == "core" and ttype == "binary" and init_command:
        timing = "eager"
        method = "eval-cache"
        ttype_trigger = ""
        out["timing"] = timing
        out["method"] = method
    # Priority 3.5: eager tools by definition (e.g. ziro-aliases)
    elif tool.get("load_timing") == "eager" or name == "ziro-aliases":
        timing = "eager"
        method = "source" if method_norm in ("source", "local-source") else method_norm
        ttype_trigger = ""
        out["timing"] = timing
        out["method"] = method
    # Priority 4: category=core + type=plugin -> deferred
    elif category == "core" and ttype == "plugin":
        timing = "deferred"
        method = "source"
        ttype_trigger = ""
        out["timing"] = timing
        out["method"] = method
        out["stage"] = 5
        out["slot"] = "b"
    # Priority 5: navigation / fuzzy_finder -> on-demand
    elif category in ("navigation", "fuzzy_finder"):
        timing = "on-demand"
        method = method_norm
        ttype_trigger = "command" if category == "navigation" else "key"
        out["timing"] = timing
        out["method"] = method
        out["trigger"] = ttype_trigger
    # Priority 6: has init_command + requires binary -> eager/eval-cache
    elif init_command and requires:
        timing = "eager"
        method = "eval-cache"
        ttype_trigger = ""
        out["timing"] = timing
        out["method"] = method
    else:
        # Safe default
        timing = "deferred"
        method = "source"
        ttype_trigger = ""
        out["timing"] = timing
        out["method"] = method
        out["stage"] = 5
        out["slot"] = "b"

    # Carry forward path / fpath / eval_command / post_source / binary / conflicts_with
    local_p = tool.get("local_path") or tool.get("source_file")
    if "path" in tool:
        out["path"] = tool["path"]
        p_val = tool["path"]
        exp = os.path.expanduser(
            p_val.replace("${ZIRO_DATA}", str(Path.home() / ".local" / "share" / "ziro"))
                 .replace("${ZIRO_HOME}", str(Path.home() / ".ziro"))
                 .replace("$ZIRO_DATA", str(Path.home() / ".local" / "share" / "ziro"))
                 .replace("$ZIRO_HOME", str(Path.home() / ".ziro"))
        )
        if not os.path.exists(exp):
            out["unresolved"] = True
    elif local_p:
        res_path, res_ok = _resolve_vendor_path(local_p)
        out["path"] = res_path
        if not res_ok:
            out["unresolved"] = True
        if not out.get("source"):
            out["source"] = local_p
    elif method in ("source", "local-source") and source:
        res_path, res_ok = _resolve_vendor_path(source, subpath, tool.get("plugin_file", ""))
        if res_ok:
            out["path"] = res_path
        else:
            plugin_name = subpath.split("/")[-1] if subpath else source.split("/")[-1]
            fallback_sub = f"{subpath}/" if subpath else ""
            out["path"] = f"~/.local/share/ziro/vendor/{source}/{fallback_sub}{plugin_name}.plugin.zsh"
            out["unresolved"] = True

    if "fpath" in tool:
        out["fpath"] = tool["fpath"]
    elif name == "zsh-completions":
        out["fpath"] = ["~/.local/share/ziro/completions", "~/.local/share/ziro/vendor/zsh-users/zsh-completions/src"]

    if eval_command:
        out["eval_command"] = eval_command

    if "post_source" in tool:
        out["post_source"] = tool["post_source"]
    elif name == "starship":
        out["post_source"] = "setopt promptsubst"

    if "binary" in tool:
        out["binary"] = tool["binary"]

    if "conflicts_with" in tool:
        out["conflicts_with"] = tool["conflicts_with"]

    # Cache path for eval-cache tools
    if method == "eval-cache":
        out["cache_path"] = tool.get("cache_path") or f"~/.cache/ziro/eval-cache/{cache_key}.zsh"

    if init_command:
        out["init_command"] = init_command

    # Reason
    signals = {
        "trigger_keys": trigger_keys,
        "trigger_commands": trigger_commands,
        "trigger_functions": trigger_functions,
    }
    out["reason"] = _heuristic_tool_reason(timing, method, ttype_trigger, category, signals)

    # Security heuristic integration (Phase C)
    if ttype in ("builtin", "binary"):
        sec = {
            "trust_score": 4,
            "trust_level": "high",
            "signals": {"known_org": True, "has_release_tag": True, "recent_activity": True, "source_clean": True},
            "dangerous_found": [],
            "notes": [],
            "blocked": False,
            "override_required": False,
        }
        final_strat, report, blocked, override_req = (
            ("eager", "agree", False, False) if timing == "eager" else ("lazy", "agree", False, False)
        )
    else:
        p_val = out.get("path") or tool.get("path") or ""
        target_path = None
        if p_val:
            exp = os.path.expanduser(
                p_val.replace("${ZIRO_DATA}", str(Path.home() / ".local" / "share" / "ziro"))
                     .replace("${ZIRO_HOME}", str(Path.home() / ".ziro"))
                     .replace("$ZIRO_DATA", str(Path.home() / ".local" / "share" / "ziro"))
                     .replace("$ZIRO_HOME", str(Path.home() / ".ziro"))
            )
            if os.path.exists(exp):
                p_obj = Path(exp)
                target_path = p_obj.parent if p_obj.is_file() else p_obj
        if target_path is None and source:
            res_p, res_ok = _resolve_vendor_path(source, subpath, tool.get("plugin_file", ""))
            if res_ok:
                p_obj = Path(os.path.expanduser(res_p))
                target_path = p_obj.parent if p_obj.is_file() else p_obj
        if target_path is None and local_p:
            res_p, res_ok = _resolve_vendor_path(local_p)
            if res_ok:
                p_obj = Path(os.path.expanduser(res_p))
                target_path = p_obj.parent if p_obj.is_file() else p_obj

        is_internal = (
            name.startswith("ziro-")
            or (local_p and any(d in str(local_p) for d in ("lib/", "core/", "commands/")))
        )
        if is_internal:
            sec = {
                "trust_score": None,
                "trust_level": "internal",
                "signals": {
                    "known_org": True,
                    "has_release_tag": True,
                    "recent_activity": True,
                    "source_clean": True,
                },
                "dangerous_found": [],
                "notes": [],
                "contains_dangerous": False,
                "blocked": False,
                "override_required": False,
            }
            final_strat = "eager" if timing == "eager" else "lazy"
            report = "agree"
            blocked = False
            override_req = False
        elif target_path is not None:
            sec = _security_heuristic(target_path, source=source)
        else:
            sec = _security_heuristic(Path(source or name), source=source)

        perf_timing = "eager" if timing == "eager" else "lazy"
        final_strat, report, blocked, override_req = _apply_decision_matrix(
            sec["trust_level"], perf_timing, bool(sec["dangerous_found"])
        )
        if final_strat == "deferred" and timing == "eager":
            out["timing"] = "deferred"
            out["stage"] = 5
            out["slot"] = "b"
        elif blocked:
            out["blocked"] = True
            out["timing"] = "deferred"

    out["trust_score"] = sec["trust_score"]
    out["trust_level"] = sec["trust_level"]
    out["security_notes"] = sec["notes"]
    out["blocked"] = blocked
    out["override_required"] = override_req
    out["security_report"] = report

    return out


def analyze_from_manifest(
    plugin_dir: Path, manifest_file: Path, plugin_name: str = ""
) -> AnalysisResult:
    """Manifest-first analysis: parse ziro-plugin.toml per GAP-7 (Spec 012)."""
    plugin_name = plugin_name or plugin_dir.name
    task_slug = slug(plugin_name)

    try:
        with manifest_file.open("rb") as f:
            data = tomllib.load(f)
    except Exception:
        return analyze_by_regex(plugin_dir, plugin_name)

    stages_data = data.get("load", {}).get("stages", [])
    if stages_data and isinstance(stages_data, list):
        first_stage = stages_data[0]
        st_id = int(first_stage.get("id", 1))
        st_slot = first_stage.get("slot", "a")
        depends = tuple(first_stage.get("depends", []))
        budget_ms = int(first_stage.get("budget_ms", 5000))
    else:
        st_id = 5
        st_slot = "b"
        depends = ()
        budget_ms = 5000

    strat = Strategy.EAGER if st_id <= 4 else Strategy.LAZY
    main_file = data.get("load", {}).get("main", "") or _find_main_file(plugin_dir, plugin_name)

    rec = Recommendation(
        strategy=strat,
        stage=st_id,
        slot=st_slot,
        name=task_slug,
        depends=depends,
        timeout_ms=budget_ms,
        pick=main_file,
    )

    sec = _security_heuristic(plugin_dir)
    perf_timing = "eager" if strat == Strategy.EAGER else "lazy"
    final_strat, report, blocked, override_req = _apply_decision_matrix(
        sec["trust_level"], perf_timing, bool(sec["dangerous_found"])
    )

    return AnalysisResult(
        plugin=plugin_name,
        source=str(plugin_dir),
        detected=DetectedSignals(),
        recommended=rec,
        confidence=1.0,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
        analyzer_version=ANALYZER_VERSION,
        trust_score=sec["trust_score"],
        trust_level=sec["trust_level"],
        security_notes=sec["notes"],
        blocked=blocked,
        override_required=override_req,
    )


def analyze_by_regex(plugin_dir: Path, plugin_name: str = "") -> AnalysisResult:
    """Analyze plugin source via static regex analysis."""
    plugin_name = plugin_name or plugin_dir.name
    task_slug = slug(plugin_name)

    chunks: list[str] = []
    line_count = 0
    for src in _read_source_files(plugin_dir):
        try:
            txt = src.read_text(errors="ignore")
            chunks.append(txt)
            line_count += len(txt.splitlines())
        except OSError:
            continue

    content = "\n".join(chunks)
    signals = _detect_signals(content)
    key_binding = _extract_bindkey(content)
    condition = _extract_condition(content)

    rec = _recommend(
        signals,
        line_count=line_count,
        key_binding=key_binding,
        condition=condition,
        task_name=task_slug,
    )
    confidence = _confidence(signals)

    main_file = _find_main_file(plugin_dir, plugin_name)
    if main_file:
        rec = Recommendation(
            strategy=rec.strategy,
            compile=rec.compile,
            eval_cache=rec.eval_cache,
            adapter_options=rec.adapter_options,
            pick=main_file,
            stage=rec.stage,
            slot=rec.slot,
            name=rec.name,
            depends=rec.depends,
            condition=rec.condition,
            on_key=rec.on_key,
            cache_type=rec.cache_type,
            timeout_ms=rec.timeout_ms,
        )

    sec = _security_heuristic(plugin_dir)
    perf_timing = "eager" if (rec.strategy == Strategy.EAGER or getattr(rec, "stage", 5) in (1, 2, 3, 4)) else "lazy"
    final_strat, report, blocked, override_req = _apply_decision_matrix(
        sec["trust_level"], perf_timing, bool(sec["dangerous_found"])
    )

    return AnalysisResult(
        plugin=plugin_name,
        source=str(plugin_dir),
        detected=signals,
        recommended=rec,
        confidence=confidence,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
        analyzer_version=ANALYZER_VERSION,
        trust_score=sec["trust_score"],
        trust_level=sec["trust_level"],
        security_notes=sec["notes"],
        blocked=blocked,
        override_required=override_req,
    )


def analyze_plugin(plugin_dir: Path, plugin_name: str = "") -> AnalysisResult:
    """Analyze single plugin directory: Manifest-first, Regex fallback."""
    plugin_dir = Path(plugin_dir)
    plugin_name = plugin_name or plugin_dir.name

    if not plugin_dir.is_dir():
        return AnalysisResult.empty(plugin_name)

    manifest_file = plugin_dir / "ziro-plugin.toml"
    if manifest_file.is_file():
        return analyze_from_manifest(plugin_dir, manifest_file, plugin_name)
    return analyze_by_regex(plugin_dir, plugin_name)


def analyze_with_cache(plugin_dir: Path, plugin_name: str = "") -> AnalysisResult:
    """Analyze plugin, using cache if source hash matches."""
    from core.cache import compute_source_hash, load_cached, store_cached

    plugin_dir = Path(plugin_dir)
    plugin_name = plugin_name or plugin_dir.name

    if not plugin_dir.is_dir():
        return AnalysisResult.empty(plugin_name)

    source_hash = compute_source_hash(plugin_dir)

    cached = load_cached(plugin_name, source_hash)
    if cached is not None:
        return cached

    result = analyze_plugin(plugin_dir, plugin_name)
    store_cached(plugin_name, source_hash, result)
    return result


async def analyze_many_async(
    plugins: list[tuple[Path, str]],
    concurrency: int = 8,
) -> list[AnalysisResult]:
    """Analyze multiple plugins in parallel using asyncio."""
    import asyncio

    sem = asyncio.Semaphore(concurrency)

    async def _one(pd: Path, name: str) -> AnalysisResult:
        async with sem:
            return await asyncio.to_thread(analyze_with_cache, pd, name)

    return await asyncio.gather(*(_one(pd, name) for pd, name in plugins))


def analyze_many(
    plugins: list[tuple[Path, str]],
    concurrency: int = 8,
) -> list[AnalysisResult]:
    """Synchronous entry point for parallel analysis."""
    import asyncio
    return asyncio.run(analyze_many_async(plugins, concurrency))


__all__ = [
    "analyze_plugin",
    "analyze_from_manifest",
    "analyze_by_regex",
    "analyze_tool",
    "analyze_all",
    "_resolve_vendor_path",
    "slug",
    "ANALYZER_VERSION",
]

# Convenience properties on AnalysisResult for direct attribute access
if not hasattr(AnalysisResult, "stage"):
    AnalysisResult.stage = property(lambda self: getattr(self.recommended, "stage", 5))
if not hasattr(AnalysisResult, "slot"):
    AnalysisResult.slot = property(lambda self: getattr(self.recommended, "slot", "b"))
if not hasattr(AnalysisResult, "on_key"):
    AnalysisResult.on_key = property(lambda self: getattr(self.recommended, "on_key", None))


def analyze_all(
    tools_factory_path: str | None = None,
    vendor_plugin_dirs: list | None = None,
    load_toml_path: str | None = None,
) -> dict:
    """Full analysis producing a load.toml-compatible manifest dict.

    Reads:
      - tools_factory.toml (known tools)
      - installed plugins in vendor_plugin_dirs (unknown tools)
      - existing load.toml [user] section (preserved verbatim)

    Returns:
      {
        "meta": {...}, "boot": {...}, "defer": {...},
        "tool": [<analyzed tool dicts>],
        "user": <verbatim user section dict>
      }
    """
    import datetime
    from pathlib import Path as _P

    if tools_factory_path is None:
        tools_factory_path = str(_P(__file__).parent / "tools_factory.toml")
    if load_toml_path is None:
        load_toml_path = str(_P.home() / ".config" / "ziro" / "load.toml")

    # Load factory
    factory = {"tool": []}
    tf = _P(tools_factory_path)
    if tf.is_file():
        try:
            with tf.open("rb") as f:
                factory = tomllib.load(f)
        except Exception as e:
            raise ValueError(f"could not parse tools_factory.toml: {e}")

    # Load existing load.toml to preserve [user], [boot], [defer], and tool enabled state
    existing = {}
    lt = _P(load_toml_path)
    if lt.is_file():
        try:
            with lt.open("rb") as f:
                existing = tomllib.load(f)
        except Exception as e:
            raise ValueError(f"could not parse existing load.toml: {e}")

    user_section = existing.get("user", {})
    existing_tools = {t["name"]: t for t in existing.get("tool", []) if isinstance(t, dict) and "name" in t}

    # Analyze each known tool in factory
    analyzed_tools = []
    seen_names = set()
    for entry in factory.get("tool", []):
        name = entry.get("name")
        if not name or name in seen_names:
            continue
        # Skip bootstrap infrastructure
        if entry.get("type") == "bootstrap" or entry.get("category") == "infra":
            continue
        # Skip alternatives that were not selected or active in load.toml
        if entry.get("alternatives_only", False) and name not in existing_tools:
            continue
        try:
            out = analyze_tool(entry)
            if name in existing_tools and "enabled" in existing_tools[name]:
                out["enabled"] = existing_tools[name]["enabled"]
            analyzed_tools.append(out)
            seen_names.add(name)
        except Exception:
            pass

    # Build output dict
    result = {
        "meta": {
            "schema_version": "1.0.0",
            "generated_by": "ziro analyze",
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "analyzer_version": globals().get("ANALYZER_VERSION", "0.2.0"),
        },
        "boot": existing.get("boot", {
            "artifact": "~/.cache/ziro/ziro-boot.zsh",
            "zwc": "~/.cache/ziro/ziro-boot.zwc",
        }),
        "defer": existing.get("defer", {
            "eager_modules": [
                "stages/stage-0-pre-source.zsh",
                "core/version.zsh",
                "core/queue.zsh",
                "core/task-registry.zsh",
                "core/scheduler.zsh",
                "core/hooks.zsh",
                "api/ziro-defer.zsh",
                "api/ziro-defer-bind-widget.zsh",
            ],
        }),
        "tool": analyzed_tools,
        "user": user_section,
    }
    return result

